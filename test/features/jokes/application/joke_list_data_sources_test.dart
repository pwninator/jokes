import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class _MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockJokeRepository extends Mock implements JokeRepository {}

class MockAppUsageService extends Mock implements AppUsageService {
  @override
  Future<List<String>> getUnviewedJokeIds(List<String> jokeIds) async =>
      jokeIds;
}

const _emptyPage = JokeListPage(ids: <String>[], cursor: null, hasMore: false);

class _CompositeStubData {
  _CompositeStubData({
    required this.popularIds,
    required this.randomIds,
    required this.publicIds,
  });

  final List<String> popularIds;
  final List<String> randomIds;
  final List<String> publicIds;

  int _popularIndex = 0;
  int _randomIndex = 0;
  int _publicIndex = 0;

  JokeListPage nextPopular(int requestLimit) {
    final remaining = math.max(0, popularIds.length - _popularIndex);
    final take = math.min(requestLimit, remaining);
    final ids = popularIds.sublist(_popularIndex, _popularIndex + take);
    _popularIndex += take;
    final hasMore = _popularIndex < popularIds.length;
    return JokeListPage(
      ids: ids,
      cursor: ids.isEmpty
          ? null
          : JokeListPageCursor(
              orderValue: (popularIds.length - _popularIndex).toDouble(),
              docId: ids.last,
            ),
      hasMore: hasMore,
    );
  }

  JokeListPage nextRandom(int requestLimit) {
    final remaining = math.max(0, randomIds.length - _randomIndex);
    final take = math.min(requestLimit, remaining);
    final ids = randomIds.sublist(_randomIndex, _randomIndex + take);
    _randomIndex += take;
    final hasMore = _randomIndex < randomIds.length;
    return JokeListPage(
      ids: ids,
      cursor: ids.isEmpty
          ? null
          : JokeListPageCursor(orderValue: ids.last, docId: ids.last),
      hasMore: hasMore,
    );
  }

  JokeListPage nextPublic(int requestLimit) {
    final remaining = math.max(0, publicIds.length - _publicIndex);
    final take = math.min(requestLimit, remaining);
    final ids = publicIds.sublist(_publicIndex, _publicIndex + take);
    _publicIndex += take;
    final hasMore = _publicIndex < publicIds.length;
    return JokeListPage(
      ids: ids,
      cursor: ids.isEmpty
          ? null
          : JokeListPageCursor(
              orderValue: ids.length.toDouble(),
              docId: ids.last,
            ),
      hasMore: hasMore,
    );
  }
}

void _stubCompositeRepository(
  MockJokeRepository repository,
  _CompositeStubData data, {
  void Function(JokeListPageCursor?)? onRandomCursor,
}) {
  when(
    () => repository.getFilteredJokePage(
      filters: any(named: 'filters'),
      orderByField: any(named: 'orderByField'),
      orderDirection: any(named: 'orderDirection'),
      limit: any(named: 'limit'),
      cursor: any(named: 'cursor'),
    ),
  ).thenAnswer((invocation) async {
    final filters =
        invocation.namedArguments[const Symbol('filters')] as List<JokeFilter>;
    final JokeField orderField =
        invocation.namedArguments[const Symbol('orderByField')] as JokeField;
    final int limit = invocation.namedArguments[const Symbol('limit')] as int;

    final hasPopularFilter = filters.any(
      (filter) =>
          filter.field == JokeField.popularityScore &&
          filter.isGreaterThan != null,
    );

    if (hasPopularFilter) {
      return data.nextPopular(limit);
    }
    if (orderField == JokeField.randomId) {
      final cursorArg =
          invocation.namedArguments[const Symbol('cursor')]
              as JokeListPageCursor?;
      onRandomCursor?.call(cursorArg);
      return data.nextRandom(limit);
    }
    if (orderField == JokeField.publicTimestamp) {
      return data.nextPublic(limit);
    }
    return _emptyPage;
  });
}

Joke _buildJoke(String id) {
  DateTime? publicTimestamp;
  if (id.contains('future')) {
    publicTimestamp = DateTime.now().add(const Duration(days: 1));
  } else if (id.contains('null')) {
    publicTimestamp = null;
  } else {
    publicTimestamp = DateTime.utc(2024, 1, 1);
  }

  return Joke(
    id: id,
    setupText: 'setup $id',
    punchlineText: 'punchline $id',
    setupImageUrl: 'setup_$id.png',
    punchlineImageUrl: 'punch_$id.png',
    state: JokeState.published,
    publicTimestamp: publicTimestamp,
  );
}

Future<void> _pumpUntilIdle(ProviderContainer scope) async {
  await Future<void>.delayed(Duration.zero);
  while (scope.read(compositeJokePagingProviders.isLoading)) {
    await Future<void>.delayed(const Duration(milliseconds: 1));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 0, docId: 'fallback'),
    );
    registerFallbackValue(OrderDirection.descending);
    registerFallbackValue(JokeField.creationTime);
  });

  late MockJokeRepository mockRepository;
  late SharedPreferences prefs;
  ProviderContainer? container;

  ProviderContainer createContainer() {
    final scope = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        settingsServiceProvider.overrideWithValue(SettingsService(prefs)),
        jokeRepositoryProvider.overrideWithValue(mockRepository),
        appUsageServiceProvider.overrideWithValue(MockAppUsageService()),
      ],
    );
    container = scope;
    return scope;
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    mockRepository = MockJokeRepository();

    when(() => mockRepository.getJokesByIds(any())).thenAnswer((invocation) {
      final ids = invocation.positionalArguments.first as List<String>;
      return Future.value(ids.map(_buildJoke).toList());
    });
  });

  tearDown(() {
    container?.dispose();
  });

  test(
    'composite data source sequences through sources and persists cursor',
    () async {
      final data = _CompositeStubData(
        popularIds: List.generate(20, (i) => 'popular-${i + 1}'),
        randomIds: List.generate(6, (i) => 'random-${i + 1}'),
        publicIds: List.generate(4, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _pumpUntilIdle(scope);
      var state = scope.read(compositeJokePagingProviders.paging);
      final firstLoadIds = state.loadedJokes
          .map((j) => j.joke.id)
          .toList(growable: false);
      expect(firstLoadIds, isNotEmpty);
      expect(firstLoadIds.first, equals('popular-1'));
      final initialCursorValue = prefs.getString(compositeJokeCursorPrefsKey);
      final firstLoadLength = firstLoadIds.length;

      await notifier.loadMore();
      await _pumpUntilIdle(scope);
      state = scope.read(compositeJokePagingProviders.paging);
      final secondLoadIds = state.loadedJokes
          .map((j) => j.joke.id)
          .toList(growable: false);
      expect(secondLoadIds.length, greaterThan(firstLoadLength));
      final popularSoFar = secondLoadIds
          .where((id) => id.startsWith('popular'))
          .length;
      expect(popularSoFar, greaterThanOrEqualTo(1));

      final persistedAfterFirstLoadMore = prefs.getString(
        compositeJokeCursorPrefsKey,
      );
      expect(persistedAfterFirstLoadMore, isNot(equals(initialCursorValue)));
      final cursorAfterFirstLoadMore = CompositeCursor.decode(
        persistedAfterFirstLoadMore,
      );
      expect(cursorAfterFirstLoadMore?.sourceId, isNotNull);

      await notifier.loadMore();
      await _pumpUntilIdle(scope);
      state = scope.read(compositeJokePagingProviders.paging);
      expect(state.hasMore, isFalse);
      final allIds = state.loadedJokes
          .map((j) => j.joke.id)
          .toList(growable: false);
      final tailIds = allIds.length >= 2
          ? allIds.sublist(allIds.length - 2)
          : allIds;
      expect(tailIds, equals(['public-3', 'public-4']));
      final persistedAfterSecondLoadMore = prefs.getString(
        compositeJokeCursorPrefsKey,
      );
      expect(persistedAfterSecondLoadMore, isNotNull);
    },
  );

  test('load resumes from persisted cursor across containers', () async {
    const encodedListCursor = '{"o":"random-10","d":"random-10"}';
    // Start from interleaved source with popular at cap and a random cursor
    final compositeCursor = CompositeCursor(
      sourceId: 'popular_and_random',
      payload: {
        'popular_cursor_string': CompositeCursor(
          sourceId: 'most_popular',
          payload: {'count': 50},
        ).encode(),
        'random_cursor_string': CompositeCursor(
          sourceId: 'all_jokes_random',
          payload: {'cursor': encodedListCursor},
        ).encode(),
      },
    ).encode();
    await prefs.setString(compositeJokeCursorPrefsKey, compositeCursor);

    final data = _CompositeStubData(
      popularIds: List.generate(20, (i) => 'popular-${i + 1}'),
      randomIds: ['random-11', 'random-12'],
      publicIds: List.generate(4, (i) => 'public-${i + 1}'),
    );

    JokeListPageCursor? capturedCursor;
    _stubCompositeRepository(
      mockRepository,
      data,
      onRandomCursor: (cursor) {
        capturedCursor ??= cursor;
      },
    );

    final scope = createContainer();
    final notifier = scope.read(compositeJokePagingProviders.paging.notifier);
    await notifier.loadFirstPage();
    await _pumpUntilIdle(scope);

    expect(capturedCursor, isNotNull);
    expect(capturedCursor?.orderValue, 'random-10');
    expect(capturedCursor?.docId, 'random-10');

    final state = scope.read(compositeJokePagingProviders.paging);
    expect(
      state.loadedJokes.map((j) => j.joke.id).toList(),
      equals([
        'random-11',
        'random-12',
        'public-1',
        'public-2',
        'public-3',
        'public-4',
      ]),
    );

    expect(prefs.getString(compositeJokeCursorPrefsKey), isNotNull);
  });

  test(
    'filters out jokes missing public timestamp or scheduled in the future',
    () async {
      // Seed cursor to begin with random within interleaved source
      final seededCursor = CompositeCursor(
        sourceId: 'popular_and_random',
        payload: {
          'popular_cursor_string': CompositeCursor(
            sourceId: 'most_popular',
            payload: {'count': 50},
          ).encode(),
          'random_cursor_string': null,
        },
      ).encode();
      await prefs.setString(compositeJokeCursorPrefsKey, seededCursor);

      final data = _CompositeStubData(
        popularIds: const <String>[],
        randomIds: ['random-valid', 'random-future', 'random-null'],
        publicIds: const <String>[],
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _pumpUntilIdle(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      expect(
        state.loadedJokes.map((j) => j.joke.id).toList(),
        equals(['random-valid']),
      );
    },
  );

  test('reset keeps persisted cursor', () async {
    final data = _CompositeStubData(
      popularIds: List.generate(20, (i) => 'popular-${i + 1}'),
      randomIds: List.generate(6, (i) => 'random-${i + 1}'),
      publicIds: List.generate(4, (i) => 'public-${i + 1}'),
    );
    _stubCompositeRepository(mockRepository, data);

    final scope = createContainer();
    final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

    await notifier.loadFirstPage();
    await _pumpUntilIdle(scope);
    await notifier.loadMore();
    await _pumpUntilIdle(scope);
    final persistedBeforeReset = prefs.getString(compositeJokeCursorPrefsKey);
    expect(persistedBeforeReset, isNotNull);

    notifier.reset();
    await _pumpUntilIdle(scope);
    final persistedAfterReset = prefs.getString(compositeJokeCursorPrefsKey);
    expect(persistedAfterReset, equals(persistedBeforeReset));
  });

  test('composite loader skips duplicates and continues loading', () async {
    var callCount = 0;
    when(
      () => mockRepository.getFilteredJokePage(
        filters: any(named: 'filters'),
        orderByField: any(named: 'orderByField'),
        orderDirection: any(named: 'orderDirection'),
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer((invocation) async {
      final filters =
          invocation.namedArguments[const Symbol('filters')]
              as List<JokeFilter>;
      final hasPopularFilter = filters.any(
        (filter) =>
            filter.field == JokeField.popularityScore &&
            filter.isGreaterThan != null,
      );
      if (hasPopularFilter && callCount == 0) {
        callCount++;
        return JokeListPage(
          ids: ['popular-1'],
          cursor: const JokeListPageCursor(orderValue: 0.9, docId: 'popular-1'),
          hasMore: true,
        );
      } else if (hasPopularFilter && callCount == 1) {
        callCount++;
        return JokeListPage(
          ids: ['popular-1'],
          cursor: const JokeListPageCursor(orderValue: 0.8, docId: 'popular-1'),
          hasMore: true,
        );
      }
      return JokeListPage(
        ids: ['random-unique'],
        cursor: const JokeListPageCursor(
          orderValue: 'random-unique',
          docId: 'random-unique',
        ),
        hasMore: false,
      );
    });

    final scope = createContainer();
    final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

    await notifier.loadFirstPage();
    await _pumpUntilIdle(scope);
    await notifier.loadMore();
    await _pumpUntilIdle(scope);

    final state = scope.read(compositeJokePagingProviders.paging);
    expect(
      state.loadedJokes.map((j) => j.joke.id).toList(),
      containsAll(['popular-1', 'random-unique']),
    );
  });

  test(
    'composite loader advances to next sub-source when popular limit reached',
    () async {
      // Test that when popular limit is reached, the composite loader correctly
      // advances to the next sub-source (public timestamp)
      final mockRepository = MockJokeRepository();

      // Mock public timestamp jokes
      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: any(named: 'orderByField'),
          orderDirection: any(named: 'orderDirection'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer((invocation) async {
        final orderByField =
            invocation.namedArguments[const Symbol('orderByField')]
                as JokeField;
        if (orderByField == JokeField.publicTimestamp) {
          return const JokeListPage(
            ids: ['public-1', 'public-2'],
            cursor: JokeListPageCursor(orderValue: 1.0, docId: 'public-1'),
            hasMore: true,
          );
        }
        return const JokeListPage(ids: [], cursor: null, hasMore: false);
      });

      when(() => mockRepository.getJokesByIds(any())).thenAnswer((
        invocation,
      ) async {
        final ids = invocation.positionalArguments[0] as List<String>;
        return ids
            .map(
              (id) => Joke(
                id: id,
                setupText: 'Setup for $id',
                punchlineText: 'Punchline for $id',
                setupImageUrl: 'https://example.com/setup.jpg',
                punchlineImageUrl: 'https://example.com/punchline.jpg',
                publicTimestamp: DateTime.now().subtract(
                  const Duration(days: 1),
                ),
              ),
            )
            .toList();
      });

      // Set up a cursor that indicates we've reached the popular limit (50)
      final cursorAtLimit = CompositeCursor(
        sourceId: 'popular_and_random',
        payload: {
          'popular_cursor_string': CompositeCursor(
            sourceId: 'most_popular',
            payload: {'count': 50}, // At the limit
          ).encode(),
          'random_cursor_string': null,
        },
      ).encode();

      // Set up the cursor in preferences
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(compositeJokeCursorPrefsKey, cursorAtLimit);

      final scope = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          settingsServiceProvider.overrideWithValue(SettingsService(prefs)),
          jokeRepositoryProvider.overrideWithValue(mockRepository),
          appUsageServiceProvider.overrideWithValue(MockAppUsageService()),
        ],
      );
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      // Load first page - should advance to public timestamp since popular is exhausted
      await notifier.loadFirstPage();
      await _pumpUntilIdle(scope);

      final state = scope.read(compositeJokePagingProviders.paging);

      // Should get jokes from public timestamp sub-source since popular is exhausted
      expect(state.loadedJokes.length, greaterThanOrEqualTo(2));
      expect(
        state.loadedJokes.map((j) => j.joke.id).toList(),
        containsAll(['public-1', 'public-2']),
      );
      // hasMore could be true or false depending on mock behavior
    },
  );

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
