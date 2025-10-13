import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategies.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

void main() {
  group('JokeEligibilityStrategies', () {
    late List<Joke> testJokes;
    late EligibilityContext testContext;

    setUp(() {
      testJokes = [
        // Joke 1: Approved
        const Joke(
          id: 'joke1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
          state: JokeState.approved,
        ),
        // Joke 2: Not approved
        const Joke(
          id: 'joke2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
          state: JokeState.unreviewed,
        ),
        // Joke 3: Not approved
        const Joke(
          id: 'joke3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
          state: JokeState.draft,
        ),
        // Joke 4: Approved with images
        const Joke(
          id: 'joke4',
          setupText: 'Setup 4',
          punchlineText: 'Punchline 4',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          state: JokeState.approved,
        ),
        // Joke 5: Approved but already scheduled in batch
        const Joke(
          id: 'joke5',
          setupText: 'Setup 5',
          punchlineText: 'Punchline 5',
          state: JokeState.approved,
        ),
      ];

      // Create a batch with joke5 already scheduled
      final existingBatch = JokeScheduleBatch(
        id: 'test_schedule_2024_01',
        scheduleId: 'test_schedule',
        year: 2024,
        month: 1,
        jokes: {'01': testJokes[4]}, // joke5 is already scheduled
      );

      testContext = EligibilityContext(
        scheduleId: 'test_schedule',
        existingBatches: [existingBatch],
        targetMonth: DateTime(2024, 2), // Different month
      );
    });

    group('ApprovedStrategy', () {
      test(
        'should select jokes with state APPROVED and exclude already scheduled',
        () async {
          // arrange
          const strategy = ApprovedStrategy();

          // act
          final result = await strategy.getEligibleJokes(
            testJokes,
            testContext,
          );

          // assert
          expect(result.length, equals(2)); // joke1 and joke4 are approved
          expect(result.map((j) => j.id), containsAll(['joke1', 'joke4']));
          expect(
            result.map((j) => j.id),
            isNot(contains('joke2')),
          ); // not approved
          expect(
            result.map((j) => j.id),
            isNot(contains('joke3')),
          ); // not approved
          expect(
            result.map((j) => j.id),
            isNot(contains('joke5')),
          ); // already scheduled
        },
      );

      test('should exclude already scheduled jokes', () async {
        // arrange
        const strategy = ApprovedStrategy();

        // Create context where joke1 is already scheduled
        final contextWithScheduledJoke = EligibilityContext(
          scheduleId: 'test_schedule',
          existingBatches: [
            JokeScheduleBatch(
              id: 'test_schedule_2024_03',
              scheduleId: 'test_schedule',
              year: 2024,
              month: 3,
              jokes: {'15': testJokes[0]}, // joke1 is scheduled
            ),
          ],
          targetMonth: DateTime(2024, 2),
        );

        // act
        final result = await strategy.getEligibleJokes(
          testJokes,
          contextWithScheduledJoke,
        );

        // assert
        expect(result.map((j) => j.id), isNot(contains('joke1')));
        expect(result.map((j) => j.id), contains('joke4')); // Still eligible
      });

      test('should have correct name and description', () {
        const strategy = ApprovedStrategy();
        expect(strategy.name, equals('approved'));
        expect(strategy.description, equals('Jokes with state APPROVED'));
      });
    });

    group('RuleBasedStrategy', () {
      test('should use custom name and description', () {
        final strategy = RuleBasedStrategy(
          rules: const [HasImagesRule()],
          customName: 'custom_strategy',
          customDescription: 'Custom description',
        );

        expect(strategy.name, equals('custom_strategy'));
        expect(strategy.description, equals('Custom description'));
      });
    });

    group('Individual Rules', () {
      group('HasImagesRule', () {
        test('should require both images', () {
          const rule = HasImagesRule();

          expect(
            rule.evaluate(testJokes[0], testContext),
            isFalse,
          ); // No images
          expect(
            rule.evaluate(testJokes[3], testContext),
            isTrue,
          ); // Has both images
        });

        test('should reject empty image URLs', () {
          const rule = HasImagesRule();
          const jokeEmptyImages = Joke(
            id: 'test',
            setupText: 'Test',
            punchlineText: 'Test',
            setupImageUrl: '',
            punchlineImageUrl: '   ', // Whitespace only
          );

          expect(rule.evaluate(jokeEmptyImages, testContext), isFalse);
        });
      });
    });

    group('JokeEligibilityHelpers', () {
      test('isJokeAlreadyScheduled should work correctly', () {
        const strategy = ApprovedStrategy();

        expect(strategy.isJokeAlreadyScheduled('joke5', testContext), isTrue);
        expect(strategy.isJokeAlreadyScheduled('joke1', testContext), isFalse);
        expect(
          strategy.isJokeAlreadyScheduled('nonexistent', testContext),
          isFalse,
        );
      });
    });
  });
}
