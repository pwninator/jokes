import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategies.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockEligibilityStrategy extends Mock implements JokeEligibilityStrategy {}

class FakeJokeScheduleBatch extends Fake implements JokeScheduleBatch {}

class FakeEligibilityContext extends Fake implements EligibilityContext {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeJokeScheduleBatch());
    registerFallbackValue(FakeEligibilityContext());
  });

  group('JokeScheduleAutoFillService', () {
    late JokeScheduleAutoFillService service;
    late MockJokeRepository mockJokeRepository;
    late MockJokeScheduleRepository mockScheduleRepository;
    late List<Joke> testJokes;

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockScheduleRepository = MockJokeScheduleRepository();

      service = JokeScheduleAutoFillService(
        jokeRepository: mockJokeRepository,
        scheduleRepository: mockScheduleRepository,
      );

      testJokes = [
        const Joke(
          id: 'joke1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
          numThumbsUp: 5,
          numThumbsDown: 2,
          state: JokeState.approved,
        ),
        const Joke(
          id: 'joke2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
          numThumbsUp: 8,
          numThumbsDown: 1,
          state: JokeState.approved,
        ),
        const Joke(
          id: 'joke3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
          numThumbsUp: 3,
          numThumbsDown: 7, // Not eligible for approved strategy
          state: JokeState.rejected,
        ),
      ];

      // Setup default mock behaviors
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(testJokes));
      when(
        () => mockJokeRepository.setJokesPublished(any()),
      ).thenAnswer((_) async {});

      when(
        () => mockScheduleRepository.watchBatchesForSchedule(any()),
      ).thenAnswer((_) => Stream.value([]));
    });

    group('autoFillMonth', () {
      test(
        'should successfully auto-fill a month with eligible jokes',
        () async {
          // arrange
          const strategy = ApprovedStrategy();
          const scheduleId = 'test_schedule';
          final monthDate = DateTime(2024, 2);

          when(
            () => mockScheduleRepository.updateBatch(any()),
          ).thenAnswer((_) async {});

          // act
          final result = await service.autoFillMonth(
            scheduleId: scheduleId,
            monthDate: monthDate,
            strategy: strategy,
          );

          // assert
          expect(result.success, isTrue);
          expect(result.jokesFilled, equals(2)); // joke1 and joke2 are eligible
          expect(result.totalDays, equals(29)); // February 2024 has 29 days
          expect(result.strategyUsed, equals('approved'));

          // Verify batch was created and saved
          verify(() => mockScheduleRepository.updateBatch(any())).called(1);
        },
      );

      test('should handle no available jokes', () async {
        // arrange
        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value([]));

        const strategy = ApprovedStrategy();
        const scheduleId = 'test_schedule';
        final monthDate = DateTime(2024, 2);

        // act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // assert
        expect(result.success, isFalse);
        expect(result.error, contains('No jokes available in the system'));
        expect(result.strategyUsed, equals('approved'));
      });

      test('should handle no eligible jokes for strategy', () async {
        // arrange
        final mockStrategy = MockEligibilityStrategy();
        when(() => mockStrategy.name).thenReturn('test_strategy');
        when(() => mockStrategy.description).thenReturn('Test Strategy');
        when(
          () => mockStrategy.getEligibleJokes(any(), any()),
        ).thenAnswer((_) async => []);

        const scheduleId = 'test_schedule';
        final monthDate = DateTime(2024, 2);

        // act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: mockStrategy,
        );

        // assert
        expect(result.success, isFalse);
        expect(
          result.error,
          contains('No jokes meet the eligibility criteria'),
        );
        expect(result.strategyUsed, equals('test_strategy'));
      });

      test('should preserve existing jokes when not replacing', () async {
        // arrange
        const strategy = ApprovedStrategy();
        const scheduleId = 'test_schedule';
        final monthDate = DateTime(2024, 2);

        // Setup existing batch with some jokes
        final existingBatch = JokeScheduleBatch(
          id: 'test_schedule_2024_02',
          scheduleId: scheduleId,
          year: 2024,
          month: 2,
          jokes: {
            '01': testJokes[0], // joke1 already scheduled on day 1
          },
        );

        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([existingBatch]));

        when(
          () => mockScheduleRepository.updateBatch(any()),
        ).thenAnswer((_) async {});

        // act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
          replaceExisting: false,
        );

        // assert
        expect(result.success, isTrue);
        expect(
          result.jokesFilled,
          greaterThan(1),
        ); // Should include existing + new jokes

        // Verify the saved batch contains the existing joke
        final capturedBatch =
            verify(
                  () => mockScheduleRepository.updateBatch(captureAny()),
                ).captured.first
                as JokeScheduleBatch;
        expect(capturedBatch.jokes['01']?.id, equals('joke1'));
      });

      test(
        'should generate warnings when insufficient jokes available',
        () async {
          // arrange
          const strategy = ApprovedStrategy();
          const scheduleId = 'test_schedule';
          final monthDate = DateTime(2024, 2); // 29 days

          // Only provide 1 eligible joke for 29 days
          when(
            () => mockJokeRepository.getJokes(),
          ).thenAnswer((_) => Stream.value([testJokes[0]])); // Only joke1

          when(
            () => mockScheduleRepository.updateBatch(any()),
          ).thenAnswer((_) async {});

          // act
          final result = await service.autoFillMonth(
            scheduleId: scheduleId,
            monthDate: monthDate,
            strategy: strategy,
          );

          // assert
          expect(result.success, isTrue);
          expect(result.jokesFilled, equals(1));
          expect(result.warnings, isNotEmpty);
          expect(result.warnings.first, contains('Could not fill 28 days'));
        },
      );

      test('should handle repository errors gracefully', () async {
        // arrange
        when(
          () => mockJokeRepository.getJokes(),
        ).thenThrow(Exception('Database error'));

        const strategy = ApprovedStrategy();
        const scheduleId = 'test_schedule';
        final monthDate = DateTime(2024, 2);

        // act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // assert
        expect(result.success, isFalse);
        expect(result.error, contains('Auto-fill failed'));
        expect(result.strategyUsed, equals('approved'));
      });
    });

    group('AutoFillResult', () {
      test('should calculate completion percentage correctly', () {
        final result = AutoFillResult.success(
          jokesFilled: 15,
          totalDays: 30,
          strategyUsed: 'test',
        );

        expect(result.completionPercentage, equals(50.0));
      });

      test('should handle zero total days', () {
        final result = AutoFillResult.success(
          jokesFilled: 5,
          totalDays: 0,
          strategyUsed: 'test',
        );

        expect(result.completionPercentage, equals(0.0));
      });

      test('should generate appropriate summary messages', () {
        // Complete fill
        final completeFill = AutoFillResult.success(
          jokesFilled: 30,
          totalDays: 30,
          strategyUsed: 'test',
        );
        expect(
          completeFill.summaryMessage,
          equals('Successfully filled all 30 days'),
        );

        // Partial fill
        final partialFill = AutoFillResult.success(
          jokesFilled: 15,
          totalDays: 30,
          strategyUsed: 'test',
        );
        expect(
          partialFill.summaryMessage,
          contains('Filled 15 of 30 days (50.0%)'),
        );

        // No fill
        final noFill = AutoFillResult.success(
          jokesFilled: 0,
          totalDays: 30,
          strategyUsed: 'test',
        );
        expect(noFill.summaryMessage, equals('No eligible jokes found'));

        // Error
        final errorResult = AutoFillResult.error(
          error: 'Something went wrong',
          strategyUsed: 'test',
        );
        expect(errorResult.summaryMessage, equals('Something went wrong'));
      });
    });
  });
}
