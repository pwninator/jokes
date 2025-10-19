import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
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
    show JokeListPageCursor;
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

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
  loadPage: _loadDailyJokesPage,
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
  final pageCursor = cursor != null ? _deserializePopularCursor(cursor) : null;

  final page = await repository.getFilteredJokePage(
    states: {JokeState.published, JokeState.daily},
    popularOnly: true,
    // Need to be false due to the way the query works.
    // Technically only public jokes will be returned because they require user interaction.
    publicOnly: false,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Fetch full joke documents for the page
  final jokes = await repository.getJokesByIds(page.ids);

  // Require images
  final jokesWithDate = jokes
      .where(
        (j) =>
            (j.setupImageUrl != null && j.setupImageUrl!.isNotEmpty) &&
            (j.punchlineImageUrl != null && j.punchlineImageUrl!.isNotEmpty),
      )
      .map((j) => JokeWithDate(joke: j))
      .toList();

  final nextCursor = page.cursor != null
      ? _serializePopularCursor(page.cursor!)
      : null;

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

  final pageCursor = cursor != null ? _deserializePopularCursor(cursor) : null;

  final page = await repository.getFilteredJokePage(
    states: {JokeState.published, JokeState.daily},
    popularOnly: false,
    publicOnly: true,
    limit: limit,
    cursor: pageCursor,
    seasonalValue: seasonalValue,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Fetch full joke documents for the page
  final jokes = await repository.getJokesByIds(page.ids);

  // Require images
  final jokesWithDate = jokes
      .where(
        (j) =>
            (j.setupImageUrl != null && j.setupImageUrl!.isNotEmpty) &&
            (j.punchlineImageUrl != null && j.punchlineImageUrl!.isNotEmpty),
      )
      .map((j) => JokeWithDate(joke: j))
      .toList();

  final nextCursor = page.cursor != null
      ? _serializePopularCursor(page.cursor!)
      : null;

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

String _serializePopularCursor(JokeListPageCursor cursor) {
  // Compact JSON to avoid delimiter issues
  final Object encodedOrderValue;
  final o = cursor.orderValue;
  if (o is Timestamp) {
    // Encode Timestamp as millis to make it JSON encodable
    encodedOrderValue = {'ts': o.millisecondsSinceEpoch};
  } else {
    encodedOrderValue = o;
  }
  return jsonEncode({'o': encodedOrderValue, 'd': cursor.docId});
}

JokeListPageCursor _deserializePopularCursor(String cursor) {
  final Map<String, dynamic> data = jsonDecode(cursor) as Map<String, dynamic>;
  final dynamic raw = data['o'];
  Object orderValue;
  if (raw is Map && raw.containsKey('ts')) {
    final int millis = (raw['ts'] as num).toInt();
    orderValue = Timestamp.fromMillisecondsSinceEpoch(millis);
  } else {
    orderValue = raw as Object;
  }
  return JokeListPageCursor(orderValue: orderValue, docId: data['d'] as String);
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

Future<PageResult> _loadDailyJokesPage(
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
  final mostRecentJokeDate = ref.read(dailyJokesMostRecentDateProvider);
  final firstJokeDate = jokesWithDates.first.date;
  if (firstJokeDate != null &&
      (mostRecentJokeDate == null ||
          firstJokeDate.isAfter(mostRecentJokeDate))) {
    ref.read(dailyJokesMostRecentDateProvider.notifier).state = firstJokeDate;
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
