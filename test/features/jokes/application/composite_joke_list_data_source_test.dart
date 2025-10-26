import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

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
      expect(state.loadedJokes.map((j) => j.joke.id), hasLength(6));
      var cursor = CompositeCursor.decode(
        prefs.getString(compositeJokeCursorPrefsKey),
      );
      expect(cursor?.sourceId, 'most_popular');
      expect(cursor?.payload?['count'], 6);

      await notifier.loadMore();
      await _pumpUntilIdle(scope);
      state = scope.read(compositeJokePagingProviders.paging);
      expect(state.loadedJokes.map((j) => j.joke.id), hasLength(18));
      final persisted2 = prefs.getString(compositeJokeCursorPrefsKey);
      expect(persisted2, isNotNull);

      await notifier.loadMore();
      await _pumpUntilIdle(scope);
      state = scope.read(compositeJokePagingProviders.paging);
      expect(state.loadedJokes.map((j) => j.joke.id), hasLength(20));
      expect(state.hasMore, isFalse);
      final tailIds = state.loadedJokes
          .skip(18)
          .map((j) => j.joke.id)
          .toList(growable: false);
      expect(tailIds, equals(['public-3', 'public-4']));
      expect(prefs.getString(compositeJokeCursorPrefsKey), isNotNull);
    },
  );

  test('load resumes from persisted cursor across containers', () async {
    const encodedListCursor = '{"o":"random-10","d":"random-10"}';
    final compositeCursor = CompositeCursor(
      sourceId: 'all_jokes_random',
      payload: {'cursor': encodedListCursor},
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

  test('reset clears persisted cursor', () async {
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
    expect(prefs.getString(compositeJokeCursorPrefsKey), isNotNull);

    notifier.reset();
    await _pumpUntilIdle(scope);
    final persisted = prefs.getString(compositeJokeCursorPrefsKey);
    expect(persisted, isNotNull);
    expect(CompositeCursor.decode(persisted!), isNotNull);
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
}
