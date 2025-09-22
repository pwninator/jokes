import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';

/// Scope for search providers
enum SearchScope {
  userJokeSearch,
  jokeManagementSearch,
  jokeDeepResearchSearch,
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

  const SearchQuery({
    required this.query,
    required this.maxResults,
    required this.publicOnly,
    required this.matchMode,
    this.excludeJokeIds = const [],
    this.label = SearchLabel.none,
  });

  SearchQuery copyWith({
    String? query,
    int? maxResults,
    bool? publicOnly,
    MatchMode? matchMode,
    List<String>? excludeJokeIds,
    SearchLabel? label,
  }) {
    return SearchQuery(
      query: query ?? this.query,
      maxResults: maxResults ?? this.maxResults,
      publicOnly: publicOnly ?? this.publicOnly,
      matchMode: matchMode ?? this.matchMode,
      excludeJokeIds: excludeJokeIds ?? this.excludeJokeIds,
      label: label ?? this.label,
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

      return results;
    });

// Live search results that react to per-joke updates
class JokeWithVectorDistance {
  final Joke joke;
  final double? vectorDistance; // null when not from search
  const JokeWithVectorDistance({required this.joke, this.vectorDistance});
}

final searchResultsLiveProvider =
    StreamProvider.family<List<JokeWithVectorDistance>, SearchScope>((
  ref,
  scope,
) {
  final resultsAsync = ref.watch(searchResultIdsProvider(scope));

  if (resultsAsync.hasError) {
    return Stream.error(resultsAsync.error!);
  }
  if (!resultsAsync.hasValue) {
    return Stream.value([]);
  }

  final results = resultsAsync.value!;
  if (results.isEmpty) {
    return Stream.value([]);
  }

  final jokeIds = results.map((r) => r.id).toList();
  final jokesStream = ref.watch(jokesByIdsStreamProvider(jokeIds).stream);

  return jokesStream.map((jokes) {
    final jokeMap = {for (var joke in jokes) joke.id: joke};
    var ordered = <JokeWithVectorDistance>[];
    for (final result in results) {
      final joke = jokeMap[result.id];
      if (joke != null) {
        ordered.add(
          JokeWithVectorDistance(
            joke: joke,
            vectorDistance: result.vectorDistance,
          ),
        );
      }
    }

    // Apply admin filters only for admin scope
    if (scope == SearchScope.jokeManagementSearch) {
      final filterState = ref.watch(jokeFilterProvider);
      if (filterState.hasStateFilter) {
        ordered = ordered.where((jvd) {
          return jvd.joke.state != null &&
              filterState.selectedStates.contains(jvd.joke.state!);
        }).toList();
      }
    }

    return ordered;
  });
});

/// Search results adapted for the viewer (JokeWithDate, images only)
final searchResultsViewerProvider =
    StreamProvider.family<List<JokeWithDate>, SearchScope>((ref, scope) {
  final resultsAsync = ref.watch(searchResultIdsProvider(scope));

  if (resultsAsync.hasError) {
    return Stream.error(resultsAsync.error!);
  }
  if (!resultsAsync.hasValue) {
    return Stream.value([]);
  }

  final results = resultsAsync.value!;
  if (results.isEmpty) {
    return Stream.value([]);
  }

  final jokeIds = results.map((r) => r.id).toList();
  final jokesStream = ref.watch(jokesByIdsStreamProvider(jokeIds).stream);

  return jokesStream.map((jokes) {
    final jokeMap = {for (var joke in jokes) joke.id: joke};
    final ordered = <JokeWithDate>[];
    for (final result in results) {
      final joke = jokeMap[result.id];
      if (joke != null) {
        final hasImages =
            joke.setupImageUrl != null &&
            joke.setupImageUrl!.isNotEmpty &&
            joke.punchlineImageUrl != null &&
            joke.punchlineImageUrl!.isNotEmpty;
        if (hasImages) {
          ordered.add(JokeWithDate(joke: joke));
        }
      }
    }
    return ordered;
  });
});
