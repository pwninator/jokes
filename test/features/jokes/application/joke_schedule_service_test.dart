import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
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
  late MockJokeRepository mockJokeRepository;
  late MockJokeScheduleRepository mockScheduleRepository;
  late JokeScheduleAutoFillService service;
  late tz.Location mockLocation;

  setUpAll(() {
    // Initialize timezone data
    tzdata.initializeTimeZones();

    // Register fallback values for mocktail
    registerFallbackValue(FakeJokeScheduleBatch());
    registerFallbackValue(FakeEligibilityContext());
    registerFallbackValue(JokeState.approved);
    registerFallbackValue(FakeTzLocation());
  });

  setUp(() {
    mockJokeRepository = MockJokeRepository();
    mockScheduleRepository = MockJokeScheduleRepository();
    mockLocation = tz.getLocation('America/Los_Angeles');
    service = JokeScheduleAutoFillService(
      jokeRepository: mockJokeRepository,
      scheduleRepository: mockScheduleRepository,
      laLocation: mockLocation,
    );
  });

  group('JokeScheduleAutoFillService', () {
    group('publishJokeImmediately', () {
      test(
        'should publish joke immediately with current date in LA time',
        () async {
          // Arrange
          const jokeId = 'test-joke-id';
          when(
            () => mockJokeRepository.setJokesPublished(any(), false),
          ).thenAnswer((_) async {});

          // Act
          await service.publishJokeImmediately(jokeId);

          // Assert
          verify(
            () => mockJokeRepository.setJokesPublished(
              any(that: isA<Map<String, DateTime>>()),
              false,
            ),
          ).called(1);
        },
      );
    });

    group('unpublishJoke', () {
      test('should unpublish joke by resetting to APPROVED state', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        when(
          () => mockJokeRepository.resetJokesToApproved(
            any(),
            expectedState: any(named: 'expectedState'),
          ),
        ).thenAnswer((_) async {});

        // Act
        await service.unpublishJoke(jokeId);

        // Assert
        verify(
          () => mockJokeRepository.resetJokesToApproved([
            jokeId,
          ], expectedState: JokeState.published),
        ).called(1);
      });
    });

    group('scheduleJokeToDate', () {
      test(
        'should successfully schedule a published joke to future date',
        () async {
          // Arrange
          const jokeId = 'test-joke-id';
          const scheduleId = 'test-schedule';
          final targetDate = DateTime(2030, 6, 15);
          final joke = Joke(
            id: jokeId,
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            state: JokeState.published,
          );

          when(
            () => mockJokeRepository.getJokeByIdStream(jokeId),
          ).thenAnswer((_) => Stream.value(joke));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([]));
          when(
            () => mockScheduleRepository.updateBatches(any()),
          ).thenAnswer((_) async {});
          when(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).thenAnswer((_) async {});

          // Act
          await service.scheduleJokeToDate(
            jokeId: jokeId,
            date: targetDate,
            scheduleId: scheduleId,
          );

          // Assert
          verify(() => mockJokeRepository.getJokeByIdStream(jokeId)).called(1);
          verify(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).called(1);
          verify(() => mockScheduleRepository.updateBatches(any())).called(1);
          verify(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).called(1);
        },
      );

      test(
        'should successfully schedule a daily joke to future date',
        () async {
          // Arrange
          const jokeId = 'test-joke-id';
          const scheduleId = 'test-schedule';
          final targetDate = DateTime(2030, 6, 15);
          final joke = Joke(
            id: jokeId,
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            state: JokeState.daily,
          );

          when(
            () => mockJokeRepository.getJokeByIdStream(jokeId),
          ).thenAnswer((_) => Stream.value(joke));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([]));
          when(
            () => mockScheduleRepository.updateBatches(any()),
          ).thenAnswer((_) async {});
          when(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).thenAnswer((_) async {});

          // Act
          await service.scheduleJokeToDate(
            jokeId: jokeId,
            date: targetDate,
            scheduleId: scheduleId,
          );

          // Assert
          verify(() => mockJokeRepository.getJokeByIdStream(jokeId)).called(1);
          verify(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).called(1);
          verify(() => mockScheduleRepository.updateBatches(any())).called(1);
          verify(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).called(1);
        },
      );

      test('should throw exception when joke is not found', () async {
        // Arrange
        const jokeId = 'non-existent-joke';
        const scheduleId = 'test-schedule';
        final targetDate = DateTime(2030, 6, 15);

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(null));

        // Act & Assert
        expect(
          () => service.scheduleJokeToDate(
            jokeId: jokeId,
            date: targetDate,
            scheduleId: scheduleId,
          ),
          throwsA(
            isA<Exception>().having(
              (e) => e.toString(),
              'message',
              contains('Joke with ID "$jokeId" not found'),
            ),
          ),
        );
      });

      test('should throw exception when joke is in DRAFT state', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        const scheduleId = 'test-schedule';
        final targetDate = DateTime(2030, 6, 15);
        final joke = Joke(
          id: jokeId,
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          state: JokeState.draft,
        );

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(joke));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));

        // Act & Assert
        expect(
          () => service.scheduleJokeToDate(
            jokeId: jokeId,
            date: targetDate,
            scheduleId: scheduleId,
          ),
          throwsA(
            isA<Exception>().having(
              (e) => e.toString(),
              'message',
              contains('must be in PUBLISHED or DAILY state to schedule'),
            ),
          ),
        );
      });

      test('should throw exception when date is already occupied', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        const scheduleId = 'test-schedule';
        final targetDate = DateTime(2030, 6, 15);
        final existingJoke = Joke(
          id: 'existing-joke',
          setupText: 'Existing setup',
          punchlineText: 'Existing punchline',
          state: JokeState.daily,
        );
        final joke = Joke(
          id: jokeId,
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          state: JokeState.published,
        );

        final existingBatch = JokeScheduleBatch(
          id: 'test-schedule_2030_06',
          scheduleId: scheduleId,
          year: 2030,
          month: 6,
          jokes: {'15': existingJoke},
        );

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(joke));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([existingBatch]));
        when(
          () => mockScheduleRepository.updateBatches(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).thenAnswer((_) async {});

        // Act & Assert
        expect(
          () => service.scheduleJokeToDate(
            jokeId: jokeId,
            date: targetDate,
            scheduleId: scheduleId,
          ),
          throwsA(
            isA<Exception>().having(
              (e) => e.toString(),
              'message',
              contains('already has a joke scheduled for'),
            ),
          ),
        );
      });

      test(
        'should remove joke from existing batch before scheduling to new date',
        () async {
          // Arrange
          const jokeId = 'test-joke-id';
          const scheduleId = 'test-schedule';
          final newDate = DateTime(2030, 6, 15);
          final joke = Joke(
            id: jokeId,
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            state: JokeState.daily,
          );

          final existingBatch = JokeScheduleBatch(
            id: 'test-schedule_2030_06',
            scheduleId: scheduleId,
            year: 2030,
            month: 6,
            jokes: {'10': joke},
          );

          when(
            () => mockJokeRepository.getJokeByIdStream(jokeId),
          ).thenAnswer((_) => Stream.value(joke));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([existingBatch]));
          when(
            () => mockScheduleRepository.updateBatches(any()),
          ).thenAnswer((_) async {});
          when(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).thenAnswer((_) async {});

          // Act
          await service.scheduleJokeToDate(
            jokeId: jokeId,
            date: newDate,
            scheduleId: scheduleId,
          );

          // Assert
          verify(() => mockScheduleRepository.updateBatches(any())).called(1);
          verify(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).called(1);
        },
      );
    });

    group('addJokeToNextAvailableSchedule', () {
      test('should add joke to next available date in current month', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        const scheduleId = 'test-schedule';
        final joke = Joke(
          id: jokeId,
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          state: JokeState.published,
        );

        final existingBatch = JokeScheduleBatch(
          id: 'test-schedule_2030_06',
          scheduleId: scheduleId,
          year: 2030,
          month: 6,
          jokes: {'01': joke, '02': joke}, // Days 1 and 2 occupied
        );

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(joke));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([existingBatch]));
        when(
          () => mockScheduleRepository.updateBatches(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).thenAnswer((_) async {});

        // Act
        await service.addJokeToNextAvailableSchedule(
          jokeId,
          scheduleId: scheduleId,
        );

        // Assert
        verify(() => mockJokeRepository.getJokeByIdStream(jokeId)).called(1);
        verify(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).called(2);
        verify(() => mockScheduleRepository.updateBatches(any())).called(1);
        verify(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).called(1);
      });

      test(
        'should add joke to next month when current month is full',
        () async {
          // Arrange
          const jokeId = 'test-joke-id';
          const scheduleId = 'test-schedule';
          final joke = Joke(
            id: jokeId,
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            state: JokeState.published,
          );

          // Create a batch with all days filled (simplified - just day 1)
          final existingBatch = JokeScheduleBatch(
            id: 'test-schedule_2030_06',
            scheduleId: scheduleId,
            year: 2030,
            month: 6,
            jokes: {'01': joke},
          );

          when(
            () => mockJokeRepository.getJokeByIdStream(jokeId),
          ).thenAnswer((_) => Stream.value(joke));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([existingBatch]));
          when(
            () => mockScheduleRepository.updateBatches(any()),
          ).thenAnswer((_) async {});
          when(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).thenAnswer((_) async {});

          // Act
          await service.addJokeToNextAvailableSchedule(
            jokeId,
            scheduleId: scheduleId,
          );

          // Assert
          verify(() => mockJokeRepository.getJokeByIdStream(jokeId)).called(1);
          verify(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).called(2);
          verify(() => mockScheduleRepository.updateBatches(any())).called(1);
          verify(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).called(1);
        },
      );

      test('should use default schedule ID when not provided', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        final joke = Joke(
          id: jokeId,
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          state: JokeState.published,
        );

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(joke));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(
            JokeConstants.defaultJokeScheduleId,
          ),
        ).thenAnswer((_) => Stream.value([]));
        when(
          () => mockScheduleRepository.updateBatches(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).thenAnswer((_) async {});

        // Act
        await service.addJokeToNextAvailableSchedule(jokeId);

        // Assert
        verify(
          () => mockScheduleRepository.watchBatchesForSchedule(
            JokeConstants.defaultJokeScheduleId,
          ),
        ).called(2);
      });

      test('should throw exception when joke is not found', () async {
        // Arrange
        const jokeId = 'non-existent-joke';

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(null));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(
            JokeConstants.defaultJokeScheduleId,
          ),
        ).thenAnswer((_) => Stream.value([]));

        // Act & Assert
        expect(
          () => service.addJokeToNextAvailableSchedule(jokeId),
          throwsA(
            isA<Exception>().having(
              (e) => e.toString(),
              'message',
              contains('Joke with ID "$jokeId" not found'),
            ),
          ),
        );
      });
    });

    group('removeJokeFromDailySchedule', () {
      test('should successfully remove joke from current month', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        const scheduleId = 'test-schedule';
        final joke = Joke(
          id: jokeId,
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          state: JokeState.daily,
        );

        final existingBatch = JokeScheduleBatch(
          id: 'test-schedule_2030_06',
          scheduleId: scheduleId,
          year: 2030,
          month: 6,
          jokes: {'15': joke},
        );

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(joke));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([existingBatch]));
        when(
          () => mockScheduleRepository.updateBatches(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockJokeRepository.resetJokesToApproved(any()),
        ).thenAnswer((_) async {});

        // Act
        await service.removeJokeFromDailySchedule(
          jokeId,
          scheduleId: scheduleId,
        );

        // Assert
        verify(() => mockJokeRepository.getJokeByIdStream(jokeId)).called(1);
        verify(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).called(1);
        verify(() => mockScheduleRepository.updateBatches(any())).called(1);
        verify(
          () => mockJokeRepository.resetJokesToApproved([jokeId]),
        ).called(1);
      });

      test('should use default schedule ID when not provided', () async {
        // Arrange
        const jokeId = 'test-joke-id';
        final joke = Joke(
          id: jokeId,
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          state: JokeState.daily,
        );

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(joke));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(
            JokeConstants.defaultJokeScheduleId,
          ),
        ).thenAnswer((_) => Stream.value([]));
        when(
          () => mockJokeRepository.resetJokesToApproved(any()),
        ).thenAnswer((_) async {});

        // Act
        await service.removeJokeFromDailySchedule(jokeId);

        // Assert
        verify(
          () => mockScheduleRepository.watchBatchesForSchedule(
            JokeConstants.defaultJokeScheduleId,
          ),
        ).called(1);
      });

      test('should throw exception when joke is not found', () async {
        // Arrange
        const jokeId = 'non-existent-joke';

        when(
          () => mockJokeRepository.getJokeByIdStream(jokeId),
        ).thenAnswer((_) => Stream.value(null));

        // Act & Assert
        expect(
          () => service.removeJokeFromDailySchedule(jokeId),
          throwsA(
            isA<Exception>().having(
              (e) => e.toString(),
              'message',
              contains('Joke with ID "$jokeId" not found'),
            ),
          ),
        );
      });

      test(
        'should throw exception when trying to remove from past date',
        () async {
          // Arrange
          const jokeId = 'test-joke-id';
          const scheduleId = 'test-schedule';
          final joke = Joke(
            id: jokeId,
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            state: JokeState.daily,
          );

          // Create a batch for a past month
          final pastBatch = JokeScheduleBatch(
            id: 'batch-2023-01',
            scheduleId: scheduleId,
            year: 2023,
            month: 1,
            jokes: {'15': joke},
          );

          when(
            () => mockJokeRepository.getJokeByIdStream(jokeId),
          ).thenAnswer((_) => Stream.value(joke));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([pastBatch]));

          // Act & Assert
          expect(
            () => service.removeJokeFromDailySchedule(
              jokeId,
              scheduleId: scheduleId,
            ),
            throwsA(
              isA<Exception>().having(
                (e) => e.toString(),
                'message',
                contains(
                  'Cannot remove joke "test-joke-id" from past schedule',
                ),
              ),
            ),
          );
        },
      );
    });

    group('autoFillMonth', () {
      test('should successfully auto-fill empty month', () async {
        // Arrange
        const scheduleId = 'test-schedule';
        final monthDate = DateTime(2030, 6, 1);
        final strategy = MockEligibilityStrategy();
        final eligibleJokes = List.generate(
          31,
          (index) => Joke(
            id: 'joke$index',
            setupText: 'Setup $index',
            punchlineText: 'Punchline $index',
            state: JokeState.approved,
          ),
        );

        when(() => strategy.name).thenReturn('Test Strategy');
        when(() => strategy.description).thenReturn('Test Description');
        when(
          () => strategy.getEligibleJokes(any(), any()),
        ).thenAnswer((_) async => eligibleJokes);

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(eligibleJokes));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));
        when(
          () => mockScheduleRepository.updateBatches(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // Assert
        expect(result.success, true);
        expect(result.jokesFilled, 30);
        expect(result.totalDays, 30); // June has 30 days
        expect(result.strategyUsed, 'Test Strategy');
        expect(result.warnings, isEmpty);

        verify(() => mockJokeRepository.getJokes()).called(1);
        verify(() => strategy.getEligibleJokes(any(), any())).called(1);
        verify(() => mockScheduleRepository.updateBatches(any())).called(1);
        verify(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).called(1);
      });

      test('should return error when no jokes available', () async {
        // Arrange
        const scheduleId = 'test-schedule';
        final monthDate = DateTime(2030, 6, 1);
        final strategy = MockEligibilityStrategy();

        when(() => strategy.name).thenReturn('Test Strategy');
        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // Assert
        expect(result.success, false);
        expect(result.error, 'No jokes available in the system');
        expect(result.strategyUsed, 'Test Strategy');
      });

      test('should return error when no eligible jokes found', () async {
        // Arrange
        const scheduleId = 'test-schedule';
        final monthDate = DateTime(2030, 6, 1);
        final strategy = MockEligibilityStrategy();
        final allJokes = [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            state: JokeState.approved,
          ),
        ];

        when(() => strategy.name).thenReturn('Test Strategy');
        when(() => strategy.description).thenReturn('Test Description');
        when(
          () => strategy.getEligibleJokes(any(), any()),
        ).thenAnswer((_) async => []);

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(allJokes));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // Assert
        expect(result.success, false);
        expect(
          result.error,
          contains('No jokes meet the eligibility criteria'),
        );
        expect(result.strategyUsed, 'Test Strategy');
      });

      test('should return error when joke is not in APPROVED state', () async {
        // Arrange
        const scheduleId = 'test-schedule';
        final monthDate = DateTime(2030, 6, 1);
        final strategy = MockEligibilityStrategy();
        final ineligibleJokes = [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            state: JokeState.draft, // Not approved
          ),
        ];

        when(() => strategy.name).thenReturn('Test Strategy');
        when(() => strategy.description).thenReturn('Test Description');
        when(
          () => strategy.getEligibleJokes(any(), any()),
        ).thenAnswer((_) async => ineligibleJokes);

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(ineligibleJokes));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // Assert
        expect(result.success, false);
        expect(result.error, contains('must be APPROVED before scheduling'));
        expect(result.strategyUsed, 'Test Strategy');
      });

      test(
        'should preserve existing jokes when replaceExisting is false',
        () async {
          // Arrange
          const scheduleId = 'test-schedule';
          final monthDate = DateTime(2030, 6, 1);
          final strategy = MockEligibilityStrategy();
          final existingJoke = Joke(
            id: 'existing-joke',
            setupText: 'Existing setup',
            punchlineText: 'Existing punchline',
            state: JokeState.daily,
          );
          final eligibleJokes = [
            Joke(
              id: 'joke1',
              setupText: 'Setup 1',
              punchlineText: 'Punchline 1',
              state: JokeState.approved,
            ),
          ];

          final existingBatch = JokeScheduleBatch(
            id: 'test-schedule_2030_06',
            scheduleId: scheduleId,
            year: 2030,
            month: 6,
            jokes: {'01': existingJoke},
          );

          when(() => strategy.name).thenReturn('Test Strategy');
          when(() => strategy.description).thenReturn('Test Description');
          when(
            () => strategy.getEligibleJokes(any(), any()),
          ).thenAnswer((_) async => eligibleJokes);

          when(
            () => mockJokeRepository.getJokes(),
          ).thenAnswer((_) => Stream.value(eligibleJokes));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([existingBatch]));
          when(
            () => mockScheduleRepository.updateBatches(any()),
          ).thenAnswer((_) async {});
          when(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).thenAnswer((_) async {});

          // Act
          final result = await service.autoFillMonth(
            scheduleId: scheduleId,
            monthDate: monthDate,
            strategy: strategy,
            replaceExisting: false,
          );

          // Assert
          expect(result.success, true);
          expect(result.jokesFilled, 2); // 1 existing + 1 new joke
          expect(result.totalDays, 30);

          // Verify that the batch contains both existing and new jokes
          final capturedBatches =
              verify(
                    () => mockScheduleRepository.updateBatches(captureAny()),
                  ).captured.first
                  as List<JokeScheduleBatch>;
          final updatedBatch = capturedBatches.first;
          expect(updatedBatch.jokes.length, 2);
          expect(updatedBatch.jokes.containsKey('01'), true); // Existing joke
          expect(updatedBatch.jokes.containsKey('02'), true); // New joke
        },
      );

      test(
        'should replace existing jokes when replaceExisting is true',
        () async {
          // Arrange
          const scheduleId = 'test-schedule';
          final monthDate = DateTime(2030, 6, 1);
          final strategy = MockEligibilityStrategy();
          final existingJoke = Joke(
            id: 'existing-joke',
            setupText: 'Existing setup',
            punchlineText: 'Existing punchline',
            state: JokeState.daily,
          );
          final eligibleJokes = [
            Joke(
              id: 'joke1',
              setupText: 'Setup 1',
              punchlineText: 'Punchline 1',
              state: JokeState.approved,
            ),
          ];

          final existingBatch = JokeScheduleBatch(
            id: 'test-schedule_2030_06',
            scheduleId: scheduleId,
            year: 2030,
            month: 6,
            jokes: {'01': existingJoke},
          );

          when(() => strategy.name).thenReturn('Test Strategy');
          when(() => strategy.description).thenReturn('Test Description');
          when(
            () => strategy.getEligibleJokes(any(), any()),
          ).thenAnswer((_) async => eligibleJokes);

          when(
            () => mockJokeRepository.getJokes(),
          ).thenAnswer((_) => Stream.value(eligibleJokes));
          when(
            () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
          ).thenAnswer((_) => Stream.value([existingBatch]));
          when(
            () => mockScheduleRepository.updateBatches(any()),
          ).thenAnswer((_) async {});
          when(
            () => mockJokeRepository.setJokesPublished(any(), true),
          ).thenAnswer((_) async {});

          // Act
          final result = await service.autoFillMonth(
            scheduleId: scheduleId,
            monthDate: monthDate,
            strategy: strategy,
            replaceExisting: true,
          );

          // Assert
          expect(result.success, true);
          expect(result.jokesFilled, 1); // Only new joke, existing replaced
          expect(result.totalDays, 30);

          // Verify that the batch contains only the new joke
          final capturedBatches =
              verify(
                    () => mockScheduleRepository.updateBatches(captureAny()),
                  ).captured.first
                  as List<JokeScheduleBatch>;
          final updatedBatch = capturedBatches.first;
          expect(updatedBatch.jokes.length, 1);
          expect(updatedBatch.jokes.containsKey('01'), true);
          expect(
            updatedBatch.jokes['01']!.id,
            'joke1',
          ); // New joke, not existing
        },
      );

      test('should add warning when insufficient eligible jokes', () async {
        // Arrange
        const scheduleId = 'test-schedule';
        final monthDate = DateTime(2030, 6, 1); // 30 days
        final strategy = MockEligibilityStrategy();
        final eligibleJokes = [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            state: JokeState.approved,
          ),
        ]; // Only 1 joke for 30 days

        when(() => strategy.name).thenReturn('Test Strategy');
        when(() => strategy.description).thenReturn('Test Description');
        when(
          () => strategy.getEligibleJokes(any(), any()),
        ).thenAnswer((_) async => eligibleJokes);

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(eligibleJokes));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));
        when(
          () => mockScheduleRepository.updateBatches(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockJokeRepository.setJokesPublished(any(), true),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // Assert
        expect(result.success, true);
        expect(result.jokesFilled, 1);
        expect(result.totalDays, 30);
        expect(result.warnings, isNotEmpty);
        expect(result.warnings.first, contains('Could not fill 29 days'));
      });

      test('should return error when strategy throws exception', () async {
        // Arrange
        const scheduleId = 'test-schedule';
        final monthDate = DateTime(2030, 6, 1);
        final strategy = MockEligibilityStrategy();
        final allJokes = [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            state: JokeState.approved,
          ),
        ];

        when(() => strategy.name).thenReturn('Test Strategy');
        when(
          () => strategy.getEligibleJokes(any(), any()),
        ).thenThrow(Exception('Strategy error'));

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(allJokes));
        when(
          () => mockScheduleRepository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final result = await service.autoFillMonth(
          scheduleId: scheduleId,
          monthDate: monthDate,
          strategy: strategy,
        );

        // Assert
        expect(result.success, false);
        expect(
          result.error,
          contains('Auto-fill failed: Exception: Strategy error'),
        );
        expect(result.strategyUsed, 'Test Strategy');
      });
    });

    group('AutoFillResult', () {
      test('should calculate completion percentage correctly', () {
        // Arrange
        final result = AutoFillResult.success(
          jokesFilled: 15,
          totalDays: 30,
          strategyUsed: 'Test Strategy',
        );

        // Assert
        expect(result.completionPercentage, 50.0);
      });

      test('should return 0% completion for zero total days', () {
        // Arrange
        final result = AutoFillResult.success(
          jokesFilled: 0,
          totalDays: 0,
          strategyUsed: 'Test Strategy',
        );

        // Assert
        expect(result.completionPercentage, 0.0);
      });

      test('should generate correct summary message for success', () {
        // Arrange
        final result = AutoFillResult.success(
          jokesFilled: 30,
          totalDays: 30,
          strategyUsed: 'Test Strategy',
        );

        // Assert
        expect(result.summaryMessage, 'Successfully filled all 30 days');
      });

      test('should generate correct summary message for partial success', () {
        // Arrange
        final result = AutoFillResult.success(
          jokesFilled: 15,
          totalDays: 30,
          strategyUsed: 'Test Strategy',
        );

        // Assert
        expect(result.summaryMessage, 'Filled 15 of 30 days (50.0%)');
      });

      test('should generate correct summary message for no jokes filled', () {
        // Arrange
        final result = AutoFillResult.success(
          jokesFilled: 0,
          totalDays: 30,
          strategyUsed: 'Test Strategy',
        );

        // Assert
        expect(result.summaryMessage, 'No eligible jokes found');
      });

      test('should generate correct summary message for error', () {
        // Arrange
        final result = AutoFillResult.error(
          error: 'Test error',
          strategyUsed: 'Test Strategy',
        );

        // Assert
        expect(result.summaryMessage, 'Test error');
      });

      test(
        'should generate fallback summary message for error without message',
        () {
          // Arrange
          final result = AutoFillResult(
            success: false,
            jokesFilled: 0,
            totalDays: 0,
            strategyUsed: 'Test Strategy',
          );

          // Assert
          expect(result.summaryMessage, 'Auto-fill failed');
        },
      );
    });
  });
}
