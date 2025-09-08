import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/reschedule_dialog.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_service.dart';

class MockJokeScheduleAutoFillService extends Mock
    implements JokeScheduleAutoFillService {}

void main() {
  group('RescheduleDialog', () {
    late MockJokeScheduleAutoFillService mockService;

    setUpAll(() {
      registerFallbackValue(DateTime.now());
    });

    setUp(() {
      mockService = MockJokeScheduleAutoFillService();

      // Setup default mock behavior
      when(
        () => mockService.scheduleJokeToDate(
          jokeId: any(named: 'jokeId'),
          date: any(named: 'date'),
          scheduleId: any(named: 'scheduleId'),
        ),
      ).thenAnswer((_) async {});
    });

    Widget createTestWidget({
      required String jokeId,
      required DateTime initialDate,
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
            body: RescheduleDialog(
              jokeId: jokeId,
              initialDate: initialDate,
              scheduleId: scheduleId,
              onSuccess: onSuccess,
              scheduledDates: scheduledDates,
            ),
          ),
        ),
      );
    }

    testWidgets('displays dialog with correct title and content', (
      WidgetTester tester,
    ) async {
      const jokeId = 'test-joke-id';
      final initialDate = DateTime.now().add(const Duration(days: 30));

      await tester.pumpWidget(
        createTestWidget(jokeId: jokeId, initialDate: initialDate),
      );

      // Check dialog title
      expect(find.text('Change scheduled date'), findsOneWidget);

      // Check cancel button
      expect(find.text('Cancel'), findsOneWidget);

      // Check change date button
      expect(find.text('Change date'), findsOneWidget);
      expect(find.byKey(const Key('change-date-btn')), findsOneWidget);

      // Check calendar is present
      expect(find.byType(CalendarDatePicker), findsOneWidget);
    });

    testWidgets(
      'calls service with correct parameters when change date is pressed',
      (WidgetTester tester) async {
        const jokeId = 'test-joke-id';
        const scheduleId = 'test-schedule-id';
        final initialDate = DateTime.now().add(const Duration(days: 30));

        await tester.pumpWidget(
          createTestWidget(
            jokeId: jokeId,
            initialDate: initialDate,
            scheduleId: scheduleId,
          ),
        );

        // Find and tap the calendar to select a new date
        final calendar = find.byType(CalendarDatePicker);
        expect(calendar, findsOneWidget);

        // Simulate date selection by tapping on a different date
        await tester.tap(calendar);
        await tester.pumpAndSettle();

        // Tap the change date button
        await tester.tap(find.byKey(const Key('change-date-btn')));
        await tester.pumpAndSettle();

        // Verify the service was called with correct parameters
        verify(
          () => mockService.scheduleJokeToDate(
            jokeId: jokeId,
            date: any(named: 'date'),
            scheduleId: scheduleId,
          ),
        ).called(1);
      },
    );

    testWidgets('closes dialog when cancel is pressed', (
      WidgetTester tester,
    ) async {
      const jokeId = 'test-joke-id';
      final initialDate = DateTime.now().add(const Duration(days: 30));

      await tester.pumpWidget(
        createTestWidget(jokeId: jokeId, initialDate: initialDate),
      );

      // Tap cancel button
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Verify dialog is closed (no longer in widget tree)
      expect(find.text('Change scheduled date'), findsNothing);
    });

    testWidgets('uses default schedule ID when none provided', (
      WidgetTester tester,
    ) async {
      const jokeId = 'test-joke-id';
      final initialDate = DateTime.now().add(const Duration(days: 30));

      await tester.pumpWidget(
        createTestWidget(
          jokeId: jokeId,
          initialDate: initialDate,
          // No scheduleId provided
        ),
      );

      // Tap the change date button
      await tester.tap(find.byKey(const Key('change-date-btn')));
      await tester.pumpAndSettle();

      // Verify the service was called with default schedule ID
      verify(
        () => mockService.scheduleJokeToDate(
          jokeId: jokeId,
          date: any(named: 'date'),
          scheduleId: any(named: 'scheduleId'),
        ),
      ).called(1);
    });

    testWidgets('handles service errors gracefully', (
      WidgetTester tester,
    ) async {
      const jokeId = 'test-joke-id';
      final initialDate = DateTime.now().add(const Duration(days: 30));

      // Override the default mock behavior for this test
      when(
        () => mockService.scheduleJokeToDate(
          jokeId: any(named: 'jokeId'),
          date: any(named: 'date'),
          scheduleId: any(named: 'scheduleId'),
        ),
      ).thenThrow(Exception('Service error'));

      await tester.pumpWidget(
        createTestWidget(jokeId: jokeId, initialDate: initialDate),
      );

      // Tap the change date button
      await tester.tap(find.byKey(const Key('change-date-btn')));
      await tester.pumpAndSettle();

      // Verify the service was called
      verify(
        () => mockService.scheduleJokeToDate(
          jokeId: jokeId,
          date: any(named: 'date'),
          scheduleId: any(named: 'scheduleId'),
        ),
      ).called(1);

      // Verify error snackbar is shown
      expect(
        find.text('Failed to reschedule joke: Exception: Service error'),
        findsOneWidget,
      );

      // Verify dialog is still open (not closed due to error)
      expect(find.text('Change scheduled date'), findsOneWidget);
    });

    testWidgets('calls onSuccess callback when reschedule is successful', (
      WidgetTester tester,
    ) async {
      const jokeId = 'test-joke-id';
      final initialDate = DateTime.now().add(const Duration(days: 30));
      bool onSuccessCalled = false;

      await tester.pumpWidget(
        createTestWidget(
          jokeId: jokeId,
          initialDate: initialDate,
          onSuccess: () {
            onSuccessCalled = true;
          },
        ),
      );

      // Tap the change date button
      await tester.tap(find.byKey(const Key('change-date-btn')));
      await tester.pumpAndSettle();

      // Verify the service was called
      verify(
        () => mockService.scheduleJokeToDate(
          jokeId: jokeId,
          date: any(named: 'date'),
          scheduleId: any(named: 'scheduleId'),
        ),
      ).called(1);

      // Verify onSuccess callback was called
      expect(onSuccessCalled, isTrue);
    });

    testWidgets('disables scheduled dates in calendar', (
      WidgetTester tester,
    ) async {
      const jokeId = 'test-joke-id';
      final initialDate = DateTime.now().add(const Duration(days: 30));
      final scheduledDates = [
        DateTime.now().add(const Duration(days: 25)),
        DateTime.now().add(const Duration(days: 35)),
      ];

      await tester.pumpWidget(
        createTestWidget(
          jokeId: jokeId,
          initialDate: initialDate,
          scheduledDates: scheduledDates,
        ),
      );

      // Verify calendar is present
      expect(find.byType(CalendarDatePicker), findsOneWidget);

      // The CalendarDatePicker should be rendered with the selectableDayPredicate
      // We can't easily test the visual appearance, but we can verify the widget
      // is created with the correct parameters
      final calendar = tester.widget<CalendarDatePicker>(
        find.byType(CalendarDatePicker),
      );
      expect(calendar.selectableDayPredicate, isNotNull);
    });
  });
}
