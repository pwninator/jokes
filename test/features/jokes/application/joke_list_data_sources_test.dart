import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_performance/firebase_performance.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/feed_sync_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:snickerdoodle/src/features/settings/application/random_starting_id_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockJokeRepository extends Mock implements JokeRepository {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockSettingsService extends Mock implements SettingsService {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockFeedSyncService extends Mock implements FeedSyncService {}

class MockJokeCategoryRepository extends Mock
    implements JokeCategoryRepository {}

class MockTrace extends Mock implements Trace {
  @override
  Future<void> start() async {}

  @override
  Future<void> stop() async {}

  @override
  Map<String, String> getAttributes() => {};

  @override
  void putAttribute(String attribute, String value) {}
}

class MockFirebasePerformanceWithTrace extends Mock
    implements FirebasePerformance {
  @override
  Trace newTrace(String name) => MockTrace();
}

/// Helper to check if filters contain a seasonal filter
bool _hasSeasonalFilter(List<JokeFilter> filters, String seasonalValue) {
  return filters.any(
    (f) => f.field == JokeField.seasonal && f.isEqualTo == seasonalValue,
  );
}

/// Create a CompositeCursor
CompositeCursor _compositeCursor({
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

/// Build a test joke
Joke _buildJoke(String id, {DateTime? publicTimestamp, bool hasImages = true}) {
  return Joke(
    id: id,
    setupText: 'setup $id',
    punchlineText: 'punchline $id',
    setupImageUrl: hasImages ? 'setup_$id.png' : null,
    punchlineImageUrl: hasImages ? 'punch_$id.png' : null,
    state: JokeState.published,
    publicTimestamp: publicTimestamp ?? DateTime.utc(2024, 1, 1),
  );
}

JokeInteraction _buildInteraction(
  String id,
  int feedIndex, {
  DateTime? viewedTimestamp,
}) {
  return JokeInteraction(
    jokeId: id,
    lastUpdateTimestamp: DateTime.utc(2025, 1, 1),
    setupText: 'Setup $id',
    punchlineText: 'Punchline $id',
    setupImageUrl: 'setup_$id.png',
    punchlineImageUrl: 'punch_$id.png',
    feedIndex: feedIndex,
    viewedTimestamp: viewedTimestamp,
    hasEverSaved: false,
  );
}

void _stubFeedInteractions(
  MockJokeInteractionsRepository repository,
  List<JokeInteraction> interactions,
) {
  when(
    () => repository.getFeedJokes(
      cursorFeedIndex: any(named: 'cursorFeedIndex'),
      limit: any(named: 'limit'),
    ),
  ).thenAnswer((invocation) async {
    final cursor =
        invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
    final limit = invocation.namedArguments[const Symbol('limit')] as int? ?? 0;

    final sorted = List<JokeInteraction>.from(interactions)
      ..sort((a, b) => (a.feedIndex ?? 0).compareTo(b.feedIndex ?? 0));

    final filtered = sorted.where((interaction) {
      final index = interaction.feedIndex ?? -1;
      if (cursor == null) return true;
      return index > cursor;
    }).toList();

    if (filtered.isEmpty) {
      return <JokeInteraction>[];
    }

    return filtered.take(limit).toList();
  });
}

/// Test helpers for stubbing repository queries for composite joke sources.
class CompositeTestHelpers {
  final MockJokeRepository repository;

  CompositeTestHelpers(this.repository);

  /// Stub Halloween priority source query.
  void stubHalloweenQuery({
    required List<String> ids,
    String? cursor,
    bool hasMore = false,
  }) {
    final pageCursor = cursor != null
        ? JokeListPageCursor.deserialize(cursor)
        : null;
    when(
      () => repository.getFilteredJokePage(
        filters: any(
          that: predicate<List<JokeFilter>>(
            (filters) => _hasSeasonalFilter(filters, 'Halloween'),
          ),
          named: 'filters',
        ),
        orderByField: JokeField.savedFraction,
        orderDirection: OrderDirection.descending,
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer(
      _stubOnceSource(ids: ids, cursor: pageCursor, hasMore: hasMore),
    );
  }

  /// Stub best jokes composite source query.
  void stubBestJokesQuery({
    required List<String> ids,
    String? cursor,
    bool hasMore = false,
  }) {
    final pageCursor = cursor != null
        ? JokeListPageCursor.deserialize(cursor)
        : null;
    when(
      () => repository.getFilteredJokePage(
        filters: any(
          that: predicate<List<JokeFilter>>(
            (filters) => !_hasSeasonalFilter(filters, 'Halloween'),
          ),
          named: 'filters',
        ),
        orderByField: JokeField.savedFraction,
        orderDirection: OrderDirection.descending,
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer(
      _stubOnceSource(ids: ids, cursor: pageCursor, hasMore: hasMore),
    );
  }

  /// Stub random jokes composite source query.
  void stubRandomJokesQuery({
    required List<String> ids,
    String? cursor,
    bool hasMore = true,
  }) {
    final pageCursor = cursor != null
        ? JokeListPageCursor.deserialize(cursor)
        : null;
    when(
      () => repository.getFilteredJokePage(
        filters: any(named: 'filters'),
        orderByField: JokeField.randomId,
        orderDirection: OrderDirection.ascending,
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer(
      _stubOnceSource(ids: ids, cursor: pageCursor, hasMore: hasMore),
    );
  }

  /// Stub public timestamp composite source query.
  void stubPublicTimestampQuery({
    required List<String> ids,
    String? cursor,
    bool hasMore = false,
  }) {
    final pageCursor = cursor != null
        ? JokeListPageCursor.deserialize(cursor)
        : null;
    when(
      () => repository.getFilteredJokePage(
        filters: any(named: 'filters'),
        orderByField: JokeField.publicTimestamp,
        orderDirection: OrderDirection.ascending,
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer(
      _stubOnceSource(ids: ids, cursor: pageCursor, hasMore: hasMore),
    );
  }
}

/// Wait for async operations to complete
Future<void> _waitForLoading(ProviderContainer container) async {
  await Future<void>.delayed(const Duration(milliseconds: 100));
}

/// Helper to create a stub that returns data once, then empty pages
/// This prevents infinite loops from mocks returning the same jokes repeatedly
Future<JokeListPage> Function(Invocation) _stubOnceSource({
  required List<String> ids,
  JokeListPageCursor? cursor,
  required bool hasMore,
}) {
  var called = false;
  return (_) async {
    if (!called) {
      called = true;
      return JokeListPage(
        ids: ids,
        cursor: cursor,
        hasMore: hasMore,
        jokes: ids.map(_buildJoke).toList(),
      );
    } else {
      // Subsequent calls return empty with same cursor
      return JokeListPage(ids: [], cursor: cursor, hasMore: false, jokes: []);
    }
  };
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
  late MockAppUsageService mockAppUsageService;
  late MockFirebaseAnalytics mockFirebaseAnalytics;
  late MockJokeInteractionsRepository mockInteractionsRepository;
  late MockFirebasePerformanceWithTrace mockFirebasePerformance;
  late MockFeedSyncService mockFeedSyncService;
  late MockJokeCategoryRepository mockJokeCategoryRepository;
  late SharedPreferences prefs;
  late CompositeTestHelpers testHelpers;
  ProviderContainer? container;

  ProviderContainer createContainer({
    DateTime Function()? clock,
    Map<String, bool>? viewedJokes,
    List<Override> extraOverrides = const [],
  }) {
    final mockUsageService = MockAppUsageService();
    when(() => mockUsageService.getNumJokesViewed()).thenAnswer((_) async => 0);
    when(
      () => mockUsageService.getNumJokesNavigated(),
    ).thenAnswer((_) async => 0);
    // Setup viewed jokes filtering
    if (viewedJokes != null) {
      when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        final ids = invocation.positionalArguments.first as List<String>;
        return ids.where((id) => viewedJokes[id] != true).toList();
      });
    } else {
      when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        return invocation.positionalArguments.first as List<String>;
      });
    }

    final overrides = <Override>[
      sharedPreferencesProvider.overrideWithValue(prefs),
      settingsServiceProvider.overrideWithValue(SettingsService(prefs)),
      jokeRepositoryProvider.overrideWithValue(mockRepository),
      jokeCategoryRepositoryProvider.overrideWithValue(
        mockJokeCategoryRepository,
      ),
      appUsageServiceProvider.overrideWithValue(mockUsageService),
      firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
      firebasePerformanceProvider.overrideWithValue(mockFirebasePerformance),
      performanceServiceProvider.overrideWithValue(_NoopPerf()),
      feedSyncServiceProvider.overrideWithValue(mockFeedSyncService),
      jokeInteractionsRepositoryProvider.overrideWithValue(
        mockInteractionsRepository,
      ),
      // Always include clockProvider - use provided clock or default to current time
      clockProvider.overrideWithValue(clock ?? () => DateTime.utc(2025, 1, 1)),
      ...extraOverrides,
    ];

    final scope = ProviderContainer(overrides: overrides);
    container = scope;
    return scope;
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    mockRepository = MockJokeRepository();
    mockAppUsageService = MockAppUsageService();
    mockFirebaseAnalytics = MockFirebaseAnalytics();
    mockInteractionsRepository = MockJokeInteractionsRepository();
    mockFirebasePerformance = MockFirebasePerformanceWithTrace();
    mockFeedSyncService = MockFeedSyncService();
    mockJokeCategoryRepository = MockJokeCategoryRepository();
    testHelpers = CompositeTestHelpers(mockRepository);

    when(
      () => mockJokeCategoryRepository.getCachedCategoryJokes(any()),
    ).thenAnswer((_) async => const <CategoryCachedJoke>[]);

    // Default: all jokes are unviewed
    when(() => mockAppUsageService.getUnviewedJokeIds(any())).thenAnswer((
      invocation,
    ) async {
      return invocation.positionalArguments.first as List<String>;
    });

    when(
      () => mockInteractionsRepository.getFeedJokes(
        cursorFeedIndex: any(named: 'cursorFeedIndex'),
        limit: any(named: 'limit'),
      ),
    ).thenAnswer((_) async => []);

    when(
      () => mockInteractionsRepository.countFeedJokes(),
    ).thenAnswer((_) async => 1000);

    when(
      () => mockInteractionsRepository.getJokeInteractions(any()),
    ).thenAnswer((_) async => []);

    when(
      () => mockFeedSyncService.triggerSync(forceSync: any(named: 'forceSync')),
    ).thenAnswer((_) async => true);

    // Default: return jokes by IDs
    when(() => mockRepository.getJokesByIds(any())).thenAnswer((invocation) {
      final ids = invocation.positionalArguments.first as List<String>;
      return Future.value(ids.map((id) => _buildJoke(id)).toList());
    });

    // Default stub that fails fast on unstubbed queries
    when(
      () => mockRepository.getFilteredJokePage(
        filters: any(named: 'filters'),
        orderByField: any(named: 'orderByField'),
        orderDirection: any(named: 'orderDirection'),
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenThrow(
      Exception('Unstubbed repository query - test setup incomplete'),
    );

    when(
      () => mockRepository.readFeedJokes(cursor: any(named: 'cursor')),
    ).thenThrow(
      Exception('Unstubbed readFeedJokes query - test setup incomplete'),
    );
  });

  tearDown(() {
    container?.dispose();
  });

  group('CompositeCursor', () {
    test('constructor with default values', () {
      final cursor = CompositeCursor();
      expect(cursor.totalJokesLoaded, 0);
      expect(cursor.subSourceCursors, isEmpty);
      expect(cursor.prioritySourceCursors, isEmpty);
    });

    test('constructor with custom values', () {
      final subSourceCursors = {'popular': 'cursor1', 'random': 'cursor2'};
      final priorityCursors = {'priority1': 'p1'};
      final cursor = CompositeCursor(
        totalJokesLoaded: 42,
        subSourceCursors: subSourceCursors,
        prioritySourceCursors: priorityCursors,
      );
      expect(cursor.totalJokesLoaded, 42);
      expect(cursor.subSourceCursors, subSourceCursors);
      expect(cursor.prioritySourceCursors, priorityCursors);
    });

    test('encode returns valid JSON', () {
      final cursor = CompositeCursor(
        totalJokesLoaded: 10,
        subSourceCursors: {'popular': 'cursor1'},
        prioritySourceCursors: {'p1': 'p1-cursor'},
      );
      final encoded = cursor.encode();
      expect(encoded, isA<String>());
      expect(encoded, contains('totalJokesLoaded'));
      expect(encoded, contains('subSourceCursors'));
      expect(encoded, contains('prioritySourceCursors'));
    });

    test('decode parses valid JSON', () {
      final json =
          '{"totalJokesLoaded":15,"subSourceCursors":{"popular":"cursor1"},"prioritySourceCursors":{"p1":"p1-cursor"}}';
      final cursor = CompositeCursor.decode(json);
      expect(cursor, isNotNull);
      expect(cursor!.totalJokesLoaded, 15);
      expect(cursor.subSourceCursors['popular'], 'cursor1');
      expect(cursor.prioritySourceCursors['p1'], 'p1-cursor');
    });

    test('decode returns null for invalid JSON', () {
      final cursor = CompositeCursor.decode('invalid json');
      expect(cursor, isNull);
    });

    test('decode returns null for null input', () {
      final cursor = CompositeCursor.decode(null);
      expect(cursor, isNull);
    });

    test('round-trip encode/decode preserves data', () {
      final original = CompositeCursor(
        totalJokesLoaded: 25,
        subSourceCursors: {'popular': 'cursor1', 'random': 'cursor2'},
        prioritySourceCursors: {
          'priority1': 'cursor2',
          'priority2': kDoneSentinel,
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

    test('returns full limit when random source is disabled', () {
      final randomMin = CompositeJokeSourceBoundaries.randomMinIndex;
      final limit = calculateEffectiveLimit(randomMin - 3, 10);
      expect(limit, 10);
    });

    test('returns full limit when public source is disabled', () {
      final publicMin = CompositeJokeSourceBoundaries.publicMinIndex;
      final limit = calculateEffectiveLimit(publicMin - 3, 10);
      expect(limit, 10);
    });

    test('returns full limit when best jokes source is disabled', () {
      final bestMax = CompositeJokeSourceBoundaries.bestJokesMaxIndex;
      final limit = calculateEffectiveLimit(bestMax - 3, 10);
      expect(limit, 10);
    });

    test('verifies null boundaries exist for unlimited sources', () {
      // Priority sources with no limits
      expect(CompositeJokeSourceBoundaries.seasonalMinIndex, isNull);
      expect(CompositeJokeSourceBoundaries.seasonalMaxIndex, isNull);
      expect(CompositeJokeSourceBoundaries.todayJokeMaxIndex, isNull);

      // Composite sources with no max limit
      expect(CompositeJokeSourceBoundaries.publicMaxIndex, isNull);
    });
  });

  group('Priority Sources', () {
    group('Halloween priority source', () {
      test(
        'loads Halloween jokes when condition is true and source is active',
        () async {
          // Halloween active: Oct 31, 2025
          final halloweenTime = DateTime(2025, 10, 31);

          testHelpers.stubHalloweenQuery(
            ids: ['h1', 'h2', 'h3', 'h4', 'h5'],
            hasMore: false,
          );

          when(
            () =>
                mockJokeCategoryRepository.getCachedCategoryJokes('halloween'),
          ).thenAnswer(
            (_) async => const [
              CategoryCachedJoke(
                jokeId: 'h1',
                setupText: 'setup h1',
                punchlineText: 'punchline h1',
                setupImageUrl: 'setup_h1.png',
                punchlineImageUrl: 'punch_h1.png',
              ),
              CategoryCachedJoke(
                jokeId: 'h2',
                setupText: 'setup h2',
                punchlineText: 'punchline h2',
                setupImageUrl: 'setup_h2.png',
                punchlineImageUrl: 'punch_h2.png',
              ),
              CategoryCachedJoke(
                jokeId: 'h3',
                setupText: 'setup h3',
                punchlineText: 'punchline h3',
                setupImageUrl: 'setup_h3.png',
                punchlineImageUrl: 'punch_h3.png',
              ),
              CategoryCachedJoke(
                jokeId: 'h4',
                setupText: 'setup h4',
                punchlineText: 'punchline h4',
                setupImageUrl: 'setup_h4.png',
                punchlineImageUrl: 'punch_h4.png',
              ),
              CategoryCachedJoke(
                jokeId: 'h5',
                setupText: 'setup h5',
                punchlineText: 'punchline h5',
                setupImageUrl: 'setup_h5.png',
                punchlineImageUrl: 'punch_h5.png',
              ),
            ],
          );

          final scope = createContainer(clock: () => halloweenTime);
          final notifier = scope.read(
            compositeJokePagingProviders.paging.notifier,
          );

          await notifier.loadFirstPage();
          await _waitForLoading(scope);

          final state = scope.read(compositeJokePagingProviders.paging);
          final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

          expect(loadedIds, ['h1', 'h2', 'h3', 'h4', 'h5']);
        },
      );

      test('skips Halloween when condition is false', () async {
        // Not Halloween: Sep 1, 2025
        final notHalloweenTime = DateTime(2025, 9, 1);

        _stubFeedInteractions(mockInteractionsRepository, [
          _buildInteraction('feed-0', 0),
          _buildInteraction('feed-1', 1),
          _buildInteraction('feed-2', 2),
        ]);

        final scope = createContainer(clock: () => notHalloweenTime);
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        // Should load from local feed jokes when priority source is inactive
        expect(loadedIds, ['feed-0', 'feed-1', 'feed-2']);
      });

      test('marks Halloween as done when hasMore is false', () async {
        final halloweenTime = DateTime(2025, 10, 31);

        testHelpers.stubHalloweenQuery(ids: [], hasMore: false);

        final scope = createContainer(clock: () => halloweenTime);
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        // Verify state has no jokes and hasMore is false
        final state = scope.read(compositeJokePagingProviders.paging);
        expect(state.loadedJokes, isEmpty);
        expect(state.hasMore, isFalse);
      });
    });

    group("Today's joke priority source", () {
      test('loads today joke when condition is true and at index 5', () async {
        final testTime = DateTime(2025, 1, 15, 12, 0);
        DateTime clock() => testTime;

        // Start at index 5 to activate today's joke
        final cursor = _compositeCursor(
          totalJokesLoaded: CompositeJokeSourceBoundaries.todayJokeMinIndex,
          prioritySourceCursors: {},
        );
        await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

        // Mock daily jokes page
        final mockScheduleRepo = MockJokeScheduleRepository();
        final batch = JokeScheduleBatch(
          id: JokeScheduleBatch.createBatchId(
            JokeConstants.defaultJokeScheduleId,
            2025,
            1,
          ),
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: 2025,
          month: 1,
          jokes: {'15': _buildJoke('daily-1')},
        );
        when(
          () => mockScheduleRepo.getBatchForMonth(any(), any(), any()),
        ).thenAnswer((_) async => batch);

        // Create container with schedule repository override
        final scope = createContainer(
          clock: clock,
          extraOverrides: [
            jokeScheduleRepositoryProvider.overrideWithValue(mockScheduleRepo),
          ],
        );

        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        expect(loadedIds, contains('daily-1'));
      });

      test('skips today joke when already shown today', () async {
        final testTime = DateTime(2025, 1, 15);

        // Set today's date in settings
        final todayStr = '2025-01-15';
        await prefs.setString('today_joke_last_date', todayStr);

        _stubFeedInteractions(mockInteractionsRepository, [
          _buildInteraction('feed-0', 0),
          _buildInteraction('feed-1', 1),
          _buildInteraction('feed-2', 2),
        ]);

        final scope = createContainer(clock: () => testTime);
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        // Should load from local feed jokes when today's joke is skipped
        expect(loadedIds, containsAll(['feed-0', 'feed-1']));
      });
    });
  });

  group('Composite Sources', () {
    test(
      'loads from local feed jokes source when only local feed jokes is active',
      () async {
        final firstPage = [
          _buildInteraction('feed-1', 0),
          _buildInteraction('feed-2', 1),
          _buildInteraction('feed-3', 2),
        ];

        when(
          () => mockInteractionsRepository.getFeedJokes(
            cursorFeedIndex: any(named: 'cursorFeedIndex'),
            limit: any(named: 'limit'),
          ),
        ).thenAnswer((invocation) async {
          final cursor =
              invocation.namedArguments[const Symbol('cursorFeedIndex')]
                  as int?;
          if (cursor == null) {
            return firstPage;
          }
          return <JokeInteraction>[];
        });

        // Disable priority sources
        final cursor = _compositeCursor(
          prioritySourceCursors: {
            'priority_halloween_jokes': kDoneSentinel,
            'priority_today_joke': kDoneSentinel,
          },
        );
        await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

        final scope = createContainer();

        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        expect(loadedIds, containsAll(['feed-1', 'feed-2', 'feed-3']));
        expect(loadedIds.length, greaterThanOrEqualTo(3));
      },
    );

    test('loads from local feed jokes source', () async {
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((invocation) async {
        final cursor =
            invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
        if (cursor == null) {
          return [
            _buildInteraction('feed-1', 0),
            _buildInteraction('feed-2', 1),
          ];
        }
        return <JokeInteraction>[];
      });

      final cursor = _compositeCursor(
        totalJokesLoaded: 0,
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer(viewedJokes: {'fs-1': true});

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, containsAll(['feed-1', 'feed-2']));
    });

    test('loads from local feed jokes source with pagination', () async {
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((invocation) async {
        final cursor =
            invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
        final limit =
            invocation.namedArguments[const Symbol('limit')] as int? ?? 0;
        if (cursor == null) {
          return List.generate(
            limit,
            (index) => _buildInteraction('feed-$index', index),
          );
        }
        final nextIndex = cursor + 1;
        return [_buildInteraction('feed-$nextIndex', nextIndex)];
      });

      final cursor = _compositeCursor(
        totalJokesLoaded: 0,
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should load local feed jokes
      expect(loadedIds, containsAll(['feed-0', 'feed-1', 'feed-2']));
    });

    test('handles pagination with hasMore true', () async {
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((invocation) async {
        final cursor =
            invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
        final limit =
            invocation.namedArguments[const Symbol('limit')] as int? ?? 0;
        if (cursor == null) {
          return List.generate(
            limit,
            (index) => _buildInteraction('feed-$index', index),
          );
        }
        return [_buildInteraction('feed-$limit', limit)];
      });

      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      await notifier.loadMore();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should load multiple pages of feed jokes
      expect(loadedIds.length, greaterThanOrEqualTo(3));
      expect(loadedIds, contains('feed-0'));
    });

    test('filters out viewed jokes', () async {
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((invocation) async {
        final cursor =
            invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
        if (cursor == null) {
          return [
            _buildInteraction('feed-1', 0),
            _buildInteraction('feed-2', 1),
            _buildInteraction('feed-3', 2),
          ];
        }
        return <JokeInteraction>[];
      });

      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      // Mark feed-2 as viewed
      final scope = createContainer(viewedJokes: {'feed-2': true});

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, containsAll(['feed-1', 'feed-3']));
      expect(loadedIds, isNot(contains('feed-2')));
    });

    test('falls back to Firestore when local feed is empty', () async {
      when(
        () => mockInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((_) async => []);

      final doc0Jokes = List.generate(50, (i) => _buildJoke('fs-$i'));
      final doc1Jokes = List.generate(50, (i) => _buildJoke('fs-${50 + i}'));

      final doc0Page = JokeListPage(
        ids: doc0Jokes.map((j) => j.id).toList(),
        cursor: const JokeListPageCursor(
          orderValue: '0000000000',
          docId: '0000000000',
        ),
        hasMore: true,
        jokes: doc0Jokes,
      );
      final doc1Page = JokeListPage(
        ids: doc1Jokes.map((j) => j.id).toList(),
        cursor: const JokeListPageCursor(
          orderValue: '0000000001',
          docId: '0000000001',
        ),
        hasMore: true,
        jokes: doc1Jokes,
      );

      when(
        () => mockRepository.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer((invocation) async {
        final cursorArg =
            invocation.namedArguments[const Symbol('cursor')]
                as JokeListPageCursor?;
        if (cursorArg == null) {
          return doc0Page;
        }
        if (cursorArg.docId == '0000000000') {
          return doc1Page;
        }
        return const JokeListPage(
          ids: [],
          cursor: null,
          hasMore: false,
          jokes: [],
        );
      });

      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, containsAll(['fs-0', 'fs-1', 'fs-2']));
      final syncCalls = verify(
        () => mockFeedSyncService.triggerSync(forceSync: false),
      );
      expect(syncCalls.callCount, greaterThanOrEqualTo(1));
    });

    test('Firestore fallback paginates using feed cursor', () async {
      when(
        () => mockInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((_) async => []);

      final doc0Jokes = List.generate(50, (i) => _buildJoke('fs-$i'));
      final doc1Jokes = List.generate(50, (i) => _buildJoke('fs-${50 + i}'));
      final doc2Jokes = List.generate(50, (i) => _buildJoke('fs-${100 + i}'));

      final doc0Page = JokeListPage(
        ids: doc0Jokes.map((j) => j.id).toList(),
        cursor: const JokeListPageCursor(
          orderValue: '0000000000',
          docId: '0000000000',
        ),
        hasMore: true,
        jokes: doc0Jokes,
      );
      final doc1Page = JokeListPage(
        ids: doc1Jokes.map((j) => j.id).toList(),
        cursor: const JokeListPageCursor(
          orderValue: '0000000001',
          docId: '0000000001',
        ),
        hasMore: true,
        jokes: doc1Jokes,
      );
      final doc2Page = JokeListPage(
        ids: doc2Jokes.map((j) => j.id).toList(),
        cursor: const JokeListPageCursor(
          orderValue: '0000000002',
          docId: '0000000002',
        ),
        hasMore: true,
        jokes: doc2Jokes,
      );

      when(
        () => mockRepository.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer((invocation) async {
        final cursorArg =
            invocation.namedArguments[const Symbol('cursor')]
                as JokeListPageCursor?;
        if (cursorArg == null) {
          return doc0Page;
        }
        if (cursorArg.docId == '0000000000') {
          return doc1Page;
        }
        if (cursorArg.docId == '0000000001') {
          return doc2Page;
        }
        return const JokeListPage(
          ids: [],
          cursor: null,
          hasMore: false,
          jokes: [],
        );
      });

      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      await notifier.loadMore();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, containsAll(['fs-0', 'fs-1', 'fs-2', 'fs-3', 'fs-10']));
      final syncCalls = verify(
        () => mockFeedSyncService.triggerSync(forceSync: false),
      );
      expect(syncCalls.callCount, greaterThanOrEqualTo(2));
    });

    test('Firestore fallback filters viewed jokes using local state', () async {
      when(
        () => mockInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((_) async => []);

      final doc0Jokes = List.generate(50, (i) => _buildJoke('fs-$i'));
      final doc0Page = JokeListPage(
        ids: doc0Jokes.map((j) => j.id).toList(),
        cursor: const JokeListPageCursor(
          orderValue: '0000000000',
          docId: '0000000000',
        ),
        hasMore: true,
        jokes: doc0Jokes,
      );

      when(
        () => mockRepository.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer((invocation) async {
        final cursorArg =
            invocation.namedArguments[const Symbol('cursor')]
                as JokeListPageCursor?;
        if (cursorArg == null) {
          return doc0Page;
        }
        return const JokeListPage(
          ids: [],
          cursor: null,
          hasMore: false,
          jokes: [],
        );
      });

      when(
        () => mockInteractionsRepository.getJokeInteractions(any()),
      ).thenAnswer((invocation) async {
        final ids = invocation.positionalArguments.first as List<String>;
        return [
          _buildInteraction(
            ids[1],
            1,
            viewedTimestamp: DateTime.utc(2025, 1, 2),
          ),
        ];
      });

      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, contains('fs-0'));
      final syncCalls = verify(
        () => mockFeedSyncService.triggerSync(forceSync: false),
      );
      expect(syncCalls.callCount, greaterThanOrEqualTo(1));
    });

    test('loads from local feed jokes source at any index', () async {
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((invocation) async {
        final cursor =
            invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
        if (cursor == null) {
          return [
            _buildInteraction('feed-7', 7),
            _buildInteraction('feed-8', 8),
          ];
        }
        return <JokeInteraction>[];
      });

      // Start at index 7 - local feed jokes should still be active (no maxIndex)
      final cursor = _compositeCursor(
        totalJokesLoaded: 7,
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should load local feed jokes (no boundary limit)
      expect(loadedIds.length, greaterThanOrEqualTo(1));
      expect(loadedIds, everyElement(startsWith('feed-')));
    });

    test('local feed jokes source has no max index limit', () async {
      when(
        () => mockInteractionsRepository.getFeedJokes(
          cursorFeedIndex: any(named: 'cursorFeedIndex'),
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((invocation) async {
        final cursor =
            invocation.namedArguments[const Symbol('cursorFeedIndex')] as int?;
        if (cursor == null) {
          return [_buildInteraction('feed-0', 0)];
        }
        return <JokeInteraction>[];
      });

      // Even at high index, local feed jokes should still be active (no maxIndex)
      final cursor = _compositeCursor(
        totalJokesLoaded: 1000,
        prioritySourceCursors: {
          'priority_halloween_jokes': kDoneSentinel,
          'priority_today_joke': kDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final scope = createContainer();

      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should still load local feed jokes (no maxIndex limit)
      expect(loadedIds.length, greaterThanOrEqualTo(1));
      expect(loadedIds, everyElement(startsWith('feed-')));
    });
  });

  group('Priority + Composite Interaction', () {
    test(
      'priority source loads first, then switches to composite when done',
      () async {
        when(
          () => mockInteractionsRepository.getFeedJokes(
            cursorFeedIndex: any(named: 'cursorFeedIndex'),
            limit: any(named: 'limit'),
          ),
        ).thenAnswer((invocation) async {
          final cursor =
              invocation.namedArguments[const Symbol('cursorFeedIndex')]
                  as int?;
          if (cursor == null) {
            return [_buildInteraction('feed-1', 0)];
          }
          return <JokeInteraction>[];
        });

        final halloweenTime = DateTime(2025, 10, 31);

        when(
          () => mockJokeCategoryRepository.getCachedCategoryJokes('halloween'),
        ).thenAnswer(
          (_) async => const [
            CategoryCachedJoke(
              jokeId: 'h1',
              setupText: 'setup h1',
              punchlineText: 'punchline h1',
              setupImageUrl: 'setup_h1.png',
              punchlineImageUrl: 'punch_h1.png',
            ),
          ],
        );

        final scope = createContainer(clock: () => halloweenTime);

        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        await notifier.loadMore();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        expect(loadedIds, contains('h1'));
        expect(loadedIds, contains('feed-1'));
      },
    );
  });

  group('Helper functions', () {
    test('interleaveCompositePages interleaves in round-robin order', () {
      final p1 = PageResult(
        jokes: [
          JokeWithDate(joke: _buildJoke('a1'), dataSource: 's1'),
          JokeWithDate(joke: _buildJoke('a2'), dataSource: 's1'),
        ],
        cursor: 'c1',
        hasMore: true,
      );
      final p2 = PageResult(
        jokes: [
          JokeWithDate(joke: _buildJoke('b1'), dataSource: 's2'),
          JokeWithDate(joke: _buildJoke('b2'), dataSource: 's2'),
          JokeWithDate(joke: _buildJoke('b3'), dataSource: 's2'),
        ],
        cursor: 'c2',
        hasMore: true,
      );

      final pages = {'s1': p1, 's2': p2};
      final order = ['s1', 's2'];

      final result = interleaveCompositePages(pages, order);
      final ids = result.map((j) => j.joke.id).toList();
      expect(ids, ['a1', 'b1', 'a2', 'b2', 'b3']);
      expect(result[0].dataSource, 's1');
      expect(result[1].dataSource, 's2');
    });

    test('getCurrentDate returns normalized date', () async {
      final testTime = DateTime(2025, 6, 15, 14, 30);
      final mockUsageService = MockAppUsageService();
      when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        return invocation.positionalArguments.first as List<String>;
      });

      final container = ProviderContainer(
        overrides: [
          clockProvider.overrideWithValue(() => testTime),
          appUsageServiceProvider.overrideWithValue(mockUsageService),
        ],
      );
      addTearDown(container.dispose);

      final loaderProvider = FutureProvider((ref) {
        return getCurrentDate(ref);
      });

      final date = await container.read(loaderProvider.future);
      final expected = DateTime(2025, 6, 15);

      expect(date, expected);
    });
  });

  group('Daily Jokes', () {
    test(
      'loadDailyJokesPage returns empty page when batch contains no publishable jokes',
      () async {
        final mockScheduleRepository = MockJokeScheduleRepository();
        final testTime = DateTime(2025, 1, 15);

        final batch = JokeScheduleBatch(
          id: JokeScheduleBatch.createBatchId(
            JokeConstants.defaultJokeScheduleId,
            2025,
            1,
          ),
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: 2025,
          month: 1,
          jokes: {
            '16': _buildJoke('j-1'), // Future date (Jan 16), will be filtered
          },
        );

        when(
          () => mockScheduleRepository.getBatchForMonth(any(), any(), any()),
        ).thenAnswer((_) async => batch);

        final mockUsageService = MockAppUsageService();
        when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
          invocation,
        ) async {
          return invocation.positionalArguments.first as List<String>;
        });

        final container = ProviderContainer(
          overrides: [
            jokeScheduleRepositoryProvider.overrideWithValue(
              mockScheduleRepository,
            ),
            clockProvider.overrideWithValue(() => testTime),
            appUsageServiceProvider.overrideWithValue(mockUsageService),
          ],
        );
        addTearDown(container.dispose);

        final loaderProvider = FutureProvider((ref) {
          return loadDailyJokesPage(ref, 5, null);
        });

        final result = await container.read(loaderProvider.future);

        expect(result.jokes, isEmpty);
        expect(result.hasMore, isTrue);

        final previousMonth = DateTime(2025, 1 - 1);
        expect(
          result.cursor,
          '${previousMonth.year}_${previousMonth.month.toString()}',
        );
      },
    );
  });

  group('loadRandomJokesWithWrapping', () {
    test('starts at random starting ID on first load ever', () async {
      const randomStartingId = 123456789;
      final testJokes = [_buildJoke('joke-1'), _buildJoke('joke-2')];

      final mockSettingsService = MockSettingsService();
      when(
        () => mockSettingsService.containsKey('composite_joke_cursor'),
      ).thenReturn(false);
      when(
        () => mockSettingsService.getInt('random_starting_id'),
      ).thenReturn(randomStartingId);

      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: JokeField.randomId,
          orderDirection: OrderDirection.ascending,
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer(
        (_) async => JokeListPage(
          ids: ['joke-1', 'joke-2'],
          cursor: JokeListPageCursor(
            orderValue: randomStartingId + 2,
            docId: 'joke-2',
          ),
          hasMore: true,
          jokes: testJokes,
        ),
      );

      final mockUsageService = MockAppUsageService();
      when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        return invocation.positionalArguments.first as List<String>;
      });

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockRepository),
          settingsServiceProvider.overrideWithValue(mockSettingsService),
          randomStartingIdProvider.overrideWith((ref) => randomStartingId),
          clockProvider.overrideWithValue(() => DateTime.utc(2025, 1, 1)),
          appUsageServiceProvider.overrideWithValue(mockUsageService),
        ],
      );
      addTearDown(container.dispose);

      final loaderProvider = FutureProvider((ref) {
        return loadRandomJokesWithWrapping(ref, 5, null);
      });
      final result = await container.read(loaderProvider.future);

      expect(result.jokes.length, 2);
      expect(result.hasMore, isTrue);
      expect(result.cursor, isNotNull);
    });

    test('wraps around when hasMore is false', () async {
      final testJokes = [_buildJoke('joke-last')];
      final mockSettingsService = MockSettingsService();
      when(
        () => mockSettingsService.containsKey('composite_joke_cursor'),
      ).thenReturn(true);

      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: JokeField.randomId,
          orderDirection: OrderDirection.ascending,
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer(
        (_) async => JokeListPage(
          ids: ['joke-last'],
          cursor: JokeListPageCursor(orderValue: 999999999, docId: 'joke-last'),
          hasMore: false,
          jokes: testJokes,
        ),
      );

      final mockUsageService = MockAppUsageService();
      when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        return invocation.positionalArguments.first as List<String>;
      });

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockRepository),
          settingsServiceProvider.overrideWithValue(mockSettingsService),
          clockProvider.overrideWithValue(() => DateTime.utc(2025, 1, 1)),
          appUsageServiceProvider.overrideWithValue(mockUsageService),
        ],
      );
      addTearDown(container.dispose);

      final loaderProvider = FutureProvider((ref) {
        return loadRandomJokesWithWrapping(
          ref,
          5,
          JokeListPageCursor(orderValue: 100, docId: 'joke-1').serialize(),
        );
      });
      final result = await container.read(loaderProvider.future);

      expect(result.jokes.length, 1);
      expect(result.hasMore, isTrue);
      expect(result.cursor, contains('"o":0'));
    });
  });
}

class _NoopPerf implements PerformanceService {
  @override
  void dropNamedTrace({required TraceName name, String? key}) {}

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {}

  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {}

  @override
  void stopNamedTrace({required TraceName name, String? key}) {}
}
