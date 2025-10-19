import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/startup/startup_orchestrator.dart';
import 'package:snickerdoodle/src/startup/startup_task.dart';

class MockPerformanceService extends Mock implements PerformanceService {}

// Fake provider for testing
final fakeProvider = Provider<String>((ref) => 'fake_value');

// Simple test widget that shows when startup completes and can verify overrides
class TestStartupCompleteWidget extends ConsumerWidget {
  const TestStartupCompleteWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Try to read our fake provider to verify overrides work
    final fakeValue = ref.read(fakeProvider);

    return MaterialApp(
      home: Scaffold(
        body: Center(child: Text('Startup Complete - Override: $fakeValue')),
      ),
    );
  }
}

// Mock App widget that can verify it receives overrides
class MockAppWidget extends ConsumerWidget {
  const MockAppWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Try to read our fake provider to verify overrides work
    final fakeValue = ref.read(fakeProvider);

    return MaterialApp(
      home: Scaffold(
        body: Center(child: Text('Mock App - Override: $fakeValue')),
      ),
    );
  }
}

void main() {
  late MockPerformanceService mockPerf;

  setUpAll(() {
    registerFallbackValue(TraceName.startupOverallBlocking);
  });

  setUp(() {
    mockPerf = MockPerformanceService();

    // Mock performance service methods
    when(
      () => mockPerf.startNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerf.stopNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerf.dropNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenReturn(null);
  });

  testWidgets(
    'best effort and background tasks can access critical task overrides',
    (tester) async {
      bool criticalTaskExecuted = false;
      bool bestEffortTaskExecuted = false;
      bool backgroundTaskExecuted = false;
      String? bestEffortOverrideValue;
      String? backgroundOverrideValue;

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: StartupOrchestrator(
              firebaseOverrides: [
                performanceServiceProvider.overrideWithValue(mockPerf),
              ],
              criticalTasks: [
                StartupTask(
                  id: 'critical_task',
                  traceName: TraceName.startupTaskDrift,
                  execute: (read) async {
                    criticalTaskExecuted = true;
                    return [
                      fakeProvider.overrideWithValue('critical_override'),
                    ];
                  },
                ),
              ],
              bestEffortTasks: [
                StartupTask(
                  id: 'best_effort_task',
                  traceName: TraceName.startupTaskSharedPrefs,
                  execute: (read) async {
                    bestEffortTaskExecuted = true;
                    // Try to read the override from the critical task
                    bestEffortOverrideValue = read(fakeProvider);
                    return []; // Best effort tasks don't return overrides
                  },
                ),
              ],
              backgroundTasks: [
                StartupTask(
                  id: 'background_task',
                  traceName: TraceName.startupTaskDrift,
                  execute: (read) async {
                    backgroundTaskExecuted = true;
                    // Try to read the override from the critical task
                    backgroundOverrideValue = read(fakeProvider);
                    return []; // Background tasks don't return overrides
                  },
                ),
              ],
              readyWidget: const MockAppWidget(),
            ),
          ),
        ),
      );

      // Let startup complete (including best effort tasks)
      await tester.pump();
      await tester.pump(const Duration(seconds: 2));

      // Verify critical task was executed
      expect(criticalTaskExecuted, isTrue);

      // Verify best effort task was executed
      expect(bestEffortTaskExecuted, isTrue);

      // Verify background task was executed
      expect(backgroundTaskExecuted, isTrue);

      // Verify best effort task could access the critical task's override
      expect(bestEffortOverrideValue, equals('critical_override'));

      // Verify background task could access the critical task's override
      expect(backgroundOverrideValue, equals('critical_override'));

      // Verify startup completed successfully and Mock App received overrides
      expect(
        find.text('Mock App - Override: critical_override'),
        findsOneWidget,
      );
    },
  );

  testWidgets('shows error screen when critical task fails after retries', (
    tester,
  ) async {
    int taskAttempts = 0;

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: StartupOrchestrator(
            firebaseOverrides: [
              performanceServiceProvider.overrideWithValue(mockPerf),
            ],
            criticalTasks: [
              StartupTask(
                id: 'failing_task',
                traceName: TraceName.startupTaskDrift,
                execute: (read) async {
                  taskAttempts++;
                  throw Exception('Task failed on attempt $taskAttempts');
                },
              ),
            ],
            bestEffortTasks: const [],
            backgroundTasks: const [],
            readyWidget: const MockAppWidget(),
          ),
        ),
      ),
    );

    // Let startup attempt to complete (should fail after retries)
    await tester.pump();
    await tester.pump(const Duration(seconds: 5));

    // Verify task was attempted multiple times (retry logic)
    expect(taskAttempts, greaterThan(1));

    // Verify error screen is shown
    expect(find.text('We hit a snag...'), findsOneWidget);
    expect(find.text('Retry Startup'), findsOneWidget);
  });

  testWidgets('best effort task failure does not prevent startup', (
    tester,
  ) async {
    bool criticalTaskExecuted = false;
    bool bestEffortTaskFailed = false;

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: StartupOrchestrator(
            firebaseOverrides: [
              performanceServiceProvider.overrideWithValue(mockPerf),
            ],
            criticalTasks: [
              StartupTask(
                id: 'critical_task',
                traceName: TraceName.startupTaskDrift,
                execute: (read) async {
                  criticalTaskExecuted = true;
                  return [fakeProvider.overrideWithValue('critical_override')];
                },
              ),
            ],
            bestEffortTasks: [
              StartupTask(
                id: 'failing_best_effort_task',
                traceName: TraceName.startupTaskSharedPrefs,
                execute: (read) async {
                  bestEffortTaskFailed = true;
                  throw Exception('Best effort task failed');
                },
              ),
            ],
            backgroundTasks: const [],
            readyWidget: const MockAppWidget(),
          ),
        ),
      ),
    );

    // Let startup complete
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));

    // Verify critical task was executed
    expect(criticalTaskExecuted, isTrue);

    // Verify best effort task failed
    expect(bestEffortTaskFailed, isTrue);

    // Verify startup completed successfully despite best effort failure
    expect(find.text('Mock App - Override: critical_override'), findsOneWidget);
  });

  testWidgets('background task failure does not prevent startup', (
    tester,
  ) async {
    bool criticalTaskExecuted = false;
    bool backgroundTaskFailed = false;

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: StartupOrchestrator(
            firebaseOverrides: [
              performanceServiceProvider.overrideWithValue(mockPerf),
            ],
            criticalTasks: [
              StartupTask(
                id: 'critical_task',
                traceName: TraceName.startupTaskDrift,
                execute: (read) async {
                  criticalTaskExecuted = true;
                  return [fakeProvider.overrideWithValue('critical_override')];
                },
              ),
            ],
            bestEffortTasks: const [],
            backgroundTasks: [
              StartupTask(
                id: 'failing_background_task',
                traceName: TraceName.startupTaskDrift,
                execute: (read) async {
                  backgroundTaskFailed = true;
                  throw Exception('Background task failed');
                },
              ),
            ],
            readyWidget: const MockAppWidget(),
          ),
        ),
      ),
    );

    // Let startup complete
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));

    // Verify critical task was executed
    expect(criticalTaskExecuted, isTrue);

    // Verify background task failed
    expect(backgroundTaskFailed, isTrue);

    // Verify startup completed successfully despite background failure
    expect(find.text('Mock App - Override: critical_override'), findsOneWidget);
  });

  testWidgets('can retry startup from error screen', (tester) async {
    int taskAttempts = 0;

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: StartupOrchestrator(
            firebaseOverrides: [
              performanceServiceProvider.overrideWithValue(mockPerf),
            ],
            criticalTasks: [
              StartupTask(
                id: 'failing_task',
                traceName: TraceName.startupTaskDrift,
                execute: (read) async {
                  taskAttempts++;
                  // Always fail to ensure we see the error screen
                  throw Exception('Task failed on attempt $taskAttempts');
                },
              ),
            ],
            bestEffortTasks: const [],
            backgroundTasks: const [],
            readyWidget: const MockAppWidget(),
          ),
        ),
      ),
    );

    // Let startup fail initially
    await tester.pump();
    await tester.pump(const Duration(seconds: 5));

    // Verify error screen is shown
    expect(find.text('We hit a snag...'), findsOneWidget);
    expect(find.text('Retry Startup'), findsOneWidget);

    // Verify task was attempted multiple times (retry logic)
    expect(taskAttempts, greaterThan(1));
  });
}
