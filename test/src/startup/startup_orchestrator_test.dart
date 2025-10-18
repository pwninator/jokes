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
          overrides: [performanceServiceProvider.overrideWithValue(mockPerf)],
          child: MaterialApp(
            home: StartupOrchestrator(
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
}
