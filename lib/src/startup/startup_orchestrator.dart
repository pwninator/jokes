import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/app.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
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
    StartupContext? initialContext;
    StartupContext? enrichedContext;
    // Track if we launched tasks (for cleanup on error)
    bool tasksLaunched = false;

    try {
      if (!mounted) return;
      setState(() {
        _state = _StartupState.loading;
        _completedTasks = 0;
        _collectedOverrides = [];
      });

      initialContext = StartupContext(
        ProviderContainer(overrides: widget.initialOverrides),
      );
      // Read services from initial context for critical tasks
      final perfService = initialContext.container.read(
        performanceServiceProvider,
      );
      // Start performance trace for startup phase
      perfService.startNamedTrace(name: TraceName.startupOverall);

      final crashlyticsService = initialContext.container.read(
        crashReportingServiceProvider,
      );

      // Phase 1: Critical blocking tasks (with retry)
      AppLogger.debug('Starting critical tasks...');
      await _runCriticalTasksWithRetry(
        initialContext,
        perfService,
        crashlyticsService,
      );
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
            (task) => _runBestEffortTask(
              task,
              enrichedContext!,
              perfService,
              crashlyticsService,
            ),
          )
          .toList();
      final backgroundFutures = backgroundTasks
          .map(
            (task) => _runBackgroundTask(
              task,
              enrichedContext!,
              perfService,
              crashlyticsService,
            ),
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

      // Give the progress bar time to fill
      await Future.delayed(LoadingScreen.progressBarAnimationDuration);

      // Stop the post-critical startup trace before transitioning to ready state
      perfService.stopNamedTrace(name: TraceName.startupOverall);

      if (!mounted) return;

      setState(() {
        _state = _StartupState.ready;
      });
    } catch (e) {
      AppLogger.fatal('Startup sequence failed: $e');

      // Clean up containers if tasks weren't launched
      // If tasks were launched, they'll dispose the container when they complete
      if (!tasksLaunched) {
        initialContext?.container.dispose();
        enrichedContext?.container.dispose();
      }

      if (!mounted) return;
      setState(() {
        _state = _StartupState.error;
      });
    }
  }

  /// Run critical tasks with retry logic.
  ///
  /// Each task is retried up to 3 times on failure. Only failed tasks are
  /// retried, not successful ones. Traces cover all retries and only complete
  /// on success or after 3 failures.
  Future<void> _runCriticalTasksWithRetry(
    StartupContext context,
    PerformanceService perfService,
    CrashReportingService crashService,
  ) async {
    const maxRetries = 3;
    final failedTasks = <StartupTask>[];
    final tasksToRun = List<StartupTask>.from(criticalBlockingTasks);

    // Start traces for all critical tasks at the beginning
    // Each trace will measure from start until completion (including retries)
    for (final task in criticalBlockingTasks) {
      perfService.startNamedTrace(name: task.traceName);
    }

    try {
      for (int attempt = 1; attempt <= maxRetries; attempt++) {
        failedTasks.clear();

        // Run all tasks (or retry only failed ones) in parallel
        final results = await Future.wait(
          tasksToRun.map((task) async {
            try {
              await task.execute(context);
              _incrementProgress();
              AppLogger.debug('Startup Critical Task completed: ${task.id}');

              // Stop trace on success
              perfService.stopNamedTrace(name: task.traceName);
              return _TaskResult(task, success: true);
            } catch (e, stackTrace) {
              if (attempt == maxRetries) {
                AppLogger.fatal(
                  'Startup Critical Task failed after $maxRetries attempts: ${task.id} - $e',
                  stackTrace: stackTrace,
                );
                // Stop trace on final failure
                perfService.stopNamedTrace(name: task.traceName);
              } else {
                AppLogger.error(
                  'Startup Critical Task ${task.id} failed (attempt $attempt): $e',
                  stackTrace: stackTrace,
                );
              }
              return _TaskResult(
                task,
                success: false,
                error: e,
                stackTrace: stackTrace.toString(),
              );
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
    } catch (e) {
      // Ensure any remaining traces are stopped on unexpected error
      for (final task in criticalBlockingTasks) {
        perfService.stopNamedTrace(name: task.traceName);
      }
      rethrow;
    }
  }

  /// Run a best effort task.
  ///
  /// Failures are logged to crashlytics but don't prevent startup.
  Future<void> _runBestEffortTask(
    StartupTask task,
    StartupContext context,
    PerformanceService perfService,
    CrashReportingService crashService,
  ) async {
    perfService.startNamedTrace(name: task.traceName);

    try {
      await task.execute(context);
      _incrementProgress();
      AppLogger.debug('Startup Best effort task completed: ${task.id}');

      perfService.stopNamedTrace(name: task.traceName);
    } catch (e, stack) {
      AppLogger.fatal(
        'Startup Best effort task failed: ${task.id} - $e',
        stackTrace: stack,
      );

      // Drop the trace on failure (don't report failed tasks)
      perfService.dropNamedTrace(name: task.traceName);
    }
  }

  /// Run a background task.
  ///
  /// Failures are logged to crashlytics but don't prevent startup.
  Future<void> _runBackgroundTask(
    StartupTask task,
    StartupContext context,
    PerformanceService perfService,
    CrashReportingService crashService,
  ) async {
    perfService.startNamedTrace(name: task.traceName);

    try {
      await task.execute(context);
      AppLogger.debug('Startup Background task completed: ${task.id}');

      perfService.stopNamedTrace(name: task.traceName);
    } catch (e, stack) {
      AppLogger.fatal(
        'Startup Background task failed: ${task.id} - $e',
        stackTrace: stack,
      );

      // Drop the trace on failure (don't report failed tasks)
      perfService.dropNamedTrace(name: task.traceName);
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
        return ErrorScreen(onRetry: _runStartupSequence);

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
  _TaskResult(this.task, {required this.success, this.error, this.stackTrace});

  final StartupTask task;
  final bool success;
  final Object? error;
  final String? stackTrace;
}
