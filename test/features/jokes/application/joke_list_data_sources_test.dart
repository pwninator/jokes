import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

class _MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

void main() {
  group('Daily Jokes Stale Data Detection', () {
    test('getCurrentDate returns normalized date', () {
      final date = getCurrentDate();
      final now = DateTime.now();
      final expected = DateTime(now.year, now.month, now.day);

      expect(date, expected);
    });

    test('dailyJokesCheckNowProvider starts at 0', () {
      final container = ProviderContainer();

      final initialValue = container.read(dailyJokesCheckNowProvider);
      expect(initialValue, 0);

      container.dispose();
    });

    test('dailyJokesCheckNowProvider can be incremented', () {
      final container = ProviderContainer();

      final initialValue = container.read(dailyJokesCheckNowProvider);
      container.read(dailyJokesCheckNowProvider.notifier).state++;
      final newValue = container.read(dailyJokesCheckNowProvider);

      expect(newValue, initialValue + 1);

      container.dispose();
    });

    test('dailyJokesLastResetDateProvider starts as null', () {
      final container = ProviderContainer();

      final initialValue = container.read(dailyJokesLastResetDateProvider);
      expect(initialValue, null);

      container.dispose();
    });

    test('dailyJokesLastResetDateProvider can store date', () {
      final container = ProviderContainer();

      final today = getCurrentDate();
      container.read(dailyJokesLastResetDateProvider.notifier).state = today;
      final storedDate = container.read(dailyJokesLastResetDateProvider);

      expect(storedDate, today);

      container.dispose();
    });
  });

  group('_loadDailyJokesPage', () {
    test('returns empty page and leaves most recent date unset '
        'when batch contains no publishable jokes', () async {
      final mockScheduleRepository = _MockJokeScheduleRepository();

      final now = DateTime.now();
      final scheduleId = JokeConstants.defaultJokeScheduleId;
      final batch = JokeScheduleBatch(
        id: JokeScheduleBatch.createBatchId(scheduleId, now.year, now.month),
        scheduleId: scheduleId,
        year: now.year,
        month: now.month,
        jokes: {
          '01': const Joke(
            id: 'j-1',
            setupText: 'setup',
            punchlineText: 'punchline',
          ),
        },
      );

      when(
        () => mockScheduleRepository.getBatchForMonth(any(), any(), any()),
      ).thenAnswer((invocation) async {
        final requestedScheduleId = invocation.positionalArguments[0] as String;
        final requestedYear = invocation.positionalArguments[1] as int;
        final requestedMonth = invocation.positionalArguments[2] as int;

        if (requestedScheduleId == scheduleId &&
            requestedYear == now.year &&
            requestedMonth == now.month) {
          return batch;
        }
        return null;
      });

      final container = ProviderContainer(
        overrides: [
          jokeScheduleRepositoryProvider.overrideWithValue(
            mockScheduleRepository,
          ),
        ],
      );
      addTearDown(container.dispose);

      final loaderProvider = FutureProvider((ref) {
        return loadDailyJokesPage(ref, 5, null);
      });

      final result = await container.read(loaderProvider.future);

      expect(result.jokes, isEmpty);
      expect(result.hasMore, isTrue);

      final previousMonth = DateTime(now.year, now.month - 1);
      expect(
        result.cursor,
        '${previousMonth.year}_${previousMonth.month.toString()}',
      );
      expect(container.read(dailyJokesMostRecentDateProvider), isNull);
    });
  });
}
