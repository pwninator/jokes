import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/presentation/calendar_grid_widget.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

void main() {
  group('CalendarGridWidget', () {
    testWidgets('highlights today\'s date with blue border in current month', (
      tester,
    ) async {
      // Get today's date to build test around it
      final now = DateTime.now();
      final currentMonth = DateTime(now.year, now.month);

      // Create a batch with a joke for today (to test that today highlighting works regardless of joke presence)
      final todayKey = now.day.toString().padLeft(2, '0');
      final batch = JokeScheduleBatch(
        id: 'test-batch',
        scheduleId: 'test-schedule',
        year: now.year,
        month: now.month,
        jokes: {
          todayKey: Joke(
            id: 'joke-today',
            setupText: 'Today\'s setup',
            punchlineText: 'Today\'s punchline',
            setupImageUrl: 'setup.jpg',
            punchlineImageUrl: 'punchline.jpg',
          ),
        },
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: SizedBox(
                  height: 800, // Give enough height for the calendar
                  child: CalendarGridWidget(
                    batch: batch,
                    monthDate: currentMonth,
                  ),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Find today's day text in the calendar
      final todayText = find.text(now.day.toString());
      expect(todayText, findsOneWidget);

      // Find the container that wraps today's text by traversing up the widget tree
      final todayTextWidget = tester.element(todayText);
      final containerElement =
          todayTextWidget.findAncestorWidgetOfExactType<Container>();
      expect(
        containerElement,
        isNotNull,
        reason: 'Today\'s text should be wrapped in a Container',
      );

      // Check that today's container has the blue thick border
      final decoration = containerElement!.decoration as BoxDecoration?;
      expect(decoration?.border, isNotNull);
      final border = decoration!.border as Border;
      expect(
        border.top.color,
        Colors.blue,
        reason: 'Today\'s cell should have a blue border',
      );
      expect(
        border.top.width,
        3.0,
        reason: 'Today\'s cell should have a thick (3px) border',
      );

      // Check a few other day numbers to ensure they don't have blue thick borders
      for (int day = 1; day <= 5; day++) {
        if (day != now.day) {
          final dayTextFinder = find.text(day.toString());
          if (dayTextFinder.hasFound) {
            final dayTextElement = tester.element(dayTextFinder);
            final dayContainer =
                dayTextElement.findAncestorWidgetOfExactType<Container>();
            if (dayContainer != null) {
              final dayDecoration = dayContainer.decoration as BoxDecoration?;
              if (dayDecoration?.border != null) {
                final dayBorder = dayDecoration!.border as Border;
                final hasBlueThickBorder =
                    dayBorder.top.color == Colors.blue &&
                    dayBorder.top.width == 3.0;
                expect(
                  hasBlueThickBorder,
                  false,
                  reason:
                      'Day $day should not have a blue thick border, only today (${now.day}) should',
                );
              }
            }
          }
        }
      }
    });

    testWidgets('does not highlight any date in a different month', (
      tester,
    ) async {
      // Get today's date and create a batch for a different month
      final now = DateTime.now();
      final differentMonth = DateTime(
        now.year,
        now.month == 12 ? 1 : now.month + 1,
      );

      // Create a batch for the different month
      final batch = JokeScheduleBatch(
        id: 'test-batch',
        scheduleId: 'test-schedule',
        year: differentMonth.year,
        month: differentMonth.month,
        jokes: {
          '01': Joke(
            id: 'joke-1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            setupImageUrl: 'setup.jpg',
            punchlineImageUrl: 'punchline.jpg',
          ),
        },
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: SizedBox(
                  height: 800, // Give enough height for the calendar
                  child: CalendarGridWidget(
                    batch: batch,
                    monthDate: differentMonth,
                  ),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Check that no day in this different month has a blue thick border
      for (int day = 1; day <= 10; day++) {
        final dayTextFinder = find.text(day.toString());
        if (dayTextFinder.hasFound) {
          final dayTextElement = tester.element(dayTextFinder);
          final dayContainer =
              dayTextElement.findAncestorWidgetOfExactType<Container>();
          if (dayContainer != null) {
            final dayDecoration = dayContainer.decoration as BoxDecoration?;
            if (dayDecoration?.border != null) {
              final dayBorder = dayDecoration!.border as Border;
              final hasBlueThickBorder =
                  dayBorder.top.color == Colors.blue &&
                  dayBorder.top.width == 5.0;
              expect(
                hasBlueThickBorder,
                false,
                reason:
                    'Day $day in different month should not have a blue thick border since today is not in this month',
              );
            }
          }
        }
      }
    });

    testWidgets('highlights today even when no joke is scheduled', (
      tester,
    ) async {
      // Get today's date and create an empty batch (no jokes scheduled)
      final now = DateTime.now();
      final currentMonth = DateTime(now.year, now.month);

      // Create a batch with no jokes
      final batch = JokeScheduleBatch(
        id: 'test-batch',
        scheduleId: 'test-schedule',
        year: now.year,
        month: now.month,
        jokes: {}, // Empty - no jokes scheduled
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: SizedBox(
                  height: 800, // Give enough height for the calendar
                  child: CalendarGridWidget(
                    batch: batch,
                    monthDate: currentMonth,
                  ),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Find today's day text in the calendar (should be there even without a joke)
      final todayText = find.text(now.day.toString());
      expect(todayText, findsOneWidget);

      // Find the container that wraps today's text
      final todayTextWidget = tester.element(todayText);
      final containerElement =
          todayTextWidget.findAncestorWidgetOfExactType<Container>();
      expect(
        containerElement,
        isNotNull,
        reason: 'Today\'s text should be wrapped in a Container',
      );

      // Check that today's container has the blue thick border even without a joke
      final decoration = containerElement!.decoration as BoxDecoration?;
      expect(decoration?.border, isNotNull);
      final border = decoration!.border as Border;
      expect(
        border.top.color,
        Colors.blue,
        reason:
            'Today\'s cell should have a blue border even when no joke is scheduled',
      );
      expect(
        border.top.width,
        3.0,
        reason:
            'Today\'s cell should have a thick (3px) border even when no joke is scheduled',
      );
    });
  });
}
