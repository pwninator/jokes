import 'dart:convert';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
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

/// Helper to check if filters contain a seasonal filter
bool _hasSeasonalFilter(List<JokeFilter> filters, String seasonalValue) {
  return filters.any(
    (f) => f.field == JokeField.seasonal && f.isEqualTo == seasonalValue,
  );
}

/// Create a JokeListPageCursor as JSON string
String _cursorJson(String docId, double orderValue) {
  return jsonEncode({'o': orderValue, 'd': docId});
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
  late SharedPreferences prefs;
  late CompositeTestHelpers testHelpers;
  ProviderContainer? container;

  ProviderContainer createContainer({
    DateTime Function()? clock,
    Map<String, bool>? viewedJokes,
  }) {
    final mockUsageService = MockAppUsageService();
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
      appUsageServiceProvider.overrideWithValue(mockUsageService),
      firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
      // Always include clockProvider - use provided clock or default to current time
      clockProvider.overrideWithValue(clock ?? () => DateTime.utc(2025, 1, 1)),
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
    testHelpers = CompositeTestHelpers(mockRepository);

    // Default: all jokes are unviewed
    when(() => mockAppUsageService.getUnviewedJokeIds(any())).thenAnswer((
      invocation,
    ) async {
      return invocation.positionalArguments.first as List<String>;
    });

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
      final randomMin = CompositeJokeSourceBoundaries.randomMinIndex;
      final limit = calculateEffectiveLimit(randomMin - 3, 10);
      expect(limit, 3);
    });

    test('stops at public boundary when crossing public min index', () {
      final publicMin = CompositeJokeSourceBoundaries.publicMinIndex;
      final limit = calculateEffectiveLimit(publicMin - 3, 10);
      expect(limit, 3);
    });

    test('stops at best jokes boundary when crossing best jokes max index', () {
      final bestMax = CompositeJokeSourceBoundaries.bestJokesMaxIndex;
      final limit = calculateEffectiveLimit(bestMax - 3, 10);
      expect(limit, 3);
    });

    test('verifies null boundaries exist for unlimited sources', () {
      // Priority sources with no limits
      expect(CompositeJokeSourceBoundaries.halloweenMinIndex, isNull);
      expect(CompositeJokeSourceBoundaries.halloweenMaxIndex, isNull);
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
          final halloweenTime = SeasonalDateRanges.halloweenStart.add(
            const Duration(days: 1),
          );

          testHelpers.stubHalloweenQuery(
            ids: ['h1', 'h2', 'h3', 'h4', 'h5'],
            hasMore: false,
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

        testHelpers.stubBestJokesQuery(ids: ['b1', 'b2', 'b3'], hasMore: false);

        final scope = createContainer(clock: () => notHalloweenTime);
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        // Should load from best jokes (composite), not Halloween
        expect(loadedIds, ['b1', 'b2', 'b3']);
      });

      test('marks Halloween as done when hasMore is false', () async {
        final halloweenTime = SeasonalDateRanges.halloweenStart.add(
          const Duration(days: 1),
        );

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
        final scope = ProviderContainer(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            settingsServiceProvider.overrideWithValue(SettingsService(prefs)),
            jokeRepositoryProvider.overrideWithValue(mockRepository),
            appUsageServiceProvider.overrideWithValue(mockAppUsageService),
            firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
            clockProvider.overrideWithValue(clock),
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
        scope.dispose();
      });

      test('skips today joke when already shown today', () async {
        final testTime = DateTime(2025, 1, 15);

        // Set today's date in settings
        final todayStr = '2025-01-15';
        await prefs.setString('today_joke_last_date', todayStr);

        testHelpers.stubBestJokesQuery(ids: ['b1', 'b2'], hasMore: false);

        final scope = createContainer(clock: () => testTime);
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        // Should load from best jokes, not today's joke
        expect(loadedIds, ['b1', 'b2']);
      });
    });
  });

  group('Composite Sources', () {
    test(
      'loads from best jokes source when only best jokes is active',
      () async {
        // Disable priority sources
        final cursor = _compositeCursor(
          prioritySourceCursors: {
            'priority_halloween_jokes': kPriorityDoneSentinel,
            'priority_today_joke': kPriorityDoneSentinel,
          },
        );
        await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

        testHelpers.stubBestJokesQuery(
          ids: ['b1', 'b2', 'b3', 'b4', 'b5'],
          hasMore: false,
        );

        final scope = createContainer();
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        expect(loadedIds, everyElement(startsWith('b')));
        expect(state.hasMore, isFalse);
      },
    );

    test('interleaves best jokes and random when both are active', () async {
      final randomMin = CompositeJokeSourceBoundaries.randomMinIndex;
      final cursor = _compositeCursor(
        totalJokesLoaded: randomMin,
        subSourceCursors: {
          'best_jokes': _cursorJson('best-cursor', 10.0),
          'all_jokes_random': _cursorJson('random-cursor', 5.0),
        },
        prioritySourceCursors: {
          'priority_halloween_jokes': kPriorityDoneSentinel,
          'priority_today_joke': kPriorityDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      testHelpers.stubBestJokesQuery(ids: ['b1', 'b2'], hasMore: false);
      testHelpers.stubRandomJokesQuery(ids: ['r1', 'r2'], hasMore: false);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should interleave: b1, r1, b2, r2
      expect(loadedIds.length, 4);
      expect(loadedIds, contains('b1'));
      expect(loadedIds, contains('r1'));
    });

    test(
      'interleaves random and public timestamp when both are active',
      () async {
        // At totalJokesLoaded = 200, best_jokes stops (maxIndex exclusive)
        // but random (10-500) and public_timestamp (200+) are both active
        final publicMin = CompositeJokeSourceBoundaries.publicMinIndex;
        final cursor = _compositeCursor(
          totalJokesLoaded: publicMin,
          subSourceCursors: {
            'all_jokes_random': _cursorJson('random-cursor', 5.0),
            'all_jokes_public_timestamp': _cursorJson('public-cursor', 100.0),
          },
          prioritySourceCursors: {
            'priority_halloween_jokes': kPriorityDoneSentinel,
            'priority_today_joke': kPriorityDoneSentinel,
          },
        );
        await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

        // Stub random jokes - returns 3 jokes
        testHelpers.stubRandomJokesQuery(
          ids: ['r1', 'r2', 'r3'],
          cursor: _cursorJson('random-cursor', 5.0),
          hasMore: true,
        );

        // Stub public timestamp jokes - returns 2 jokes
        testHelpers.stubPublicTimestampQuery(
          ids: ['p1', 'p2'],
          cursor: _cursorJson('public-cursor', 100.0),
          hasMore: true,
        );

        final scope = createContainer();
        final notifier = scope.read(
          compositeJokePagingProviders.paging.notifier,
        );

        await notifier.loadFirstPage();
        await _waitForLoading(scope);

        final state = scope.read(compositeJokePagingProviders.paging);
        final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

        // Should interleave: r1, p1, r2, p2, r3 (round-robin order)
        expect(loadedIds.length, 5);
        expect(loadedIds[0], 'r1');
        expect(loadedIds[1], 'p1');
        expect(loadedIds[2], 'r2');
        expect(loadedIds[3], 'p2');
        expect(loadedIds[4], 'r3');

        // Verify all sources contributed
        expect(loadedIds, containsAll(['r1', 'r2', 'r3']));
        expect(loadedIds, containsAll(['p1', 'p2']));
        expect(
          loadedIds,
          everyElement(isNot(startsWith('b'))),
        ); // No best jokes
      },
    );

    test('handles pagination with hasMore true', () async {
      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kPriorityDoneSentinel,
          'priority_today_joke': kPriorityDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      final firstPageCursor = JokeListPageCursor(orderValue: 2.0, docId: 'b2');

      // First call: hasMore true, returns cursor for next page
      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: JokeField.savedFraction,
          orderDirection: OrderDirection.descending,
          limit: any(named: 'limit'),
          cursor: any(that: isNull, named: 'cursor'),
        ),
      ).thenAnswer(
        (_) async => JokeListPage(
          ids: ['b1', 'b2'],
          cursor: firstPageCursor,
          hasMore: true,
          jokes: ['b1', 'b2'].map(_buildJoke).toList(),
        ),
      );

      // Second call with cursor: hasMore false
      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: JokeField.savedFraction,
          orderDirection: OrderDirection.descending,
          limit: any(named: 'limit'),
          cursor: any(
            that: predicate<JokeListPageCursor?>(
              (c) => c != null && c.docId == 'b2',
            ),
            named: 'cursor',
          ),
        ),
      ).thenAnswer(
        (_) async => JokeListPage(
          ids: ['b3'],
          cursor: null,
          hasMore: false,
          jokes: ['b3'].map(_buildJoke).toList(),
        ),
      );

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      await notifier.loadMore();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, containsAll(['b1', 'b2', 'b3']));
    });

    test('filters out viewed jokes', () async {
      final cursor = _compositeCursor(
        prioritySourceCursors: {
          'priority_halloween_jokes': kPriorityDoneSentinel,
          'priority_today_joke': kPriorityDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: JokeField.savedFraction,
          orderDirection: OrderDirection.descending,
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer(
        _stubOnceSource(ids: ['b1', 'b2', 'b3'], cursor: null, hasMore: false),
      );

      // Mark b2 as viewed
      final scope = createContainer(viewedJokes: {'b2': true});
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      expect(loadedIds, containsAll(['b1', 'b3']));
      expect(loadedIds, isNot(contains('b2')));
    });

    test('handles boundary crossing at random min index', () async {
      final randomMin = CompositeJokeSourceBoundaries.randomMinIndex;
      // Start at index 7, just before random boundary at 10
      // Requesting jokes would cross the boundary, so effectiveLimit should be 3
      final cursor = _compositeCursor(
        totalJokesLoaded: randomMin - 3,
        subSourceCursors: {'best_jokes': _cursorJson('best-cursor', 5.0)},
        prioritySourceCursors: {
          'priority_halloween_jokes': kPriorityDoneSentinel,
          'priority_today_joke': kPriorityDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      // Catch-all stub for any other calls (auto-load, random, etc.) - put first
      // so specific stubs below take precedence
      when(
        () => mockRepository.getFilteredJokePage(
          filters: any(named: 'filters'),
          orderByField: any(named: 'orderByField'),
          orderDirection: any(named: 'orderDirection'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).thenAnswer(
        (_) async => JokeListPage(
          ids: const [],
          cursor: null,
          hasMore: false,
          jokes: const [],
        ),
      );

      // First load: effectiveLimit should be adjusted to 3 (stopping at index 10)
      // Only best_jokes is active (random starts at 10)
      // This specific stub should take precedence over the catch-all
      testHelpers.stubBestJokesQuery(
        ids: ['b1', 'b2', 'b3'],
        cursor: _cursorJson('best-cursor', 5.0),
        hasMore: false, // Stop auto-loading
      );

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      // First load - should stop at boundary (index 10)
      // The calculateEffectiveLimit should limit to 3 jokes to stop exactly at index 10
      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should have exactly 3 jokes (stopped at boundary, not the full requested amount)
      // Starting at index 7, effectiveLimit should be 3 to stop exactly at index 10
      expect(loadedIds.length, 3);
      expect(loadedIds, everyElement(startsWith('b')));
      expect(loadedIds, containsAll(['b1', 'b2', 'b3']));
      // Verify only best_jokes loaded (random not active yet at index < 10)
      expect(loadedIds, everyElement(isNot(startsWith('r'))));

      // Verify boundary crossing: the effectiveLimit was adjusted from the requested
      // amount to 3, stopping exactly at the random min index boundary (10)
      // This is verified by having exactly 3 jokes loaded when starting at index 7
    });

    test('stops best jokes at max index', () async {
      final bestMax = CompositeJokeSourceBoundaries.bestJokesMaxIndex;
      final cursor = _compositeCursor(
        totalJokesLoaded: bestMax,
        prioritySourceCursors: {
          'priority_halloween_jokes': kPriorityDoneSentinel,
          'priority_today_joke': kPriorityDoneSentinel,
        },
      );
      await prefs.setString(compositeJokeCursorPrefsKey, cursor.encode());

      // Only random and public should load (best jokes out of range)
      testHelpers.stubRandomJokesQuery(ids: ['r1'], hasMore: false);
      testHelpers.stubPublicTimestampQuery(ids: ['p1'], hasMore: false);

      final scope = createContainer();
      final notifier = scope.read(compositeJokePagingProviders.paging.notifier);

      await notifier.loadFirstPage();
      await _waitForLoading(scope);

      final state = scope.read(compositeJokePagingProviders.paging);
      final loadedIds = state.loadedJokes.map((j) => j.joke.id).toList();

      // Should not load best jokes (out of range)
      expect(loadedIds, containsAll(['r1', 'p1']));
      expect(loadedIds, everyElement(isNot(startsWith('b'))));
    });
  });

  group('Priority + Composite Interaction', () {
    test(
      'priority source loads first, then switches to composite when done',
      () async {
        final halloweenTime = DateTime(2025, 10, 31);

        testHelpers.stubHalloweenQuery(ids: ['h1'], hasMore: false);
        testHelpers.stubBestJokesQuery(ids: ['b1'], hasMore: false);

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
        expect(loadedIds, contains('b1'));
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
