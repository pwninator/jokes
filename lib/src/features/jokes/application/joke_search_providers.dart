import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';

/// Scope for search providers
enum SearchScope {
  userJokeSearch,
  category,
  jokeManagementSearch,
  jokeDeepResearch,
}

/// Label for search queries to provide additional context
enum SearchLabel { none, similarJokes, category }

// Search query state: strongly typed object
class SearchQuery {
  final String query;
  final int maxResults;
  final bool publicOnly;
  final MatchMode matchMode;
  final List<String> excludeJokeIds;
  final SearchLabel label;
  final bool logTrace;

  const SearchQuery({
    required this.query,
    required this.maxResults,
    required this.publicOnly,
    required this.matchMode,
    this.excludeJokeIds = const [],
    this.label = SearchLabel.none,
    this.logTrace = true,
  });

  SearchQuery copyWith({
    String? query,
    int? maxResults,
    bool? publicOnly,
    MatchMode? matchMode,
    List<String>? excludeJokeIds,
    SearchLabel? label,
    bool? logTrace,
  }) {
    return SearchQuery(
      query: query ?? this.query,
      maxResults: maxResults ?? this.maxResults,
      publicOnly: publicOnly ?? this.publicOnly,
      matchMode: matchMode ?? this.matchMode,
      excludeJokeIds: excludeJokeIds ?? this.excludeJokeIds,
      label: label ?? this.label,
      logTrace: logTrace ?? this.logTrace,
    );
  }
}

// Centralized default for an empty search query
const SearchQuery kEmptySearchQuery = SearchQuery(
  query: '',
  maxResults: 50,
  publicOnly: true,
  matchMode: MatchMode.tight,
);

final searchQueryProvider = StateProvider.family<SearchQuery, SearchScope>((
  ref,
  scope,
) {
  // Single default for empty search; screens set scope-specific params on submit
  return kEmptySearchQuery;
});

// Provider that calls the search_jokes cloud function and returns list of IDs
final searchResultIdsProvider =
    FutureProvider.family<List<JokeSearchResult>, SearchScope>((
      ref,
      scope,
    ) async {
      final params = ref.watch(searchQueryProvider(scope));
      final query = params.query.trim();
      if (query.length < 2) return <JokeSearchResult>[];

      // Start performance trace for similar search
      final perf = params.logTrace
          ? ref.read(performanceServiceProvider)
          : null;
      perf?.startNamedTrace(
        name: TraceName.searchToFirstImage,
        attributes: {'query_type': scope.name},
      );

      final service = ref.watch(jokeCloudFunctionServiceProvider);
      final results = await service.searchJokes(
        searchQuery: query,
        maxResults: params.maxResults,
        publicOnly: params.publicOnly,
        matchMode: params.matchMode,
        scope: scope,
        excludeJokeIds: params.excludeJokeIds,
        label: params.label,
      );

      // Log analytics for user scope
      if (scope == SearchScope.userJokeSearch) {
        final analyticsService = ref.read(analyticsServiceProvider);
        analyticsService.logJokeSearch(
          queryLength: query.length,
          scope: params.label != SearchLabel.none
              ? "${scope.name}:${params.label.name}"
              : scope.name,
          resultsCount: results.length,
        );
      }

      // Update performance trace with result_count if a trace is active
      perf?.putNamedTraceAttributes(
        name: TraceName.searchToFirstImage,
        attributes: {'result_count': results.length.toString()},
      );
      if (results.isEmpty) {
        // No image will appear; stop now so empty searches are recorded
        perf?.stopNamedTrace(name: TraceName.searchToFirstImage);
      }

      return results;
    });

// Live search results that react to per-joke updates
class JokeWithVectorDistance {
  final Joke joke;
  final double? vectorDistance; // null when not from search
  const JokeWithVectorDistance({required this.joke, this.vectorDistance});
}

final searchResultsLiveProvider =
    Provider.family<AsyncValue<List<JokeWithVectorDistance>>, SearchScope>((
      ref,
      scope,
    ) {
      final resultsAsync = ref.watch(searchResultIdsProvider(scope));

      // Propagate loading/error from ids fetch
      if (resultsAsync.isLoading) {
        return const AsyncValue.loading();
      }
      if (resultsAsync.hasError) {
        return AsyncValue.error(
          resultsAsync.error!,
          resultsAsync.stackTrace ?? StackTrace.current,
        );
      }

      final results = resultsAsync.value ?? const <JokeSearchResult>[];
      if (results.isEmpty) {
        return const AsyncValue.data(<JokeWithVectorDistance>[]);
      }

      // Watch each joke by id
      final perJoke = <AsyncValue<Joke?>>[];
      for (final r in results) {
        perJoke.add(ref.watch(jokeStreamByIdProvider(r.id)));
      }

      // If any still loading, show loading to keep UX consistent with other lists
      if (perJoke.any((j) => j.isLoading)) {
        return const AsyncValue.loading();
      }
      // Surface first error if any
      final firstError = perJoke.firstWhere(
        (j) => j.hasError,
        orElse: () => const AsyncValue.data(null),
      );
      if (firstError.hasError) {
        return AsyncValue.error(
          firstError.error!,
          firstError.stackTrace ?? StackTrace.current,
        );
      }

      // Build ordered list based on ids, skipping nulls
      var ordered = <JokeWithVectorDistance>[];
      for (var i = 0; i < results.length; i++) {
        final value = perJoke[i].value;
        if (value != null) {
          ordered.add(
            JokeWithVectorDistance(
              joke: value,
              vectorDistance: results[i].vectorDistance,
            ),
          );
        }
      }

      // Apply admin filters only for admin scope
      if (scope == SearchScope.jokeManagementSearch) {
        final filterState = ref.watch(jokeFilterProvider);

        // 1) State filter (filter by selected states if any are selected)
        if (filterState.hasStateFilter) {
          ordered = ordered.where((jvd) {
            return jvd.joke.state != null &&
                filterState.selectedStates.contains(jvd.joke.state!);
          }).toList();
        }

        // note: do not apply popular sorting here; handled globally below
      }

      return AsyncValue.data(ordered);
    });
