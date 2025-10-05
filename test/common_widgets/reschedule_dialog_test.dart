import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/reschedule_dialog.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_service.dart';

class MockJokeScheduleAutoFillService extends Mock implements JokeScheduleAutoFillService {}

void main() {
  group('RescheduleDialog', () {
    late MockJokeScheduleAutoFillService mockService;
    const jokeId = 'test-joke-id';
    // Use dynamic future dates to avoid assertion errors
    final initialDate = DateTime.now().add(const Duration(days: 10));
    final newDate = DateTime.now().add(const Duration(days: 20));

    setUpAll(() {
      registerFallbackValue(DateTime.now());
    });

    setUp(() {
      mockService = MockJokeScheduleAutoFillService();
      when(() => mockService.scheduleJokeToDate(
            jokeId: any(named: 'jokeId'),
            date: any(named: 'date'),
            scheduleId: any(named: 'scheduleId'),
          )).thenAnswer((_) async {});
    });

    Widget createTestWidget({
      String? scheduleId,
      VoidCallback? onSuccess,
      List<DateTime>? scheduledDates,
    }) {
      return ProviderScope(
        overrides: [
          jokeScheduleAutoFillServiceProvider.overrideWithValue(mockService),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return ElevatedButton(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (_) => RescheduleDialog(
                        jokeId: jokeId,
                        initialDate: initialDate,
                        scheduleId: scheduleId,
                        onSuccess: onSuccess,
                        scheduledDates: scheduledDates,
                      ),
                    );
                  },
                  child: const Text('Show Dialog'),
                );
              },
            ),
          ),
        ),
      );
    }

    testWidgets('successful reschedule flow works correctly', (tester) async {
      bool onSuccessCalled = false;
      await tester.pumpWidget(createTestWidget(
        scheduleId: 'custom-schedule',
        onSuccess: () => onSuccessCalled = true,
      ));

      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Change scheduled date'), findsOneWidget);
      await tester.tap(find.text(newDate.day.toString()));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('reschedule_dialog-change-date-button')));
      await tester.pumpAndSettle();

      verify(() => mockService.scheduleJokeToDate(
            jokeId: jokeId,
            date: any(named: 'date', that: predicate((d) => d is DateTime && d.day == newDate.day)),
            scheduleId: 'custom-schedule',
          )).called(1);
      expect(onSuccessCalled, isTrue);
      expect(find.text('Change scheduled date'), findsNothing);
    });

    testWidgets('uses default schedule ID when none is provided', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('reschedule_dialog-change-date-button')));
      await tester.pumpAndSettle();

      verify(() => mockService.scheduleJokeToDate(
            jokeId: jokeId,
            date: any(named: 'date', that: predicate((d) => d is DateTime && d.day == initialDate.day)),
            scheduleId: JokeConstants.defaultJokeScheduleId,
          )).called(1);
    });

    testWidgets('handles service errors gracefully', (tester) async {
      when(() => mockService.scheduleJokeToDate(
            jokeId: any(named: 'jokeId'),
            date: any(named: 'date'),
            scheduleId: any(named: 'scheduleId'),
          )).thenThrow(Exception('Service error'));

      await tester.pumpWidget(createTestWidget());
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('reschedule_dialog-change-date-button')));
      await tester.pumpAndSettle();

      expect(find.text('Failed to reschedule joke: Exception: Service error'), findsOneWidget);
      expect(find.text('Change scheduled date'), findsOneWidget);
    });

    testWidgets('closes dialog on cancel without calling service', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Change scheduled date'), findsNothing);
      verifyNever(() => mockService.scheduleJokeToDate(
          jokeId: any(named: 'jokeId'),
          date: any(named: 'date'),
          scheduleId: any(named: 'scheduleId')));
    });

    testWidgets('disables scheduled dates in the calendar', (tester) async {
      final disabledDate = DateTime.now().add(const Duration(days: 5));
      await tester.pumpWidget(createTestWidget(scheduledDates: [disabledDate]));
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      final calendar = tester.widget<CalendarDatePicker>(find.byType(CalendarDatePicker));
      expect(calendar.selectableDayPredicate!(disabledDate), isFalse);
      expect(calendar.selectableDayPredicate!(disabledDate.add(const Duration(days: 1))), isTrue);
    });
  });
}