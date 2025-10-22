import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_scheduler_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';

void main() {
  group('JokeSchedulerScreen', () {
    testWidgets('displays empty state when no schedules available', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeSchedulesProvider.overrideWith(
              (ref) => Stream.value(<JokeSchedule>[]),
            ),
          ],
          child: const MaterialApp(home: JokeSchedulerScreen()),
        ),
      );

      // Wait for build to complete
      await tester.pumpAndSettle();

      // Should show empty state
      expect(find.text('No schedule selected'), findsOneWidget);
      expect(find.text('Create a schedule to get started'), findsOneWidget);
      expect(find.byIcon(Icons.schedule_outlined), findsOneWidget);
    });

    testWidgets('displays schedule dropdown when schedules are available', (
      tester,
    ) async {
      const testSchedules = [
        JokeSchedule(id: 'daily', name: 'Daily Jokes'),
        JokeSchedule(id: 'weekly', name: 'Weekly Comedy'),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeSchedulesProvider.overrideWith(
              (ref) => Stream.value(testSchedules),
            ),
            selectedScheduleProvider.overrideWith(
              (ref) =>
                  null, // Start with no selection to avoid infinite loading
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: JokeSchedulerScreen())),
        ),
      );

      // Wait for build to complete
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Should show dropdown with schedules
      expect(find.text('Select Schedule'), findsOneWidget);
      expect(find.byType(DropdownButtonFormField<String>), findsOneWidget);
    });

    testWidgets('shows add schedule button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeSchedulesProvider.overrideWith(
              (ref) => Stream.value(<JokeSchedule>[]),
            ),
          ],
          child: const MaterialApp(home: JokeSchedulerScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Should show add button
      expect(find.byIcon(Icons.add), findsOneWidget);
    });
  });
}
