import 'dart:convert';
import 'dart:math' as math;

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/settings/application/random_starting_id_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockJokeRepository extends Mock implements JokeRepository {}

class MockAppUsageService extends Mock implements AppUsageService {
  @override
  Future<List<String>> getUnviewedJokeIds(List<String> jokeIds) async =>
      jokeIds;
}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockSettingsService extends Mock implements SettingsService {}

const _emptyPage = JokeListPage(ids: <String>[], cursor: null, hasMore: false);

class _CompositeStubData {
  _CompositeStubData({
    required this.bestIds,
    required this.randomIds,
    required this.publicIds,
  });

  final List<String> bestIds;
  final List<String> randomIds;
  final List<String> publicIds;

  int _bestIndex = 0;
  int _randomIndex = 0;
  int _publicIndex = 0;

  JokeListPage nextBest(int requestLimit) {
    final remaining = math.max(0, bestIds.length - _bestIndex);
    final take = math.min(requestLimit, remaining);
    final ids = bestIds.sublist(_bestIndex, _bestIndex + take);
    _bestIndex += take;
    final hasMore = _bestIndex < bestIds.length;
    return JokeListPage(
      ids: ids,
      cursor: ids.isEmpty
          ? null
          : JokeListPageCursor(
              orderValue: (bestIds.length - _bestIndex).toDouble(),
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
    final JokeField orderField =
        invocation.namedArguments[const Symbol('orderByField')] as JokeField;
    final int limit = invocation.namedArguments[const Symbol('limit')] as int;

    if (orderField == JokeField.savedFraction) {
      return data.nextBest(limit);
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

CompositeCursor _createCompositeCursor({
  int totalJokesLoaded = 0,
  Map<String, String>? subSourceCursors,
  Map<String, String>? prioritySourceCursors,
}) {
  return CompositeCursor(
    totalJokesLoaded: totalJokesLoaded,
    subSourceCursors: subSourceCursors ?? {},
    prioritySourceCursors: prioritySourceCursors ?? {},
  );
}

// Helper to create proper JSON-encoded cursors for testing
String _createJokeListPageCursorJson(String docId, double orderValue) {
  return jsonEncode({'o': orderValue, 'd': docId});
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

Future<void> _waitForLoadingComplete(ProviderContainer scope) async {
  // Wait for async operations to complete
  await Future<void>.delayed(const Duration(milliseconds: 100));
}

// Helper functions to get actual configuration values
int getBestJokesMinIndex() => 0;
int getBestJokesMaxIndex() => 200;
int getRandomMinIndex() => 10;
int getPublicMinIndex() => 200;

// Helper to get boundary indices for testing
List<int> getBoundaryIndices() => [
  getRandomMinIndex(),
  getPublicMinIndex(),
  getBestJokesMaxIndex(),
];

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
  late MockAppUsageService mockAppUsageService;
  late MockFirebaseAnalytics mockFirebaseAnalytics;
  late SharedPreferences prefs;
  ProviderContainer? container;

  ProviderContainer createContainer() {
    final scope = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        settingsServiceProvider.overrideWithValue(SettingsService(prefs)),
        jokeRepositoryProvider.overrideWithValue(mockRepository),
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
      ],
    );
    container = scope;
    return scope;
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    mockRepository = MockJokeRepository();
    mockAppUsageService = MockAppUsageService();
    mockFirebaseAnalytics = MockFirebaseAnalytics();

    when(() => mockRepository.getJokesByIds(any())).thenAnswer((invocation) {
      final ids = invocation.positionalArguments.first as List<String>;
      return Future.value(ids.map(_buildJoke).toList());
    });
  });

  tearDown(() {
    container?.dispose();
  });

  group('CompositeCursor', () {
    test('constructor with default values', () {
      final cursor = CompositeCursor();
      expect(cursor.totalJokesLoaded, 0);
      expect(cursor.subSourceCursors, isEmpty);
    });

    test('constructor with custom values', () {
      final subSourceCursors = {'popular': 'cursor1', 'random': 'cursor2'};
      final cursor = CompositeCursor(
        totalJokesLoaded: 42,
        subSourceCursors: subSourceCursors,
      );
      expect(cursor.totalJokesLoaded, 42);
      expect(cursor.subSourceCursors, subSourceCursors);
    });

    test('encode returns valid JSON', () {
      final cursor = CompositeCursor(
        totalJokesLoaded: 10,
        subSourceCursors: {'popular': 'cursor1'},
      );
      final encoded = cursor.encode();
      expect(encoded, isA<String>());
      expect(encoded, contains('totalJokesLoaded'));
      expect(encoded, contains('subSourceCursors'));
    });

    test('decode parses valid JSON', () {
      final json =
          '{"totalJokesLoaded":15,"subSourceCursors":{"popular":"cursor1"}}';
      final cursor = CompositeCursor.decode(json);
      expect(cursor, isNotNull);
      expect(cursor!.totalJokesLoaded, 15);
      expect(cursor.subSourceCursors['popular'], 'cursor1');
    });

    test('decode returns null for invalid JSON', () {
      final cursor = CompositeCursor.decode('invalid json');
      expect(cursor, isNull);
    });

    test('decode returns null for null input', () {
      final cursor = CompositeCursor.decode(null);
      expect(cursor, isNull);
    });

    test('decode returns null for empty string', () {
      final cursor = CompositeCursor.decode('');
      expect(cursor, isNull);
    });

    test('round-trip encode/decode preserves data', () {
      final original = CompositeCursor(
        totalJokesLoaded: 25,
        subSourceCursors: {'popular': 'cursor1', 'random': 'cursor2'},
      );
      final encoded = original.encode();
      final decoded = CompositeCursor.decode(encoded);
      expect(decoded, isNotNull);
      expect(decoded!.totalJokesLoaded, original.totalJokesLoaded);
      expect(decoded.subSourceCursors, original.subSourceCursors);
    });

    test('decode with priority cursors', () {
      final json =
          '{"totalJokesLoaded":15,"subSourceCursors":{"popular":"cursor1"},"prioritySourceCursors":{"priority1":"cursor2"}}';
      final cursor = CompositeCursor.decode(json);
      expect(cursor, isNotNull);
      expect(cursor!.totalJokesLoaded, 15);
      expect(cursor.subSourceCursors['popular'], 'cursor1');
      expect(cursor.prioritySourceCursors['priority1'], 'cursor2');
    });

    test(
      'decode without priority cursors maintains backward compatibility',
      () {
        final json =
            '{"totalJokesLoaded":15,"subSourceCursors":{"popular":"cursor1"}}';
        final cursor = CompositeCursor.decode(json);
        expect(cursor, isNotNull);
        expect(cursor!.totalJokesLoaded, 15);
        expect(cursor.subSourceCursors['popular'], 'cursor1');
        expect(cursor.prioritySourceCursors, isEmpty);
      },
    );

    test('round-trip encode/decode preserves priority cursors', () {
      final original = CompositeCursor(
        totalJokesLoaded: 25,
        subSourceCursors: {'popular': 'cursor1'},
        prioritySourceCursors: {
          'priority1': 'cursor2',
          'priority2': kPriorityDoneSentinel,
        },
      );
      final encoded = original.encode();
      final decoded = CompositeCursor.decode(encoded);
      expect(decoded, isNotNull);
      expect(decoded!.totalJokesLoaded, original.totalJokesLoaded);
      expect(decoded.subSourceCursors, original.subSourceCursors);
      expect(decoded.prioritySourceCursors, original.prioritySourceCursors);
    });
  });

  group('calculateEffectiveLimit', () {
    test('returns full limit when no boundary crossed', () {
      final limit = calculateEffectiveLimit(5, 3);
      expect(limit, 3);
    });

    test('stops at random boundary when crossing random min index', () {
      final randomMin = getRandomMinIndex();
      final limit = calculateEffectiveLimit(randomMin - 3, 10);
      expect(limit, 3); // Should stop at random min index
    });

    test('stops at public boundary when crossing public min index', () {
      final publicMin = getPublicMinIndex();
      final limit = calculateEffectiveLimit(publicMin - 3, 10);
      expect(limit, 3); // Should stop at public min index
    });

    test('stops at best jokes boundary when crossing best jokes max index', () {
      final bestMax = getBestJokesMaxIndex();
      final limit = calculateEffectiveLimit(bestMax - 3, 10);
      expect(limit, 3); // Should stop at best jokes max index
    });

    test('returns full limit when boundary is beyond range', () {
      final bestMax = getBestJokesMaxIndex();
      final limit = calculateEffectiveLimit(bestMax + 10, 5);
      expect(limit, 5); // No boundary in range
    });
  });

  group('Composite Data Source', () {
    test('basic interleaving - only best jokes source active', () async {
      final data = _CompositeStubData(
        bestIds: List.generate(10, (i) => 'best-${i + 1}'),
        randomIds: List.generate(5, (i) => 'random-${i + 1}'),
        publicIds: List.generate(5, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should load from best jokes source initially (paging system loads more automatically)
      expect(loadedIds.length, greaterThan(3));
      expect(loadedIds, everyElement(startsWith('best-')));
      expect(state.hasMore, isFalse); // All best jokes loaded
    });

    test('two-source interleaving - best jokes and random active', () async {
      // Start from random min index where random joins
      final randomMin = getRandomMinIndex();
      final cursor = _createCompositeCursor(
        totalJokesLoaded: randomMin,
        subSourceCursors: {
          'best_jokes': _createJokeListPageCursorJson('best-cursor', 10.0),
          'all_jokes_random': _createJokeListPageCursorJson(
            'random-cursor',
            5.0,
          ),
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final data = _CompositeStubData(
        bestIds: List.generate(20, (i) => 'best-${i + 1}'),
        randomIds: List.generate(20, (i) => 'random-${i + 1}'),
        publicIds: List.generate(5, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should interleave best jokes and random (paging system loads more automatically)
      expect(loadedIds.length, greaterThan(5));
      expect(loadedIds, contains('best-1'));
      expect(loadedIds, contains('random-1'));
      expect(state.hasMore, isTrue);
    });

    test('three-source interleaving - all sources active', () async {
      // Start from public min index where public joins, but before best jokes drops out
      final publicMin = getPublicMinIndex();
      final startIndex =
          publicMin - 1; // Start at 199, so best jokes is still active
      final cursor = _createCompositeCursor(
        totalJokesLoaded: startIndex,
        subSourceCursors: {
          'best_jokes': _createJokeListPageCursorJson('best-cursor', 10.0),
          'all_jokes_random': _createJokeListPageCursorJson(
            'random-cursor',
            5.0,
          ),
          'all_jokes_public_timestamp': _createJokeListPageCursorJson(
            'public-cursor',
            3.0,
          ),
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final data = _CompositeStubData(
        bestIds: List.generate(20, (i) => 'best-${i + 1}'),
        randomIds: List.generate(20, (i) => 'random-${i + 1}'),
        publicIds: List.generate(20, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should interleave all three sources (paging system loads more automatically)
      expect(loadedIds.length, greaterThan(5));
      expect(loadedIds, contains('best-1'));
      expect(loadedIds, contains('random-1'));
      expect(loadedIds, contains('public-1'));
      expect(state.hasMore, isTrue);
    });

    test(
      'two-source after best jokes exhausted - only random and public',
      () async {
        // Start from best jokes max index where best jokes drops out
        final bestMax = getBestJokesMaxIndex();
        final cursor = _createCompositeCursor(
          totalJokesLoaded: bestMax,
          subSourceCursors: {
            'all_jokes_random': _createJokeListPageCursorJson(
              'random-cursor',
              5.0,
            ),
            'all_jokes_public_timestamp': _createJokeListPageCursorJson(
              'public-cursor',
              3.0,
            ),
          },
        );
        await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

        final data = _CompositeStubData(
          bestIds: List.generate(5, (i) => 'best-${i + 1}'),
          randomIds: List.generate(20, (i) => 'random-${i + 1}'),
          publicIds: List.generate(20, (i) => 'public-${i + 1}'),
        );
        _stubCompositeRepository(mockRepository, data);

        final scope = createContainer();
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoadingComplete(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        // Should only interleave random and public (paging system loads more automatically)
        expect(loadedIds.length, greaterThan(3));
        expect(loadedIds, contains('random-1'));
        expect(loadedIds, contains('public-1'));
        expect(
          loadedIds,
          everyElement(anyOf(startsWith('random-'), startsWith('public-'))),
        );
        expect(state.hasMore, isTrue);
      },
    );

    test('mid-page boundary crossing at random min index', () async {
      // Start before random min index, load jokes that will cross boundary
      final randomMin = getRandomMinIndex();
      final startIndex = randomMin - 3;
      final cursor = _createCompositeCursor(
        totalJokesLoaded: startIndex,
        subSourceCursors: {
          'best_jokes': _createJokeListPageCursorJson('best-cursor', 10.0),
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final data = _CompositeStubData(
        bestIds: List.generate(20, (i) => 'best-${i + 1}'),
        randomIds: List.generate(20, (i) => 'random-${i + 1}'),
        publicIds: List.generate(5, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should load best jokes initially, then interleave with random
      expect(loadedIds.length, greaterThan(3));
      expect(loadedIds, contains('best-${startIndex + 1}'));
      expect(loadedIds, contains('random-1'));
      expect(state.hasMore, isTrue);
    });

    test('mid-page boundary crossing at public min index', () async {
      // Start before public min index, load jokes that will cross boundary
      final publicMin = getPublicMinIndex();
      final startIndex = publicMin - 3;
      final cursor = _createCompositeCursor(
        totalJokesLoaded: startIndex,
        subSourceCursors: {
          'best_jokes': _createJokeListPageCursorJson('best-cursor', 10.0),
          'all_jokes_random': _createJokeListPageCursorJson(
            'random-cursor',
            5.0,
          ),
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final data = _CompositeStubData(
        bestIds: List.generate(20, (i) => 'best-${i + 1}'),
        randomIds: List.generate(20, (i) => 'random-${i + 1}'),
        publicIds: List.generate(20, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should load best+random interleaved initially, then add public when crossing boundary
      // But since we cross the boundary where best jokes drops out, we should see random+public
      expect(loadedIds.length, greaterThan(5));
      expect(loadedIds, contains('random-1'));
      expect(loadedIds, contains('public-1'));
      expect(state.hasMore, isTrue);
    });

    test('subsource exhausted but in range', () async {
      // Start from a position where best jokes is exhausted but still in range
      final randomMin = getRandomMinIndex();
      final cursor = _createCompositeCursor(
        totalJokesLoaded: randomMin,
        subSourceCursors: {
          'best_jokes': _createJokeListPageCursorJson('best-exhausted', 0.0),
          'all_jokes_random': _createJokeListPageCursorJson(
            'random-cursor',
            5.0,
          ),
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final data = _CompositeStubData(
        bestIds: List.generate(5, (i) => 'best-${i + 1}'), // Limited best jokes
        randomIds: List.generate(20, (i) => 'random-${i + 1}'),
        publicIds: List.generate(20, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should continue with random even after best jokes is exhausted
      expect(loadedIds, contains('random-1'));
      expect(state.hasMore, isTrue);
    });

    test('cursor serialization preserves totalJokesLoaded', () async {
      final cursor = _createCompositeCursor(
        totalJokesLoaded: 42,
        subSourceCursors: {
          'best_jokes': 'best-cursor',
          'all_jokes_random': 'random-cursor',
        },
      );

      final encoded = cursor.encode();
      final decoded = CompositeCursor.decode(encoded);

      expect(decoded?.totalJokesLoaded, equals(42));
      expect(decoded?.subSourceCursors['best_jokes'], equals('best-cursor'));
      expect(
        decoded?.subSourceCursors['all_jokes_random'],
        equals('random-cursor'),
      );
    });

    test('resume from saved cursor', () async {
      // Start from a position where both best jokes and random are active
      final randomMin = getRandomMinIndex();
      final resumeIndex = randomMin + 5;
      final cursor = _createCompositeCursor(
        totalJokesLoaded: resumeIndex,
        subSourceCursors: {
          'best_jokes': _createJokeListPageCursorJson('best-cursor', 10.0),
          'all_jokes_random': _createJokeListPageCursorJson(
            'random-cursor',
            5.0,
          ),
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final data = _CompositeStubData(
        bestIds: List.generate(20, (i) => 'best-${i + 1}'),
        randomIds: List.generate(20, (i) => 'random-${i + 1}'),
        publicIds: List.generate(5, (i) => 'public-${i + 1}'),
      );
      _stubCompositeRepository(mockRepository, data);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoadingComplete(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should resume from resumeIndex with interleaved best jokes and random
      expect(loadedIds.length, greaterThan(3));
      expect(loadedIds, contains('best-1'));
      expect(loadedIds, contains('random-1'));
      expect(state.hasMore, isTrue);
    });
  });

  group('Daily Jokes', () {
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

    test(
      'loadDailyJokesPage returns empty page when batch contains no publishable jokes',
      () async {
        final mockScheduleRepository = MockJokeScheduleRepository();

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
          final requestedScheduleId =
              invocation.positionalArguments[0] as String;
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
      },
    );
  });

  group('loadRandomJokesWithWrapping', () {
    late MockJokeRepository mockJokeRepository;
    late MockSettingsService mockSettingsService;

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockSettingsService = MockSettingsService();
    });

    test('starts at random starting ID on first load ever', () async {
      // Arrange
      const randomStartingId = 123456789;
      final testJokes = [
        Joke(
          id: 'joke-1',
          setupText: 'setup1',
          punchlineText: 'punchline1',
          setupImageUrl: 'image1.jpg',
          punchlineImageUrl: 'punch1.jpg',
          publicTimestamp: DateTime.now().subtract(const Duration(days: 1)),
        ),
        Joke(
          id: 'joke-2',
          setupText: 'setup2',
          punchlineText: 'punchline2',
          setupImageUrl: 'image2.jpg',
          punchlineImageUrl: 'punch2.jpg',
          publicTimestamp: DateTime.now().subtract(const Duration(days: 1)),
        ),
      ];

      when(
        () => mockSettingsService.containsKey('composite_joke_cursor'),
      ).thenReturn(false); // No composite cursor = first load ever
      when(
        () => mockSettingsService.getInt('random_starting_id'),
      ).thenReturn(randomStartingId);

      when(
        () => mockJokeRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: any(named: 'orderByField'),
          orderDirection: any(named: 'orderDirection'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer((_) async {
        return JokeListPage(
          ids: ['joke-1', 'joke-2'],
          cursor: JokeListPageCursor(
            orderValue: randomStartingId + 2,
            docId: 'joke-2',
          ),
          hasMore: true,
          jokes: testJokes,
        );
      });

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          settingsServiceProvider.overrideWithValue(mockSettingsService),
          randomStartingIdProvider.overrideWith((ref) => randomStartingId),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final loaderProvider = FutureProvider((ref) {
        return loadRandomJokesWithWrapping(ref, 5, null);
      });
      final result = await container.read(loaderProvider.future);

      // Assert
      expect(result.jokes.length, 2);
      expect(result.hasMore, isTrue);
      expect(result.cursor, isNotNull);

      // Verify the repository was called with a cursor starting at randomStartingId
      verify(
        () => mockJokeRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: JokeField.randomId,
          orderDirection: OrderDirection.ascending,
          limit: 5,
          cursor: any(named: 'cursor'),
        ),
      ).called(1);
    });

    test('uses provided cursor when composite cursor exists', () async {
      // Arrange
      final providedCursor = JokeListPageCursor(
        orderValue: 100,
        docId: 'joke-1',
      ).serialize();
      final testJokes = [
        Joke(
          id: 'joke-1',
          setupText: 'setup1',
          punchlineText: 'punchline1',
          setupImageUrl: 'image1.jpg',
          punchlineImageUrl: 'punch1.jpg',
          publicTimestamp: DateTime.now().subtract(const Duration(days: 1)),
        ),
      ];

      when(
        () => mockSettingsService.containsKey('composite_joke_cursor'),
      ).thenReturn(true); // Composite cursor exists = not first load

      when(
        () => mockJokeRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: any(named: 'orderByField'),
          orderDirection: any(named: 'orderDirection'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer((_) async {
        return JokeListPage(
          ids: ['joke-1'],
          cursor: JokeListPageCursor(orderValue: 101, docId: 'joke-1'),
          hasMore: true,
          jokes: testJokes,
        );
      });

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          settingsServiceProvider.overrideWithValue(mockSettingsService),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final loaderProvider = FutureProvider((ref) {
        return loadRandomJokesWithWrapping(ref, 5, providedCursor);
      });
      final result = await container.read(loaderProvider.future);

      // Assert
      expect(result.jokes.length, 1);
      expect(result.hasMore, isTrue);

      // Verify random starting ID provider was not called
      verifyNever(() => mockSettingsService.getInt('random_starting_id'));
    });

    test('wraps around when hasMore is false', () async {
      // Arrange
      final testJokes = [
        Joke(
          id: 'joke-last',
          setupText: 'setup',
          punchlineText: 'punchline',
          setupImageUrl: 'image.jpg',
          punchlineImageUrl: 'punch.jpg',
          publicTimestamp: DateTime.now().subtract(const Duration(days: 1)),
        ),
      ];

      when(
        () => mockSettingsService.containsKey('composite_joke_cursor'),
      ).thenReturn(true);

      when(
        () => mockJokeRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: any(named: 'orderByField'),
          orderDirection: any(named: 'orderDirection'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer((_) async {
        return JokeListPage(
          ids: ['joke-last'],
          cursor: JokeListPageCursor(orderValue: 999999999, docId: 'joke-last'),
          hasMore: false, // End of jokes
          jokes: testJokes,
        );
      });

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          settingsServiceProvider.overrideWithValue(mockSettingsService),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final loaderProvider = FutureProvider((ref) {
        return loadRandomJokesWithWrapping(
          ref,
          5,
          JokeListPageCursor(orderValue: 100, docId: 'joke-1').serialize(),
        );
      });
      final result = await container.read(loaderProvider.future);

      // Assert
      expect(result.jokes.length, 1);
      expect(result.hasMore, isTrue); // Should be true to continue pagination
      expect(
        result.cursor,
        '{"o":0,"d":" DUMMY_VALUE "}',
      ); // Should be dummy docId to wrap around
    });

    test('continues normally when hasMore is true', () async {
      // Arrange
      final testJokes = [
        Joke(
          id: 'joke-1',
          setupText: 'setup',
          punchlineText: 'punchline',
          setupImageUrl: 'image.jpg',
          punchlineImageUrl: 'punch.jpg',
          publicTimestamp: DateTime.now().subtract(const Duration(days: 1)),
        ),
      ];

      when(
        () => mockSettingsService.containsKey('composite_joke_cursor'),
      ).thenReturn(true);

      when(
        () => mockJokeRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: any(named: 'orderByField'),
          orderDirection: any(named: 'orderDirection'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer((_) async {
        return JokeListPage(
          ids: ['joke-1'],
          cursor: JokeListPageCursor(orderValue: 101, docId: 'joke-1'),
          hasMore: true,
          jokes: testJokes,
        );
      });

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          settingsServiceProvider.overrideWithValue(mockSettingsService),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final loaderProvider = FutureProvider((ref) {
        return loadRandomJokesWithWrapping(
          ref,
          5,
          JokeListPageCursor(orderValue: 100, docId: 'joke-1').serialize(),
        );
      });
      final result = await container.read(loaderProvider.future);

      // Assert
      expect(result.jokes.length, 1);
      expect(result.hasMore, isTrue);
      expect(result.cursor, isNotNull); // Should preserve the cursor
    });
  });

  group('Helper functions', () {
    test('interleaveCompositePages interleaves in round-robin order using all jokes', () {
      final p1 = PageResult(
        jokes: [
          JokeWithDate(joke: _buildJoke('a1'), dataSource: 's1-old'),
          JokeWithDate(joke: _buildJoke('a2'), dataSource: 's1-old'),
        ],
        cursor: 'c1',
        hasMore: true,
      );
      final p2 = PageResult(
        jokes: [
          JokeWithDate(joke: _buildJoke('b1'), dataSource: 's2-old'),
          JokeWithDate(joke: _buildJoke('b2'), dataSource: 's2-old'),
          JokeWithDate(joke: _buildJoke('b3'), dataSource: 's2-old'),
        ],
        cursor: 'c2',
        hasMore: true,
      );

      final pages = {'s1': p1, 's2': p2};
      final order = ['s1', 's2'];

      final result = interleaveCompositePages(pages, order);
      final ids = result.map((j) => j.joke.id).toList();
      expect(ids, ['a1', 'b1', 'a2', 'b2', 'b3']);
      // Ensure dataSource tagging reflects the interleaving source ids
      expect(result[0].dataSource, 's1');
      expect(result[1].dataSource, 's2');
    });

    test('interleaveCompositePages returns empty when both inputs empty', () {
      final result = interleaveCompositePages({}, []);
      expect(result, isEmpty);
    });

    test('interleaveCompositePages returns empty when order empty, even if pages exist', () {
      final p = PageResult(
        jokes: [JokeWithDate(joke: _buildJoke('x1'))],
        cursor: 'c',
        hasMore: false,
      );
      final result = interleaveCompositePages({'s': p}, []);
      expect(result, isEmpty);
    });

    test('interleaveCompositePages ignores pages not listed in order', () {
      final p = PageResult(
        jokes: [JokeWithDate(joke: _buildJoke('x1'))],
        cursor: 'c',
        hasMore: false,
      );
      final result = interleaveCompositePages({'extra': p}, ['s1']);
      expect(result, isEmpty);
    });

    test('interleaveCompositePages skips order ids missing from pages', () {
      final p = PageResult(
        jokes: [JokeWithDate(joke: _buildJoke('x1'))],
        cursor: 'c',
        hasMore: false,
      );
      final result = interleaveCompositePages({'s2': p}, ['s1', 's2']);
      expect(result.map((j) => j.joke.id).toList(), ['x1']);
    });

    test('interleaveCompositePages does not mutate input pages', () {
      final p = PageResult(
        jokes: [
          JokeWithDate(joke: _buildJoke('x1')),
          JokeWithDate(joke: _buildJoke('x2')),
        ],
        cursor: 'c',
        hasMore: false,
      );
      final pages = {'s': p};
      final beforeLen = p.jokes.length;
      final _ = interleaveCompositePages(pages, ['s']);
      expect(p.jokes.length, beforeLen);
    });

    testWidgets('createNextPage combines priority and composite, updates cursor correctly', (tester) async {
      // Arrange container and overrides
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final scope = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          settingsServiceProvider.overrideWithValue(SettingsService(prefs)),
          appUsageServiceProvider.overrideWithValue(MockAppUsageService()),
        ],
      );
      addTearDown(scope.dispose);

      // Previous cursor with some state
      final prev = CompositeCursor(
        totalJokesLoaded: 10,
        subSourceCursors: {'best_jokes': 'best-prev'},
        prioritySourceCursors: {'p1': 'p1-prev'},
      );

      // Priority page (single) and composite pages (two)
      final priorityPages = <String, PageResult>{
        'p1': PageResult(
          jokes: [JokeWithDate(joke: _buildJoke('p-1'), dataSource: 'p1')],
          cursor: 'p1-next',
          hasMore: false, // will be marked done
        ),
      };

      final compositePages = <String, PageResult>{
        'best_jokes': const PageResult(
          jokes: [],
          cursor: null,
          hasMore: false,
        ),
        'all_jokes_random': PageResult(
          jokes: [
            JokeWithDate(joke: _buildJoke('r-1'), dataSource: 'all_jokes_random'),
            JokeWithDate(joke: _buildJoke('r-2'), dataSource: 'all_jokes_random'),
          ],
          cursor: 'r-next',
          hasMore: true,
        ),
      };

      // Act
      final loader = FutureProvider((ref) {
        return createNextPage(
          ref: ref,
          prevCursor: prev,
          priorityPagesBySubSourceId: priorityPages,
          compositePagesBySubSourceId: compositePages,
          prioritySubSourcesOverride: [
            // Define explicit test order for priority sources
            CompositeJokeSubSource(
              id: 'p1',
              minIndex: 0,
              maxIndex: null,
              load: (ref, limit, cursor) async => const PageResult(
                jokes: [],
                cursor: null,
                hasMore: false,
              ),
            ),
          ],
        );
      });
      final page = await scope.read(loader.future);

      // Assert combined jokes: priority first, then composite interleaved (only one composite here)
      final ids = page.jokes.map((j) => j.joke.id).toList();
      expect(ids, ['p-1', 'r-1', 'r-2']);

      // Cursor should include p1 key and advance random cursor, total only counts composite
      final decoded = CompositeCursor.decode(page.cursor);
      expect(decoded, isNotNull);
      expect(decoded!.totalJokesLoaded, 12); // +2 composite
      expect(decoded.prioritySourceCursors.containsKey('p1'), isTrue);
      expect(decoded.subSourceCursors['all_jokes_random'], 'r-next');
    });
  });
}
