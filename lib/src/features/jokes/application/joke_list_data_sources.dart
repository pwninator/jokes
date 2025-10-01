import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart'
    show JokeListPageCursor;
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

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

final _userJokeSearchProviders = createSearchPagingProviders(
  scope: SearchScope.userJokeSearch,
);

final _dailyJokesPagingProviders = createDailyJokesPagingProviders();

/// Active category selection for Discover. Changing this resets the unified
/// category data source via its reset trigger.
final activeCategoryProvider = StateProvider<JokeCategory?>((ref) => null);

final _categoryPagingProviders = createPagingProviders(
  loadPage: _loadCategoryPage,
  resetTriggers: [
    ResetTrigger(
      provider: activeCategoryProvider,
      shouldReset: (prev, next) =>
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

String _serializePopularCursor(JokeListPageCursor cursor) {
  // Compact JSON to avoid delimiter issues
  return jsonEncode({'o': cursor.orderValue, 'd': cursor.docId});
}

JokeListPageCursor _deserializePopularCursor(String cursor) {
  final Map<String, dynamic> data = jsonDecode(cursor) as Map<String, dynamic>;
  return JokeListPageCursor(
    orderValue: data['o'] as Object,
    docId: data['d'] as String,
  );
}

/// Creates a scope-specific set of paging providers for search
PagingProviderBundle createSearchPagingProviders({
  required SearchScope scope,
  int initialPageSize = 2,
  int loadPageSize = 5,
  int loadMoreThreshold = 5,
}) {
  return createPagingProviders(
    loadPage: _makeLoadSearchPage(scope),
    resetTriggers: [
      ResetTrigger(
        provider: searchQueryProvider(scope),
        shouldReset: (prev, next) =>
            (prev as SearchQuery?)?.query != (next as SearchQuery).query,
      ),
    ],
    // Scope-specific analytics source label
    errorAnalyticsSource: 'search:${scope.name}',
    initialPageSize: initialPageSize,
    loadPageSize: loadPageSize,
    loadMoreThreshold: loadMoreThreshold,
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

PagingProviderBundle createDailyJokesPagingProviders({
  int initialPageSize = 5,
  int loadPageSize = 10,
  int loadMoreThreshold = 10,
}) {
  return createPagingProviders(
    loadPage: _loadDailyJokesPage,
    resetTriggers: const [],
    errorAnalyticsSource: 'daily_jokes',
    initialPageSize: initialPageSize,
    loadPageSize: loadPageSize,
    loadMoreThreshold: loadMoreThreshold,
  );
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

  AppLogger.debug(
    'PAGINATION: Loaded daily jokes page with cursor "$cursor", fetched ${jokesWithDates.length} jokes, next cursor: "$nextCursor"',
  );
  return PageResult(jokes: jokesWithDates, cursor: nextCursor, hasMore: true);
}
