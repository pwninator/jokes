import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/application/generic_paging_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

/// All providers for category search paging
final categorySearch = createPagingProviders(
  loadPage: _loadSearchPage,
  resetTriggers: [
    ResetTrigger(
      provider: searchQueryProvider(SearchScope.category),
      shouldReset: (prev, next) =>
          (prev as SearchQuery?)?.query != (next as SearchQuery).query,
    ),
  ],
  errorAnalyticsSource: 'category_search',
  initialPageSize: 2,
  loadPageSize: 5,
  loadMoreThreshold: 5,
);

/// Data source for category search
class CategorySearchDataSource extends PagingDataSource {
  CategorySearchDataSource(WidgetRef ref) : super(ref, categorySearch);
}

/// Loads a page of search results and converts them to JokeWithDate objects
/// This uses a two-phase approach: searchResultIdsProvider caches all IDs from the
/// search, then we paginate by fetching joke data in batches.
Future<PageResult> _loadSearchPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGINATION: Loading search page with limit: $limit, cursor: $cursor',
  );

  // Get all search result IDs from the cached provider
  final allResults = await ref.read(
    searchResultIdsProvider(SearchScope.category).future,
  );

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
  // if (pageIds.isEmpty) {

  final repository = ref.read(jokeRepositoryProvider);
  final jokes = await repository.getJokesByIds(pageIds);
  final jokesWithDate = jokes.map((j) => JokeWithDate(joke: j)).toList();

  // Calculate next cursor and hasMore
  final nextOffset = offset + limit;
  final hasMore = nextOffset < allResults.length;

  AppLogger.debug(
    'PAGINATION: Loaded page at offset $offset, '
    'fetched ${pageIds.length} jokes, '
    'total results: ${allResults.length}, '
    'hasMore: $hasMore',
  );

  return PageResult(
    jokes: jokesWithDate,
    cursor: hasMore ? nextOffset.toString() : null,
    hasMore: hasMore,
    totalCount: allResults.length,
  );
}
