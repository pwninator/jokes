import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_batch_widget.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_auto_fill_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';

class MockAutoFillNotifier extends Mock implements AutoFillNotifier {}

void main() {
  group('JokeScheduleBatchWidget', () {
    late MockAutoFillNotifier mockAutoFillNotifier;

    setUp(() {
      mockAutoFillNotifier = MockAutoFillNotifier();

      // Setup default mock behaviors
      when(
        () => mockAutoFillNotifier.isMonthProcessing(any(), any()),
      ).thenReturn(false);
      when(
        () => mockAutoFillNotifier.autoFillMonth(any(), any()),
      ).thenAnswer((_) async => true);
    });

    Widget createTestWidget({
      required Widget child,
      List<Override> overrides = const [],
    }) {
      return ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: SizedBox(
                height: 800, // Provide enough height to prevent overflow
                child: child,
              ),
            ),
          ),
        ),
      );
    }

    testWidgets('should display month name and auto fill button', (
      tester,
    ) async {
      // arrange
      final monthDate = DateTime(2024, 2);

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
            autoFillProvider.overrideWith((ref) => mockAutoFillNotifier),
          ],
          child: JokeScheduleBatchWidget(monthDate: monthDate),
        ),
      );

      // assert
      expect(find.text('February 2024'), findsOneWidget);
      expect(find.text('Auto Fill'), findsOneWidget);
      expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
    });

    testWidgets('should show loading indicator when month is processing', (
      tester,
    ) async {
      // arrange
      final monthDate = DateTime(2024, 2);

      when(
        () =>
            mockAutoFillNotifier.isMonthProcessing('test_schedule', monthDate),
      ).thenReturn(true);

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
            autoFillProvider.overrideWith((ref) => mockAutoFillNotifier),
          ],
          child: JokeScheduleBatchWidget(monthDate: monthDate),
        ),
      );

      // assert
      expect(find.byKey(const Key('auto-fill-loading')), findsOneWidget);
      expect(find.text('Auto Fill'), findsNothing);
    });

    testWidgets(
      'should show confirmation dialog when auto fill button is pressed',
      (tester) async {
        // arrange
        final monthDate = DateTime(2024, 2);

        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
              selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
              autoFillProvider.overrideWith((ref) => mockAutoFillNotifier),
            ],
            child: JokeScheduleBatchWidget(monthDate: monthDate),
          ),
        );

        // act
        await tester.tap(find.byKey(const Key('auto-fill-button')));
        await tester.pumpAndSettle();

        // assert
        expect(find.text('Auto Fill Schedule'), findsOneWidget);
        expect(
          find.byKey(const Key('auto-fill-dialog-content')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('auto-fill-cancel-button')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('auto-fill-confirm-button')),
          findsOneWidget,
        );
      },
    );

    testWidgets('should call auto fill when dialog is confirmed', (
      tester,
    ) async {
      // arrange
      final monthDate = DateTime(2024, 2);

      when(() => mockAutoFillNotifier.state).thenReturn(
        AutoFillState(
          lastResult: AutoFillResult.success(
            jokesFilled: 15,
            totalDays: 29,
            strategyUsed: 'thumbs_up',
          ),
        ),
      );

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
            autoFillProvider.overrideWith((ref) => mockAutoFillNotifier),
          ],
          child: JokeScheduleBatchWidget(monthDate: monthDate),
        ),
      );

      // act
      await tester.tap(find.byKey(const Key('auto-fill-button')));
      await tester.pumpAndSettle();

      // Confirm the dialog
      await tester.tap(find.byKey(const Key('auto-fill-confirm-button')));
      await tester.pumpAndSettle();

      // assert
      verify(
        () => mockAutoFillNotifier.autoFillMonth('test_schedule', monthDate),
      ).called(1);
    });
  });
}
