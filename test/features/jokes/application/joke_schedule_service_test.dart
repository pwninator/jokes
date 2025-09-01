import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategies.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockEligibilityStrategy extends Mock implements JokeEligibilityStrategy {}

class FakeJokeScheduleBatch extends Fake implements JokeScheduleBatch {}

class FakeEligibilityContext extends Fake implements EligibilityContext {}

class FakeTzLocation extends Fake implements tz.Location {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeJokeScheduleBatch());
    registerFallbackValue(FakeEligibilityContext());
    registerFallbackValue(
      JokeState.approved,
    ); // Use actual enum value for fallback
    registerFallbackValue(FakeTzLocation()); // For timezone fallback
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
        () => mockJokeRepository.setJokesPublished(any(), any()),
      ).thenAnswer((_) async {});
      when(
        () =>
            mockJokeRepository.resetJokesToApproved(any(), JokeState.approved),
      ).thenAnswer((_) async {});
      when(
        () =>
            mockJokeRepository.resetJokesToApproved(any(), JokeState.published),
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

    group('unpublishJoke', () {
      test('should successfully unpublish a PUBLISHED joke', () async {
        // arrange
        const jokeId = 'published_joke';

        // act
        await service.unpublishJoke(jokeId);

        // assert
        verify(
          () => mockJokeRepository.resetJokesToApproved([
            jokeId,
          ], JokeState.published),
        ).called(1);
      });

      test('should handle repository errors gracefully', () async {
        // arrange
        const jokeId = 'published_joke';
        when(
          () => mockJokeRepository.resetJokesToApproved(
            any(),
            JokeState.published,
          ),
        ).thenThrow(Exception('Repository error'));

        // act & assert
        expect(() => service.unpublishJoke(jokeId), throwsA(isA<Exception>()));
      });
    });

    group('addJokeToNextAvailableDailySchedule', () {
      late Joke publishedJoke;
      late Joke nonPublishedJoke;

      setUp(() {
        // Initialize timezone data for tests
        tzdata.initializeTimeZones();

        publishedJoke = const Joke(
          id: 'published_joke',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          numThumbsUp: 10,
          numThumbsDown: 2,
          state: JokeState.published,
        );

        nonPublishedJoke = const Joke(
          id: 'draft_joke',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          numThumbsUp: 5,
          numThumbsDown: 1,
          state: JokeState.draft,
        );

        // Setup default mock for published joke
        when(() => mockJokeRepository.getJokeByIdStream('published_joke'))
            .thenAnswer((_) => Stream.value(publishedJoke));

        // Setup default mock for non-published joke
        when(() => mockJokeRepository.getJokeByIdStream('draft_joke'))
            .thenAnswer((_) => Stream.value(nonPublishedJoke));

        // Setup default empty batches for daily schedule
        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([]));

        // Setup batch update mock
        when(() => mockScheduleRepository.updateBatch(any()))
            .thenAnswer((_) async {});
      });

      test('should successfully add a PUBLISHED joke to next available date', () async {
        // arrange
        const jokeId = 'published_joke';

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        verify(() => mockJokeRepository.getJokeByIdStream(jokeId)).called(1);
        verify(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId)).called(1);
        verify(() => mockScheduleRepository.updateBatch(any())).called(1);
        verify(() => mockJokeRepository.setJokesPublished(any(), true)).called(1);
      });

      test('should throw exception when joke is not found', () async {
        // arrange
        const jokeId = 'nonexistent_joke';
        when(() => mockJokeRepository.getJokeByIdStream(jokeId))
            .thenAnswer((_) => Stream.value(null));

        // act & assert
        expect(
          () => service.addJokeToNextAvailableDailySchedule(jokeId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Joke with ID "nonexistent_joke" not found'),
          )),
        );
      });

      test('should throw exception when joke is not in PUBLISHED state', () async {
        // arrange
        const jokeId = 'draft_joke';

        // act & assert
        expect(
          () => service.addJokeToNextAvailableDailySchedule(jokeId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('must be in PUBLISHED state'),
          )),
        );
      });

      test('should throw exception when joke is already scheduled', () async {
        // arrange
        const jokeId = 'published_joke';
        final existingBatch = JokeScheduleBatch(
          id: 'daily_jokes_2024_01',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: 2024,
          month: 1,
          jokes: {
            '15': publishedJoke, // Joke already scheduled on Jan 15, 2024
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([existingBatch]));

        // act & assert
        expect(
          () => service.addJokeToNextAvailableDailySchedule(jokeId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('already scheduled in batch 2024-01'),
          )),
        );
      });

      test('should find next available date when some dates are taken', () async {
        // arrange
        const jokeId = 'published_joke';

        // Create a batch for current month with some dates taken
        final currentDate = DateTime.now();
        final existingBatch = JokeScheduleBatch(
          id: 'daily_jokes_${currentDate.year}_${currentDate.month.toString().padLeft(2, '0')}',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: currentDate.year,
          month: currentDate.month,
          jokes: {
            // Fill all dates up to yesterday
            for (int day = 1; day < currentDate.day; day++)
              day.toString().padLeft(2, '0'): Joke(
                id: 'existing_joke_$day',
                setupText: 'Setup',
                punchlineText: 'Punchline',
                numThumbsUp: 1,
                numThumbsDown: 0,
                state: JokeState.daily,
              ),
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([existingBatch]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should add joke to today or next available date
        final todayKey = currentDate.day.toString().padLeft(2, '0');
        expect(capturedBatch.jokes[todayKey]?.id, equals(jokeId));
      });

      test('should create new batch for next month when current month is full', () async {
        // arrange
        const jokeId = 'published_joke';

        // Create a batch for current month that is completely full
        final currentDate = DateTime.now();
        final daysInMonth = DateTime(currentDate.year, currentDate.month + 1, 0).day;

        final fullBatch = JokeScheduleBatch(
          id: 'daily_jokes_${currentDate.year}_${currentDate.month.toString().padLeft(2, '0')}',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: currentDate.year,
          month: currentDate.month,
          jokes: {
            // Fill all days of the month
            for (int day = 1; day <= daysInMonth; day++)
              day.toString().padLeft(2, '0'): Joke(
                id: 'existing_joke_$day',
                setupText: 'Setup',
                punchlineText: 'Punchline',
                numThumbsUp: 1,
                numThumbsDown: 0,
                state: JokeState.daily,
              ),
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([fullBatch]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should create batch for next month using Dart's automatic overflow
        final expectedNextDate = DateTime(currentDate.year, currentDate.month + 1, 1);

        expect(capturedBatch.year, equals(expectedNextDate.year));
        expect(capturedBatch.month, equals(expectedNextDate.month));
        expect(capturedBatch.scheduleId, equals(JokeConstants.defaultJokeScheduleId));

        // Should add joke to first day of next month
        expect(capturedBatch.jokes['01']?.id, equals(jokeId));
      });

      test('should handle December to January year transition correctly', () async {
        // arrange
        const jokeId = 'published_joke';

        // Create a batch for December 2024 that is completely full (31 days)
        final decBatch = JokeScheduleBatch(
          id: 'daily_jokes_2024_12',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: 2024,
          month: 12,
          jokes: {
            // Fill all 31 days of December
            for (int day = 1; day <= 31; day++)
              day.toString().padLeft(2, '0'): Joke(
                id: 'dec_joke_$day',
                setupText: 'Setup',
                punchlineText: 'Punchline',
                numThumbsUp: 1,
                numThumbsDown: 0,
                state: JokeState.daily,
              ),
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([decBatch]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should create batch for January 2025 (December 31st + 1 day)
        expect(capturedBatch.year, equals(2025));
        expect(capturedBatch.month, equals(1));
        expect(capturedBatch.scheduleId, equals(JokeConstants.defaultJokeScheduleId));

        // Should add joke to first day of January
        expect(capturedBatch.jokes['01']?.id, equals(jokeId));
      });

      test('should handle regular month transition without year change', () async {
        // arrange
        const jokeId = 'published_joke';

        // Create a batch for November 2024 that is completely full (30 days)
        final novBatch = JokeScheduleBatch(
          id: 'daily_jokes_2024_11',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: 2024,
          month: 11,
          jokes: {
            // Fill all 30 days of November
            for (int day = 1; day <= 30; day++)
              day.toString().padLeft(2, '0'): Joke(
                id: 'nov_joke_$day',
                setupText: 'Setup',
                punchlineText: 'Punchline',
                numThumbsUp: 1,
                numThumbsDown: 0,
                state: JokeState.daily,
              ),
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([novBatch]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should create batch for December 2024 (November 30th + 1 day)
        expect(capturedBatch.year, equals(2024));
        expect(capturedBatch.month, equals(12));
        expect(capturedBatch.scheduleId, equals(JokeConstants.defaultJokeScheduleId));

        // Should add joke to first day of December
        expect(capturedBatch.jokes['01']?.id, equals(jokeId));
      });

      test('should handle February leap year correctly', () async {
        // arrange
        const jokeId = 'published_joke';

        // Create a batch for February 2024 (leap year, 29 days)
        final febBatch = JokeScheduleBatch(
          id: 'daily_jokes_2024_02',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: 2024,
          month: 2,
          jokes: {
            // Fill all 29 days of February 2024
            for (int day = 1; day <= 29; day++)
              day.toString().padLeft(2, '0'): Joke(
                id: 'feb_joke_$day',
                setupText: 'Setup',
                punchlineText: 'Punchline',
                numThumbsUp: 1,
                numThumbsDown: 0,
                state: JokeState.daily,
              ),
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([febBatch]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should create batch for March 2024 (February 29th + 1 day)
        expect(capturedBatch.year, equals(2024));
        expect(capturedBatch.month, equals(3));
        expect(capturedBatch.scheduleId, equals(JokeConstants.defaultJokeScheduleId));

        // Should add joke to first day of March
        expect(capturedBatch.jokes['01']?.id, equals(jokeId));
      });

      test('should handle future batches correctly', () async {
        // arrange
        const jokeId = 'published_joke';
        final currentDate = DateTime.now();

        // Create batches for current and future months
        final currentBatch = JokeScheduleBatch(
          id: 'daily_jokes_${currentDate.year}_${currentDate.month.toString().padLeft(2, '0')}',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: currentDate.year,
          month: currentDate.month,
          jokes: {
            // Current month has some dates taken
            '01': const Joke(
              id: 'existing_joke_1',
              setupText: 'Setup',
              punchlineText: 'Punchline',
              numThumbsUp: 1,
              numThumbsDown: 0,
              state: JokeState.daily,
            ),
          },
        );

        final futureBatch = JokeScheduleBatch(
          id: 'daily_jokes_${currentDate.year}_${(currentDate.month + 1).toString().padLeft(2, '0')}',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: currentDate.year,
          month: currentDate.month + 1,
          jokes: {
            // Future month also has some dates taken
            '01': const Joke(
              id: 'existing_joke_2',
              setupText: 'Setup',
              punchlineText: 'Punchline',
              numThumbsUp: 1,
              numThumbsDown: 0,
              state: JokeState.daily,
            ),
          },
        );

        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([currentBatch, futureBatch]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should find available date in current month (day 2)
        expect(capturedBatch.id, equals(currentBatch.id));
        expect(capturedBatch.jokes['02']?.id, equals(jokeId));
      });

      test('should handle timezone conversion for LA timezone', () async {
        // arrange
        const jokeId = 'published_joke';

        // Use LA timezone in the service
        final laLocation = tz.getLocation('America/Los_Angeles');
        final serviceWithLA = JokeScheduleAutoFillService(
          jokeRepository: mockJokeRepository,
          scheduleRepository: mockScheduleRepository,
          laLocation: laLocation,
        );

        // act
        await serviceWithLA.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedPublishMap = verify(() => mockJokeRepository.setJokesPublished(captureAny(), true))
            .captured.first as Map<String, DateTime>;

        // Should have published with LA timezone
        expect(capturedPublishMap.containsKey(jokeId), isTrue);
        final publishDate = capturedPublishMap[jokeId]!;
        // Pacific Time can be either PST (Standard) or PDT (Daylight)
        expect(publishDate.timeZoneName, anyOf(equals('PST'), equals('PDT')));
      });

      test('should handle repository errors during batch update', () async {
        // arrange
        const jokeId = 'published_joke';
        when(() => mockScheduleRepository.updateBatch(any()))
            .thenThrow(Exception('Batch update failed'));

        // act & assert
        expect(
          () => service.addJokeToNextAvailableDailySchedule(jokeId),
          throwsA(isA<Exception>()),
        );
      });

      test('should handle repository errors during joke publishing', () async {
        // arrange
        const jokeId = 'published_joke';
        when(() => mockJokeRepository.setJokesPublished(any(), any()))
            .thenThrow(Exception('Publishing failed'));

        // act & assert
        expect(
          () => service.addJokeToNextAvailableDailySchedule(jokeId),
          throwsA(isA<Exception>()),
        );
      });

      test('should handle empty batch collection', () async {
        // arrange
        const jokeId = 'published_joke';
        when(() => mockScheduleRepository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId))
            .thenAnswer((_) => Stream.value([]));

        // act
        await service.addJokeToNextAvailableDailySchedule(jokeId);

        // assert
        final capturedBatch = verify(() => mockScheduleRepository.updateBatch(captureAny()))
            .captured.first as JokeScheduleBatch;

        // Should create batch for current month
        final currentDate = DateTime.now();
        expect(capturedBatch.year, equals(currentDate.year));
        expect(capturedBatch.month, equals(currentDate.month));
        expect(capturedBatch.scheduleId, equals(JokeConstants.defaultJokeScheduleId));

        // Should add joke to first available date (today or next available)
        final todayKey = currentDate.day.toString().padLeft(2, '0');
        expect(capturedBatch.jokes[todayKey]?.id, equals(jokeId));
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
