import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/app.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/startup/error_screen.dart';
import 'package:snickerdoodle/src/startup/loading_screen.dart';
import 'package:snickerdoodle/src/startup/startup_task.dart';
import 'package:snickerdoodle/src/startup/startup_tasks.dart';

/// Orchestrates the app startup sequence.
///
/// Manages execution of critical, best effort, and background tasks,
/// showing appropriate UI states and handling errors with retry logic.
class StartupOrchestrator extends StatefulWidget {
  const StartupOrchestrator({required this.initialOverrides, super.key});

  /// Initial provider overrides (e.g., from main.dart setup).
  final List<Override> initialOverrides;

  @override
  State<StartupOrchestrator> createState() => _StartupOrchestratorState();
}

class _StartupOrchestratorState extends State<StartupOrchestrator> {
  _StartupState _state = _StartupState.loading;
  String _errorMessage = '';
  int _completedTasks = 0;
  List<Override> _collectedOverrides = [];

  // Total tasks we track for progress (critical + best effort)
  final int _totalTrackedTasks =
      criticalBlockingTasks.length + bestEffortBlockingTasks.length;

  @override
  void initState() {
    super.initState();
    _runStartupSequence();
  }

  /// Main startup sequence orchestration.
  Future<void> _runStartupSequence() async {
    if (!mounted) return;
    setState(() {
      _state = _StartupState.loading;
      _completedTasks = 0;
      _collectedOverrides = [];
    });

    final initialContext = StartupContext(
      ProviderContainer(overrides: widget.initialOverrides),
    );
    StartupContext? enrichedContext;
    bool tasksLaunched =
        false; // Track if we launched tasks (for cleanup on error)

    try {
      // Phase 1: Critical blocking tasks (with retry)
      AppLogger.debug('Starting critical tasks...');
      await _runCriticalTasksWithRetry(initialContext);
      AppLogger.debug('Critical tasks completed');

      // Recreate container with accumulated overrides from critical tasks
      // This container will be used by both best-effort and background tasks
      // and must stay alive until ALL tasks complete
      AppLogger.debug(
        'Recreating container with ${initialContext.overrides.length} overrides',
      );
      enrichedContext = initialContext.recreateWithOverrides(
        widget.initialOverrides,
      );

      // Start performance trace for post-critical startup phase
      // (Firebase is now initialized, so Performance SDK is available)
      final perfService = enrichedContext.container.read(
        performanceServiceProvider,
      );
      perfService.startNamedTrace(name: TraceName.startupPostCritical);

      // Dispose the initial container since we now have an enriched one
      try {
        initialContext.container.dispose();
      } catch (e) {
        AppLogger.warn('Error disposing initial container: $e');
        // Continue anyway - enrichedContext is ready
      }

      // Phase 2: Best effort and background tasks (parallel)
      // Both task types use the enrichedContext container which stays alive
      // until ALL tasks complete (even those that timeout or run in background)
      AppLogger.debug('Starting best effort and background tasks...');
      final bestEffortFutures = bestEffortBlockingTasks
          .map(
            (task) => _runBestEffortTask(task, enrichedContext!, perfService),
          )
          .toList();
      final backgroundFutures = backgroundTasks
          .map(
            (task) => _runBackgroundTask(task, enrichedContext!, perfService),
          )
          .toList();

      // Set up disposal callback IMMEDIATELY to prevent memory leaks if exceptions occur
      // This must happen before setting tasksLaunched or awaiting any futures
      // ignore: unawaited_futures
      Future.wait([...bestEffortFutures, ...backgroundFutures])
          .then((_) {
            AppLogger.debug('All tasks completed');
            enrichedContext?.container.dispose();
          })
          .catchError((e) {
            AppLogger.warn('Task error: $e');
            enrichedContext?.container.dispose();
          });

      tasksLaunched = true; // Tasks are now running and disposal is registered

      // Wait for best effort tasks with timeout (for UI progression)
      await Future.wait(bestEffortFutures).timeout(
        bestEffortTimeout,
        onTimeout: () {
          AppLogger.debug('Best effort tasks timed out');
          return [];
        },
      );

      AppLogger.debug('Startup sequence completed successfully');

      // Collect all overrides accumulated during critical tasks
      _collectedOverrides = [
        ...widget.initialOverrides,
        ...initialContext.overrides,
      ];

      // Give the progress bar time to fill
      if (!mounted) return;
      setState(() {
        // Force 100% completion for UX even if best effort tasks failed
        _completedTasks = _totalTrackedTasks;
      });
      await Future.delayed(Duration(milliseconds: 1000));

      // Stop the post-critical startup trace before transitioning to ready state
      perfService.stopNamedTrace(name: TraceName.startupPostCritical);

      if (!mounted) return;

      setState(() {
        _state = _StartupState.ready;
      });
    } catch (e) {
      AppLogger.warn('Startup sequence failed: $e');

      // Clean up containers if tasks weren't launched
      // If tasks were launched, they'll dispose the container when they complete
      if (!tasksLaunched) {
        if (enrichedContext != null) {
          enrichedContext.container.dispose();
        } else {
          // Error during critical tasks, enrichedContext was never created
          initialContext.container.dispose();
        }
      }

      if (!mounted) return;
      setState(() {
        _state = _StartupState.error;
        _errorMessage = e.toString();
      });
    }
  }

  /// Run critical tasks with retry logic.
  ///
  /// Each task is retried up to 3 times on failure. Only failed tasks are
  /// retried, not successful ones.
  Future<void> _runCriticalTasksWithRetry(StartupContext context) async {
    const maxRetries = 3;
    final failedTasks = <StartupTask>[];
    final tasksToRun = List<StartupTask>.from(criticalBlockingTasks);

    for (int attempt = 1; attempt <= maxRetries; attempt++) {
      failedTasks.clear();

      // Run all tasks (or retry only failed ones) in parallel
      final results = await Future.wait(
        tasksToRun.map((task) async {
          try {
            await task.execute(context);
            _incrementProgress();
            AppLogger.debug('Critical task completed: ${task.id}');
            return _TaskResult(task, success: true);
          } catch (e) {
            AppLogger.warn(
              'Critical task failed (attempt $attempt): ${task.id} - $e',
            );
            if (attempt == maxRetries) {
              // Log to console but don't try to use crashlytics if it's not initialized
              AppLogger.warn(
                'Critical task failed after $maxRetries attempts: ${task.id} - $e',
              );
            }
            return _TaskResult(task, success: false, error: e);
          }
        }),
      );

      // Collect failed tasks for retry
      for (final result in results) {
        if (!result.success) {
          failedTasks.add(result.task);
        }
      }

      // If all succeeded, we're done
      if (failedTasks.isEmpty) {
        return;
      }

      // If this was the last attempt, throw
      if (attempt == maxRetries) {
        throw Exception(
          'Critical tasks failed after $maxRetries attempts: '
          '${failedTasks.map((t) => t.id).join(", ")}',
        );
      }

      // Prepare to retry only failed tasks
      tasksToRun.clear();
      tasksToRun.addAll(failedTasks);
      AppLogger.debug(
        'Retrying ${failedTasks.length} failed tasks (attempt ${attempt + 1})...',
      );
    }
  }

  /// Run a best effort task.
  ///
  /// Failures are logged to crashlytics but don't prevent startup.
  Future<void> _runBestEffortTask(
    StartupTask task,
    StartupContext context,
    PerformanceService perfService,
  ) async {
    if (task.traceName != null) {
      perfService.startNamedTrace(name: task.traceName!);
    }

    try {
      await task.execute(context);
      _incrementProgress();
      AppLogger.debug('Best effort task completed: ${task.id}');

      if (task.traceName != null) {
        perfService.stopNamedTrace(name: task.traceName!);
      }
    } catch (e) {
      AppLogger.warn('Best effort task failed: ${task.id} - $e');
      // Drop the trace on failure (don't report failed tasks)
      if (task.traceName != null) {
        perfService.dropNamedTrace(name: task.traceName!);
      }
      // Errors are already logged to crashlytics in task implementations
    }
  }

  /// Run a background task.
  ///
  /// Failures are logged to crashlytics but don't prevent startup.
  Future<void> _runBackgroundTask(
    StartupTask task,
    StartupContext context,
    PerformanceService perfService,
  ) async {
    if (task.traceName != null) {
      perfService.startNamedTrace(name: task.traceName!);
    }

    try {
      await task.execute(context);
      AppLogger.debug('Background task completed: ${task.id}');

      if (task.traceName != null) {
        perfService.stopNamedTrace(name: task.traceName!);
      }
    } catch (e) {
      AppLogger.warn('Background task failed: ${task.id} - $e');
      // Drop the trace on failure (don't report failed tasks)
      if (task.traceName != null) {
        perfService.dropNamedTrace(name: task.traceName!);
      }
      // Errors are already logged to crashlytics in task implementations
    }
  }

  /// Increment the progress counter and update UI.
  void _incrementProgress() {
    if (!mounted) return;
    setState(() {
      _completedTasks++;
    });
  }

  @override
  Widget build(BuildContext context) {
    switch (_state) {
      case _StartupState.loading:
        return LoadingScreen(
          completed: _completedTasks,
          total: _totalTrackedTasks,
        );

      case _StartupState.error:
        return ErrorScreen(error: _errorMessage, onRetry: _runStartupSequence);

      case _StartupState.ready:
        return ProviderScope(
          overrides: _collectedOverrides,
          child: const App(),
        );
    }
  }
}

/// Internal state of the startup orchestrator.
enum _StartupState { loading, error, ready }

/// Result of a task execution (used internally for retry logic).
class _TaskResult {
  _TaskResult(this.task, {required this.success, this.error});

  final StartupTask task;
  final bool success;
  final Object? error;
}
