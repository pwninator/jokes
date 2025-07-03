import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_batch_widget.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
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
            numThumbsUp: 5,
            numThumbsDown: 1,
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
  });
}
