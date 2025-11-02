import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

// Pagination state for admin list
class AdminPagingState {
  final List<String> loadedIds;
  final JokeListPageCursor? cursor;
  final bool isLoading;
  final bool hasMore;

  const AdminPagingState({
    required this.loadedIds,
    required this.cursor,
    required this.isLoading,
    required this.hasMore,
  });

  const AdminPagingState.initial()
    : loadedIds = const <String>[],
      cursor = null,
      isLoading = false,
      hasMore = true;

  AdminPagingState copyWith({
    List<String>? loadedIds,
    JokeListPageCursor? cursor,
    bool? isLoading,
    bool? hasMore,
  }) {
    return AdminPagingState(
      loadedIds: loadedIds ?? this.loadedIds,
      cursor: cursor ?? this.cursor,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
    );
  }
}

class AdminPagingNotifier extends StateNotifier<AdminPagingState> {
  AdminPagingNotifier(this.ref) : super(const AdminPagingState.initial()) {
    // Reset and load first page on filter changes
    ref.listen<JokeFilterState>(jokeFilterProvider, (prev, next) {
      reset();
      // Defer to allow UI/provider tree to settle
      Future.microtask(loadFirstPage);
    });
    // Also reset when search becomes empty or toggles away from search
    ref.listen<SearchQuery>(
      searchQueryProvider(SearchScope.jokeManagementSearch),
      (prev, next) {
        if (next.query.trim().isEmpty) {
          reset();
          Future.microtask(loadFirstPage);
        }
      },
    );

    // Trigger initial page load
    Future.microtask(loadFirstPage);
  }

  final Ref ref;
  static const int defaultPageSize = 10;

  void reset() {
    state = const AdminPagingState.initial();
  }

  List<JokeFilter> _buildFilters(JokeFilterState filterState) {
    final filters = <JokeFilter>[];
    if (filterState.selectedStates.isNotEmpty) {
      filters.add(
        JokeFilter.whereInValues(
          JokeField.state,
          filterState.selectedStates.map((s) => s.value),
        ),
      );
    }
    switch (filterState.adminScoreFilter) {
      case JokeAdminScoreFilter.popular:
        filters.add(JokeFilter.greaterThan(JokeField.popularityScore, 0.0));
        break;
      case JokeAdminScoreFilter.recent:
        filters.add(
          JokeFilter.greaterThan(JokeField.popularityScoreRecent, 0.0),
        );
        break;
      case JokeAdminScoreFilter.best:
        filters.add(JokeFilter.greaterThan(JokeField.savedFraction, 0.0));
        break;
      case JokeAdminScoreFilter.none:
        break;
    }
    return filters;
  }

  JokeField _getOrderByField(JokeFilterState filterState) {
    switch (filterState.adminScoreFilter) {
      case JokeAdminScoreFilter.popular:
        return JokeField.popularityScore;
      case JokeAdminScoreFilter.recent:
        return JokeField.popularityScoreRecent;
      case JokeAdminScoreFilter.best:
        return JokeField.savedFraction;
      case JokeAdminScoreFilter.none:
        return JokeField.creationTime;
    }
  }

  Future<void> loadFirstPage({int limit = defaultPageSize}) async {
    if (state.isLoading) return;
    state = state.copyWith(
      isLoading: true,
      loadedIds: const <String>[],
      cursor: null,
      hasMore: true,
    );
    final repository = ref.read(jokeRepositoryProvider);
    final filterState = ref.read(jokeFilterProvider);
    try {
      final page = await repository.getFilteredJokePage(
        filters: _buildFilters(filterState),
        orderByField: _getOrderByField(filterState),
        orderDirection: OrderDirection.descending,
        limit: limit,
        cursor: null,
      );
      state = state.copyWith(
        loadedIds: page.ids,
        cursor: page.cursor,
        hasMore: page.hasMore,
        isLoading: false,
      );
    } catch (e) {
      // Fail closed
      state = state.copyWith(isLoading: false, hasMore: false);
    }
  }

  Future<void> loadMore({int limit = defaultPageSize}) async {
    if (state.isLoading || !state.hasMore) return;
    state = state.copyWith(isLoading: true);
    final repository = ref.read(jokeRepositoryProvider);
    final filterState = ref.read(jokeFilterProvider);
    try {
      final page = await repository.getFilteredJokePage(
        filters: _buildFilters(filterState),
        orderByField: _getOrderByField(filterState),
        orderDirection: OrderDirection.descending,
        limit: limit,
        cursor: state.cursor,
      );
      // Deduplicate in case of overlapping pages
      final existing = Set<String>.from(state.loadedIds);
      final appended = <String>[
        ...state.loadedIds,
        ...page.ids.where((id) => !existing.contains(id)),
      ];
      state = state.copyWith(
        loadedIds: appended,
        cursor: page.cursor,
        hasMore: page.hasMore,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false);
    }
  }
}

final adminPagingProvider =
    StateNotifierProvider<AdminPagingNotifier, AdminPagingState>((ref) {
      return AdminPagingNotifier(ref);
    });

final adminPagedIdsProvider = Provider<List<String>>((ref) {
  return ref.watch(adminPagingProvider).loadedIds;
});

// Unified admin jokes provider: search path uses live search; otherwise
// builds from filtered snapshot of IDs and streams per-doc.
final adminJokesLiveProvider =
    Provider<AsyncValue<List<JokeWithVectorDistance>>>((ref) {
      final searchParams = ref.watch(
        searchQueryProvider(SearchScope.jokeManagementSearch),
      );

      // If there is a search query, delegate to live search provider
      if (searchParams.query.trim().isNotEmpty) {
        return ref.watch(
          searchResultsLiveProvider(SearchScope.jokeManagementSearch),
        );
      }
      final ids = ref.watch(adminPagedIdsProvider);
      if (ids.isEmpty) {
        // Show loading while first page fetch is in flight
        final isLoading = ref.watch(adminPagingProvider).isLoading;
        return isLoading
            ? const AsyncValue<List<JokeWithVectorDistance>>.loading()
            : const AsyncValue.data(<JokeWithVectorDistance>[]);
      }

      // Watch each joke by id
      final perJoke = <AsyncValue<Joke?>>[];
      for (final id in ids) {
        perJoke.add(ref.watch(jokeStreamByIdProvider(id)));
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

      // Build ordered list based on ids, skipping nulls. Return partial data
      // even if some items are still loading.
      final ordered = <JokeWithVectorDistance>[];
      for (var i = 0; i < ids.length; i++) {
        final value = perJoke[i].value;
        if (value != null) {
          ordered.add(
            JokeWithVectorDistance(joke: value, vectorDistance: null),
          );
        }
      }
      if (ordered.isEmpty && perJoke.any((j) => j.isLoading)) {
        return const AsyncValue.loading();
      }
      return AsyncValue.data(ordered);
    });
