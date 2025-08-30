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
          numThumbsUp: 5,
          numThumbsDown: 2,
          state: JokeState.approved,
        ),
        // Joke 2: Not approved
        const Joke(
          id: 'joke2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
          numThumbsUp: 3,
          numThumbsDown: 7,
          state: JokeState.unreviewed,
        ),
        // Joke 3: Not approved
        const Joke(
          id: 'joke3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
          numThumbsUp: 0,
          numThumbsDown: 0,
          state: JokeState.draft,
        ),
        // Joke 4: Approved with images
        const Joke(
          id: 'joke4',
          setupText: 'Setup 4',
          punchlineText: 'Punchline 4',
          numThumbsUp: 10,
          numThumbsDown: 1,
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          state: JokeState.approved,
        ),
        // Joke 5: Approved but already scheduled in batch
        const Joke(
          id: 'joke5',
          setupText: 'Setup 5',
          punchlineText: 'Punchline 5',
          numThumbsUp: 8,
          numThumbsDown: 1,
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

    group('HighlyRatedStrategy', () {
      test('should select jokes meeting minimum thresholds', () async {
        // arrange
        const strategy = HighlyRatedStrategy(minThumbsUp: 5, minRatio: 2.0);

        // act
        final result = await strategy.getEligibleJokes(testJokes, testContext);

        // assert
        expect(
          result.length,
          equals(2),
        ); // joke1 (5 thumbs up, 2.5 ratio) and joke4 (10 thumbs up, 10.0 ratio) meet criteria
        expect(result.map((j) => j.id), containsAll(['joke1', 'joke4']));
      });

      test('should handle zero thumbs down correctly', () async {
        // arrange
        const strategy = HighlyRatedStrategy(minThumbsUp: 5, minRatio: 2.0);
        final jokesWithZeroDown = [
          const Joke(
            id: 'joke_zero_down',
            setupText: 'Setup',
            punchlineText: 'Punchline',
            numThumbsUp: 5,
            numThumbsDown: 0, // Zero thumbs down should pass ratio test
          ),
        ];

        // act
        final result = await strategy.getEligibleJokes(
          jokesWithZeroDown,
          testContext,
        );

        // assert
        expect(result.length, equals(1));
        expect(result.first.id, equals('joke_zero_down'));
      });

      test('should generate correct name with parameters', () {
        const strategy1 = HighlyRatedStrategy(minThumbsUp: 5, minRatio: 2.0);
        const strategy2 = HighlyRatedStrategy(minThumbsUp: 10, minRatio: 3.5);

        expect(strategy1.name, equals('highly_rated_5_2.0'));
        expect(strategy2.name, equals('highly_rated_10_3.5'));
      });
    });

    group('RuleBasedStrategy', () {
      test('should apply all rules correctly', () async {
        // arrange
        final strategy = RuleBasedStrategy(
          rules: [
            const MinThumbsUpRule(3),
            const PositiveRatioRule(),
            const HasImagesRule(),
          ],
          customName: 'test_combo',
          customDescription: 'Test combination',
        );

        // act
        final result = await strategy.getEligibleJokes(testJokes, testContext);

        // assert
        expect(
          result.length,
          equals(1),
        ); // only joke4 has images and meets criteria
        expect(result.first.id, equals('joke4'));
      });

      test('should use custom name and description', () {
        final strategy = RuleBasedStrategy(
          rules: const [MinThumbsUpRule(1)],
          customName: 'custom_strategy',
          customDescription: 'Custom description',
        );

        expect(strategy.name, equals('custom_strategy'));
        expect(strategy.description, equals('Custom description'));
      });
    });

    group('Individual Rules', () {
      group('MinThumbsUpRule', () {
        test('should evaluate thumbs up threshold correctly', () {
          const rule = MinThumbsUpRule(5);

          expect(
            rule.evaluate(testJokes[0], testContext),
            isTrue,
          ); // 5 thumbs up
          expect(
            rule.evaluate(testJokes[1], testContext),
            isFalse,
          ); // 3 thumbs up
          expect(
            rule.evaluate(testJokes[3], testContext),
            isTrue,
          ); // 10 thumbs up
        });

        test('should have correct name and description', () {
          const rule = MinThumbsUpRule(5);
          expect(rule.name, equals('min_thumbs_up_5'));
          expect(rule.description, equals('At least 5 thumbs up'));
        });
      });

      group('ThumbsRatioRule', () {
        test('should evaluate ratio correctly', () {
          const rule = ThumbsRatioRule(2.0);

          expect(
            rule.evaluate(testJokes[0], testContext),
            isTrue,
          ); // 5:2 = 2.5 > 2.0
          expect(
            rule.evaluate(testJokes[1], testContext),
            isFalse,
          ); // 3:7 < 2.0
          expect(
            rule.evaluate(testJokes[3], testContext),
            isTrue,
          ); // 10:1 > 2.0
        });

        test('should handle zero thumbs down', () {
          const rule = ThumbsRatioRule(2.0);
          const jokeZeroDown = Joke(
            id: 'test',
            setupText: 'Test',
            punchlineText: 'Test',
            numThumbsUp: 1,
            numThumbsDown: 0,
          );

          expect(rule.evaluate(jokeZeroDown, testContext), isTrue);
        });
      });

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

      group('PositiveRatioRule', () {
        test('should require more thumbs up than down', () {
          const rule = PositiveRatioRule();

          expect(rule.evaluate(testJokes[0], testContext), isTrue); // 5 > 2
          expect(rule.evaluate(testJokes[1], testContext), isFalse); // 3 < 7
          expect(rule.evaluate(testJokes[2], testContext), isFalse); // 0 = 0
        });
      });

      group('AnyThumbsUpRule', () {
        test('should require at least one thumbs up', () {
          const rule = AnyThumbsUpRule();

          expect(rule.evaluate(testJokes[0], testContext), isTrue); // 5 > 0
          expect(rule.evaluate(testJokes[1], testContext), isTrue); // 3 > 0
          expect(rule.evaluate(testJokes[2], testContext), isFalse); // 0 = 0
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
