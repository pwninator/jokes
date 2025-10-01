import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/application/generic_paging_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

/// Data source for category search
class CategorySearchDataSource extends PagingDataSource {
  CategorySearchDataSource(WidgetRef ref) : super(ref, _categorySearch);
}

/// Data source for user joke search
class UserJokeSearchDataSource extends PagingDataSource {
  UserJokeSearchDataSource(WidgetRef ref) : super(ref, _userJokeSearch);
}

// Predefined provider bundles for common scopes
final _categorySearch = createSearchPagingProviders(
  scope: SearchScope.category,
);
final _userJokeSearch = createSearchPagingProviders(
  scope: SearchScope.userJokeSearch,
);

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
      'PAGINATION: Loaded page at offset $offset, fetched ${pageIds.length} jokes, total results: ${allResults.length}, hasMore: $hasMore',
    );

    return PageResult(
      jokes: jokesWithDate,
      cursor: hasMore ? nextOffset.toString() : null,
      hasMore: hasMore,
      totalCount: allResults.length,
    );
  };
}
