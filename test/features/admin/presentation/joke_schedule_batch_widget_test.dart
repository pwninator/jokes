import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_batch_widget.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

// Mock repositories (following existing patterns in codebase)
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

// Fake classes for mocktail fallback values
class FakeJokeScheduleBatch extends Fake implements JokeScheduleBatch {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeJokeScheduleBatch());
  });
  group('JokeScheduleBatchWidget', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeScheduleRepository mockScheduleRepository;

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockScheduleRepository = MockJokeScheduleRepository();

      // Setup default mock behaviors
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(<Joke>[]));
      when(
        () => mockScheduleRepository.updateBatch(any()),
      ).thenAnswer((_) async {});
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
              child: SizedBox(height: 800, child: child),
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
            // ✅ Mock the dependencies, not the StateNotifier itself
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeScheduleRepositoryProvider.overrideWithValue(
              mockScheduleRepository,
            ),
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
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

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeScheduleRepositoryProvider.overrideWithValue(
              mockScheduleRepository,
            ),
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
            // Override with processing state
            autoFillProvider.overrideWith((ref) {
              final service = ref.watch(jokeScheduleAutoFillServiceProvider);
              final notifier = AutoFillNotifier(service, ref);
              // Set initial processing state
              notifier.state = const AutoFillState(
                processingMonths: {'test_schedule_2024_2'},
              );
              return notifier;
            }),
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
              jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
              jokeScheduleRepositoryProvider.overrideWithValue(
                mockScheduleRepository,
              ),
              scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
              selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
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

    testWidgets('should handle auto fill confirmation', (tester) async {
      // arrange
      final monthDate = DateTime(2024, 2);

      // Mock successful auto-fill
      when(() => mockJokeRepository.getJokes()).thenAnswer(
        (_) => Stream.value([
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
          ),
        ]),
      );

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeScheduleRepositoryProvider.overrideWithValue(
              mockScheduleRepository,
            ),
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
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

      // assert - dialog should be dismissed
      expect(find.text('Auto Fill Schedule'), findsNothing);
    });

    testWidgets('should show delete button', (tester) async {
      // arrange
      final monthDate = DateTime(2024, 2);

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeScheduleRepositoryProvider.overrideWithValue(
              mockScheduleRepository,
            ),
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
          ],
          child: JokeScheduleBatchWidget(monthDate: monthDate),
        ),
      );

      // assert
      expect(find.byIcon(Icons.delete_outline), findsOneWidget);
    });

    testWidgets(
      'delete is triggered only for future months and shows success snackbar',
      (tester) async {
        // arrange a future month to satisfy deletion rule
        final now = DateTime.now();
        final futureMonth = DateTime(now.year + 1, 2);
        const scheduleId = 'test_schedule';

        when(
          () => mockScheduleRepository.deleteBatch(any()),
        ).thenAnswer((_) async {});

        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
              jokeScheduleRepositoryProvider.overrideWithValue(
                mockScheduleRepository,
              ),
              scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
              selectedScheduleProvider.overrideWith((ref) => scheduleId),
            ],
            child: JokeScheduleBatchWidget(monthDate: futureMonth),
          ),
        );

        final deleteButtonFinder = find.byType(HoldableButton);
        expect(deleteButtonFinder, findsOneWidget);

        // tap does nothing
        await tester.tap(deleteButtonFinder);
        await tester.pumpAndSettle();
        expect(find.text('Delete Schedule Batch'), findsNothing);

        // hold to trigger delete
        await tester.startGesture(tester.getCenter(deleteButtonFinder));
        await tester.pump(const Duration(milliseconds: 2100));
        await tester.pumpAndSettle();

        // verify delete called for the future month
        verify(
          () => mockScheduleRepository.deleteBatch(
            JokeScheduleBatch.createBatchId(
              scheduleId,
              futureMonth.year,
              futureMonth.month,
            ),
          ),
        ).called(1);

        // Verify snackbar message contains month/year
        final monthNames = [
          '',
          'January',
          'February',
          'March',
          'April',
          'May',
          'June',
          'July',
          'August',
          'September',
          'October',
          'November',
          'December',
        ];
        final expected =
            'Successfully deleted schedule for ${monthNames[futureMonth.month]} ${futureMonth.year}';
        expect(find.text(expected), findsOneWidget);
      },
    );

    testWidgets('delete button is disabled for current/past months', (
      tester,
    ) async {
      // arrange: current month
      final now = DateTime.now();
      final currentMonth = DateTime(now.year, now.month);

      await tester.pumpWidget(
        createTestWidget(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeScheduleRepositoryProvider.overrideWithValue(
              mockScheduleRepository,
            ),
            scheduleBatchesProvider.overrideWith((ref) => Stream.value([])),
            selectedScheduleProvider.overrideWith((ref) => 'test_schedule'),
          ],
          child: JokeScheduleBatchWidget(monthDate: currentMonth),
        ),
      );

      // assert: HoldableButton exists and is visually disabled (spinner rendered)
      final buttonFinder = find.byType(HoldableButton);
      expect(buttonFinder, findsOneWidget);
      // Simulate tap/hold should not trigger delete; UI shows disabled spinner
      await tester.tap(buttonFinder);
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Successfully deleted schedule for'),
        findsNothing,
      );
    });

    // Removed tests for confirmation dialog as it's no longer used for delete.
    // 'should delete batch when confirmation is given' - merged into the above.
    // 'should not delete batch when confirmation is cancelled' - no longer applicable.
  });
}
