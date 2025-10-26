import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart'
    show JokeField, JokeFilter, JokeListPageCursor, OrderDirection;
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

/// Signal provider that triggers stale joke checks for daily jokes.
/// Incremented by DailyJokesScreen when it wants to trigger a check.
final dailyJokesCheckNowProvider = StateProvider<int>((ref) => 0);

/// Tracks the last date we performed a reset of the daily jokes list.
/// Used to ensure we only reset once per day to avoid thrashing.
final dailyJokesLastResetDateProvider = StateProvider<DateTime?>((ref) => null);

/// Tracks the date of the most recent daily joke.
final dailyJokesMostRecentDateProvider = StateProvider<DateTime?>(
  (ref) => null,
);

/// Signal used to invalidate saved jokes paging data.
/// Increment the value to trigger a refresh of saved jokes data sources.
final savedJokesRefreshTriggerProvider = StateProvider<int>((ref) => 0);

/// Data source for daily jokes loaded from monthly schedule batches
class DailyJokesDataSource extends JokeListDataSource {
  DailyJokesDataSource(WidgetRef ref) : super(ref, _dailyJokesPagingProviders);
}

/// Data source for user joke search
class UserJokeSearchDataSource extends JokeListDataSource {
  UserJokeSearchDataSource(WidgetRef ref)
    : super(ref, _userJokeSearchProviders);
}

/// Unified category data source that routes to search vs. popular loaders
/// based on the currently active category.
class CategoryDataSource extends JokeListDataSource {
  CategoryDataSource(WidgetRef ref) : super(ref, _categoryPagingProviders);
}

/// Data source for saved jokes with incremental loading
class SavedJokesDataSource extends JokeListDataSource {
  SavedJokesDataSource(WidgetRef ref) : super(ref, _savedJokesPagingProviders);
}

/// Composite feed that sequences through multiple joke sources.
class CompositeJokeDataSource extends JokeListDataSource {
  CompositeJokeDataSource(WidgetRef ref)
    : super(ref, compositeJokePagingProviders);
}

final _userJokeSearchProviders = createPagingProviders(
  loadPage: _makeLoadSearchPage(SearchScope.userJokeSearch),
  resetTriggers: [
    ResetTrigger(
      provider: searchQueryProvider(SearchScope.userJokeSearch),
      shouldReset: (ref, prev, next) =>
          (prev as SearchQuery?)?.query != (next as SearchQuery).query,
    ),
  ],
  // Scope-specific analytics source label
  errorAnalyticsSource: 'search:${SearchScope.userJokeSearch.name}',
  initialPageSize: 2,
  loadPageSize: 5,
  loadMoreThreshold: 5,
);

final PagingProviderBundle _dailyJokesPagingProviders = createPagingProviders(
  loadPage: loadDailyJokesPage,
  resetTriggers: [
    ResetTrigger(
      provider: dailyJokesCheckNowProvider,
      shouldReset: shouldResetDailyJokesForStaleData,
    ),
  ],
  errorAnalyticsSource: 'daily_jokes',
  initialPageSize: 5,
  loadPageSize: 10,
  loadMoreThreshold: 10,
);

final _savedJokesPagingProviders = createPagingProviders(
  loadPage: _loadSavedJokesPage,
  resetTriggers: [
    ResetTrigger(
      provider: savedJokesRefreshTriggerProvider,
      shouldReset: (_, prev, next) {
        if (prev == null) return false;
        return prev != next;
      },
    ),
  ],

  errorAnalyticsSource: 'saved_jokes',
  initialPageSize: 3,
  loadPageSize: 10,
  loadMoreThreshold: 5,
);

/// Shared preferences key for persisting the composite feed cursor.
const compositeJokeCursorPrefsKey = 'composite_joke_cursor';
const _popularCompositeLimit = 10;

final compositeJokePagingProviders = createPagingProviders(
  loadPage: _loadCompositeJokePage,
  resetTriggers: const [],
  errorAnalyticsSource: 'composite_jokes',
  initialPageSize: 6,
  loadPageSize: 12,
  loadMoreThreshold: 0,
  initialCursorProvider: (ref) {
    final settings = ref.read(settingsServiceProvider);
    return settings.getString(compositeJokeCursorPrefsKey);
  },
  onCursorChanged: (ref, cursor) {
    /// Never clear the saved cursor.
    if (cursor == null || cursor.isEmpty) return;
    final settings = ref.read(settingsServiceProvider);
    unawaited(settings.setString(compositeJokeCursorPrefsKey, cursor));
  },
);

class CompositeJokeSubSource {
  const CompositeJokeSubSource({required this.id, required this.load});

  final String id;
  final Future<CompositeSubSourcePage> Function(
    Ref ref,
    int limit,
    CompositeCursor? cursor,
  )
  load;
}

class CompositeSubSourcePage {
  const CompositeSubSourcePage({
    required this.jokes,
    required this.hasMore,
    required this.nextCursor,
  });

  final List<JokeWithDate> jokes;
  final bool hasMore;
  final CompositeCursor? nextCursor;

  /// This sub source has no more jokes to load.
  /// When this is returned, move to the next sub source.
  static const empty = CompositeSubSourcePage(
    jokes: <JokeWithDate>[],
    hasMore: false,
    nextCursor: null,
  );
}

class CompositeCursor {
  const CompositeCursor({required this.sourceId, this.payload});

  final String sourceId;
  final Map<String, dynamic>? payload;

  String encode() {
    return jsonEncode({
      'source': sourceId,
      if (payload != null) 'payload': payload,
    });
  }

  static CompositeCursor? decode(String? encoded) {
    if (encoded == null || encoded.isEmpty) return null;
    try {
      final Map<String, dynamic> data =
          jsonDecode(encoded) as Map<String, dynamic>;
      final source = data['source'] as String?;
      if (source == null) return null;
      final payload = data['payload'];
      return CompositeCursor(
        sourceId: source,
        payload: payload is Map<String, dynamic>
            ? Map<String, dynamic>.from(payload)
            : null,
      );
    } catch (_) {
      return null;
    }
  }
}

final List<CompositeJokeSubSource> _compositeSubSources = [
  CompositeJokeSubSource(
    id: 'most_popular',
    load: _loadPopularCompositeSubSource,
  ),
  CompositeJokeSubSource(
    id: 'all_jokes_random',
    load: _loadRandomCompositeSubSource,
  ),
  CompositeJokeSubSource(
    id: 'all_jokes_public_timestamp',
    load: _loadPublicTimestampCompositeSubSource,
  ),
];

Future<CompositeSubSourcePage> _loadPopularCompositeSubSource(
  Ref ref,
  int limit,
  CompositeCursor? cursor,
) async {
  final payload = cursor?.payload;
  final consumed = (payload?['count'] as num?)?.toInt() ?? 0;
  if (consumed >= _popularCompositeLimit) {
    return CompositeSubSourcePage.empty;
  }

  final remaining = _popularCompositeLimit - consumed;
  final fetchLimit = math.min(limit, remaining);
  if (fetchLimit <= 0) {
    return CompositeSubSourcePage.empty;
  }

  final pageCursor = payload?['cursor'] as String?;
  final page = await _loadPopularCategoryPage(ref, fetchLimit, pageCursor);

  final newCount = consumed + page.jokes.length;
  final bool hasMoreWithinTop =
      page.hasMore && newCount < _popularCompositeLimit;

  final nextCursor = hasMoreWithinTop
      ? CompositeCursor(
          sourceId: 'most_popular',
          payload: {
            'count': newCount,
            if (page.cursor != null) 'cursor': page.cursor,
          },
        )
      : null;

  return CompositeSubSourcePage(
    jokes: page.jokes,
    hasMore: hasMoreWithinTop,
    nextCursor: nextCursor,
  );
}

Future<CompositeSubSourcePage> _loadRandomCompositeSubSource(
  Ref ref,
  int limit,
  CompositeCursor? cursor,
) async {
  final payload = cursor?.payload;
  final page = await _loadOrderedJokesPage(
    ref,
    limit,
    payload?['cursor'] as String?,
    orderByField: JokeField.randomId,
    descending: false,
  );

  return CompositeSubSourcePage(
    jokes: page.jokes,
    hasMore: page.hasMore,
    nextCursor: page.cursor == null
        ? null
        : CompositeCursor(
            sourceId: 'all_jokes_random',
            payload: {'cursor': page.cursor},
          ),
  );
}

Future<CompositeSubSourcePage> _loadPublicTimestampCompositeSubSource(
  Ref ref,
  int limit,
  CompositeCursor? cursor,
) async {
  final payload = cursor?.payload;
  final page = await _loadOrderedJokesPage(
    ref,
    limit,
    payload?['cursor'] as String?,
    orderByField: JokeField.publicTimestamp,
    descending: false,
  );

  return CompositeSubSourcePage(
    jokes: page.jokes,
    hasMore: page.hasMore,
    nextCursor: page.cursor == null
        ? null
        : CompositeCursor(
            sourceId: 'all_jokes_public_timestamp',
            payload: {'cursor': page.cursor},
          ),
  );
}

Future<PageResult> _loadCompositeJokePage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  CompositeCursor? currentCursor = CompositeCursor.decode(cursor);
  int currentIndex = 0;

  if (currentCursor != null) {
    final index = _compositeSubSources.indexWhere(
      (source) => source.id == currentCursor!.sourceId,
    );
    if (index >= 0) {
      currentIndex = index;
    }
  }

  final collected = <JokeWithDate>[];
  String? nextCursorEncoded;
  bool hasMore = false;
  String? cursorSignature = currentCursor?.encode();
  bool terminatedEarly = false;

  while (currentIndex < _compositeSubSources.length) {
    if (collected.length >= limit) {
      hasMore = true;
      nextCursorEncoded = currentCursor?.encode();
      break;
    }

    final subSource = _compositeSubSources[currentIndex];
    final remaining = limit - collected.length;
    final cursorForSource =
        (currentCursor != null && currentCursor.sourceId == subSource.id)
        ? currentCursor
        : null;
    final page = await subSource.load(ref, remaining, cursorForSource);
    collected.addAll(page.jokes);

    if (page.hasMore) {
      final nextCursor = page.nextCursor;
      final nextSignature = nextCursor?.encode();
      if (page.jokes.isEmpty && nextSignature == cursorSignature) {
        // Avoid tight loops if the sub-source reports progress without data.
        hasMore = false;
        nextCursorEncoded = null;
        terminatedEarly = true;
        break;
      }
      currentCursor = nextCursor;
      cursorSignature = nextSignature;
      hasMore = true;

      if (collected.length >= limit) {
        nextCursorEncoded = nextCursor?.encode();
        break;
      }
      continue;
    }

    currentIndex += 1;
    currentCursor = null;
    cursorSignature = null;
  }

  if (!terminatedEarly &&
      nextCursorEncoded == null &&
      currentIndex < _compositeSubSources.length) {
    hasMore = true;
    final nextCursor =
        currentCursor ??
        CompositeCursor(sourceId: _compositeSubSources[currentIndex].id);
    nextCursorEncoded = nextCursor.encode();
  }

  if (currentIndex >= _compositeSubSources.length) {
    hasMore = false;
    nextCursorEncoded = null;
  }

  return PageResult(
    jokes: collected,
    cursor: nextCursorEncoded,
    hasMore: hasMore,
  );
}

Future<PageResult> _loadOrderedJokesPage(
  Ref ref,
  int limit,
  String? cursor, {
  required JokeField orderByField,
  required bool descending,
}) async {
  final repository = ref.read(jokeRepositoryProvider);
  final pageCursor = cursor != null
      ? JokeListPageCursor.deserialize(cursor)
      : null;

  final filters = <JokeFilter>[
    JokeFilter.whereInValues(JokeField.state, [
      JokeState.published.value,
      JokeState.daily.value,
    ]),
  ];
  final page = await repository.getFilteredJokePage(
    filters: filters,
    orderByField: orderByField,
    orderDirection: descending
        ? OrderDirection.descending
        : OrderDirection.ascending,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  final jokes = await repository.getJokesByIds(page.ids);
  final now = DateTime.now();
  final filtered = jokes.where((joke) {
    final timestamp = joke.publicTimestamp;
    if (timestamp == null) return false;
    return !timestamp.isAfter(now);
  }).toList();
  final jokesWithDate = _filterJokesWithImages(filtered);

  final nextCursor = page.cursor?.serialize();

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

List<JokeWithDate> _filterJokesWithImages(List<Joke> jokes) {
  return jokes
      .where(
        (j) =>
            (j.setupImageUrl != null && j.setupImageUrl!.isNotEmpty) &&
            (j.punchlineImageUrl != null && j.punchlineImageUrl!.isNotEmpty),
      )
      .map((j) => JokeWithDate(joke: j))
      .toList();
}

/// Active category selection for Discover. Changing this resets the unified
/// category data source via its reset trigger.
final activeCategoryProvider = StateProvider<JokeCategory?>((ref) => null);

final _categoryPagingProviders = createPagingProviders(
  loadPage: _loadCategoryPage,
  resetTriggers: [
    ResetTrigger(
      provider: activeCategoryProvider,
      shouldReset: (ref, prev, next) =>
          (prev as JokeCategory?)?.id != (next as JokeCategory?)?.id,
    ),
  ],
  errorAnalyticsSource: 'category',
  initialPageSize: 2,
  loadPageSize: 5,
  loadMoreThreshold: 5,
);

Future<PageResult> _loadCategoryPage(Ref ref, int limit, String? cursor) async {
  final category = ref.read(activeCategoryProvider);
  if (category == null) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }
  switch (category.type) {
    case CategoryType.search:
      return _makeLoadSearchPage(SearchScope.category)(ref, limit, cursor);
    case CategoryType.popular:
      return _loadPopularCategoryPage(ref, limit, cursor);
    case CategoryType.seasonal:
      return _loadSeasonalCategoryPage(ref, limit, cursor);
    default:
      return const PageResult(jokes: [], cursor: null, hasMore: false);
  }
}

Future<PageResult> _loadPopularCategoryPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGINATION: Loading popular category page with limit: $limit, cursor: $cursor',
  );

  final repository = ref.read(jokeRepositoryProvider);

  // Deserialize cursor JSON if present
  final pageCursor = cursor != null
      ? JokeListPageCursor.deserialize(cursor)
      : null;

  final page = await repository.getFilteredJokePage(
    filters: [
      JokeFilter.whereInValues(JokeField.state, [
        JokeState.published.value,
        JokeState.daily.value,
      ]),
      JokeFilter.greaterThan(JokeField.popularityScore, 0.0),
    ],
    orderByField: JokeField.popularityScore,
    orderDirection: OrderDirection.descending,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Fetch full joke documents for the page
  final jokes = await repository.getJokesByIds(page.ids);

  // Require images
  final jokesWithDate = _filterJokesWithImages(jokes);

  final nextCursor = page.cursor?.serialize();

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

Future<PageResult> _loadSeasonalCategoryPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGINATION: Loading seasonal category page with limit: $limit, cursor: $cursor',
  );

  final category = ref.read(activeCategoryProvider);
  final seasonalValue = category?.seasonalValue?.trim();
  if (seasonalValue == null || seasonalValue.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  final repository = ref.read(jokeRepositoryProvider);

  final pageCursor = cursor != null
      ? JokeListPageCursor.deserialize(cursor)
      : null;

  final page = await repository.getFilteredJokePage(
    filters: [
      JokeFilter.whereInValues(JokeField.state, [
        JokeState.published.value,
        JokeState.daily.value,
      ]),
      JokeFilter.equals(JokeField.seasonal, seasonalValue),
      JokeFilter.lessThan(JokeField.publicTimestamp, DateTime.now()),
    ],
    orderByField: JokeField.publicTimestamp,
    orderDirection: OrderDirection.descending,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Fetch full joke documents for the page
  final jokes = await repository.getJokesByIds(page.ids);

  final jokesWithDate = _filterJokesWithImages(jokes);

  final nextCursor = page.cursor?.serialize();

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

/// Factory that returns a page loader bound to a specific SearchScope
Future<PageResult> Function(Ref ref, int limit, String? cursor)
_makeLoadSearchPage(SearchScope scope) {
  return (Ref ref, int limit, String? cursor) async {
    AppLogger.debug(
      'PAGINATION: Loading search page with limit: $limit, cursor: $cursor, scope: ${scope.name}',
    );

    // Get all search result IDs from the cached provider for this scope
    final allResults = await ref.read(searchResultIdsProvider(scope).future);

    if (allResults.isEmpty) {
      return const PageResult(
        jokes: [],
        cursor: null,
        hasMore: false,
        totalCount: 0,
      );
    }

    // Parse cursor as offset (0-based index into the full result set)
    final offset = cursor != null ? int.parse(cursor) : 0;

    // Slice the IDs for this page
    final pageResults = allResults.skip(offset).take(limit).toList();
    final pageIds = pageResults.map((r) => r.id).toList();

    // Fetch joke data only for this page
    final repository = ref.read(jokeRepositoryProvider);
    final jokes = await repository.getJokesByIds(pageIds);
    final jokesWithDate = jokes.map((j) => JokeWithDate(joke: j)).toList();

    // Calculate next cursor and hasMore
    final nextOffset = offset + limit;
    final hasMore = nextOffset < allResults.length;

    AppLogger.debug(
      'PAGINATION: Loaded search page at offset $offset, fetched ${pageIds.length} jokes, total results: ${allResults.length}, hasMore: $hasMore',
    );

    return PageResult(
      jokes: jokesWithDate,
      cursor: hasMore ? nextOffset.toString() : null,
      hasMore: hasMore,
      totalCount: allResults.length,
    );
  };
}

Future<PageResult> loadDailyJokesPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGINATION: Loading daily jokes page with limit: $limit, cursor: $cursor',
  );

  final repository = ref.read(jokeScheduleRepositoryProvider);

  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);

  // Determine target month to load
  final DateTime targetMonth;
  if (cursor == null) {
    targetMonth = DateTime(now.year, now.month);
  } else {
    final parts = cursor.split('_');
    final int year = int.parse(parts[0]);
    final int month = int.parse(parts[1]);
    targetMonth = DateTime(year, month);
  }

  // Fetch the batch for the target month
  final batch = await repository.getBatchForMonth(
    JokeConstants.defaultJokeScheduleId,
    targetMonth.year,
    targetMonth.month,
  );

  if (batch == null) {
    AppLogger.debug('PAGINATION: No batch for this month: $targetMonth');
    // No batch for this month: stop pagination
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Extract jokes from batch; sort by day descending (newest first)
  final jokesWithDates = <JokeWithDate>[];
  final sortedDays = batch.jokes.keys.toList()..sort((a, b) => b.compareTo(a));

  for (final dayKey in sortedDays) {
    final joke = batch.jokes[dayKey];
    if (joke == null) continue;

    final int? day = int.tryParse(dayKey);
    if (day == null) continue;

    final jokeDate = DateTime(batch.year, batch.month, day);
    final bool include = !jokeDate.isAfter(today);

    if (include &&
        joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty) {
      jokesWithDates.add(JokeWithDate(joke: joke, date: jokeDate));
    }
  }

  // Compute next cursor as previous month; keep paginating until no batch exists
  final previousMonth = DateTime(targetMonth.year, targetMonth.month - 1);
  final nextCursor = '${previousMonth.year}_${previousMonth.month.toString()}';

  // Update the most recent daily joke date
  if (jokesWithDates.isNotEmpty) {
    final mostRecentJokeDate = ref.read(dailyJokesMostRecentDateProvider);
    final firstJokeDate = jokesWithDates.first.date;
    if (firstJokeDate != null &&
        (mostRecentJokeDate == null ||
            firstJokeDate.isAfter(mostRecentJokeDate))) {
      ref.read(dailyJokesMostRecentDateProvider.notifier).state = firstJokeDate;
    }
  }

  AppLogger.debug(
    'PAGINATION: Loaded daily jokes page with cursor "$cursor", fetched ${jokesWithDates.length} jokes, next cursor: "$nextCursor"',
  );
  return PageResult(jokes: jokesWithDates, cursor: nextCursor, hasMore: true);
}

/// Determines if daily jokes should be reset due to stale data.
///
/// This function is called whenever the check signal is incremented.
/// It checks if the first loaded joke is stale (date < today) and
/// we haven't already reset today (to avoid thrashing).
bool shouldResetDailyJokesForStaleData(Ref ref, dynamic prev, dynamic next) {
  AppLogger.debug('PAGINATION: Checking if daily jokes should be reset');

  final today = getCurrentDate();
  final lastResetDate = ref.read(dailyJokesLastResetDateProvider);

  if (lastResetDate != null && !lastResetDate.isBefore(today)) {
    // Already reset today, don't reset
    return false;
  }

  final firstJokeDate = ref.read(dailyJokesMostRecentDateProvider);
  if (firstJokeDate == null) {
    // First joke has no date, don't reset
    return false;
  }

  final isStale = firstJokeDate.isBefore(today);
  if (!isStale) {
    // Not stale, don't reset
    return false;
  }

  AppLogger.debug(
    'PAGINATION: Resetting stale jokes. First joke date: $firstJokeDate, today: $today',
  );
  // Mark that we're resetting today to prevent multiple resets
  ref.read(dailyJokesLastResetDateProvider.notifier).state = today;
  return true;
}

Future<PageResult> _loadSavedJokesPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGINATION: Loading saved jokes page with limit: $limit, cursor: $cursor',
  );

  final appUsageService = ref.read(appUsageServiceProvider);
  final savedJokeIds = await appUsageService.getSavedJokeIds();

  if (savedJokeIds.isEmpty) {
    return const PageResult(
      jokes: [],
      cursor: null,
      hasMore: false,
      totalCount: 0,
    );
  }

  // Offset-based pagination (like search)
  final offset = cursor != null ? int.parse(cursor) : 0;
  final pageIds = savedJokeIds.skip(offset).take(limit).toList();

  // Fetch jokes for this page
  final repository = ref.read(jokeRepositoryProvider);
  final jokes = await repository.getJokesByIds(pageIds);

  // Create map for order preservation
  final jokeMap = <String, Joke>{};
  for (final joke in jokes) {
    jokeMap[joke.id] = joke;
  }

  // Build results in original order, filtering for images
  final jokesWithDate = <JokeWithDate>[];
  for (final id in pageIds) {
    final joke = jokeMap[id];
    if (joke != null &&
        joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty) {
      jokesWithDate.add(JokeWithDate(joke: joke));
    }
  }

  final nextOffset = offset + limit;
  final hasMore = nextOffset < savedJokeIds.length;

  AppLogger.debug(
    'PAGINATION: Loaded saved jokes page at offset $offset, fetched ${jokesWithDate.length} jokes, total saved: ${savedJokeIds.length}, hasMore: $hasMore',
  );

  return PageResult(
    jokes: jokesWithDate,
    cursor: hasMore ? nextOffset.toString() : null,
    hasMore: hasMore,
    totalCount: savedJokeIds.length,
  );
}

/// Get current date (midnight-normalized) for comparison
DateTime getCurrentDate() {
  final now = DateTime.now();
  return DateTime(now.year, now.month, now.day);
}
