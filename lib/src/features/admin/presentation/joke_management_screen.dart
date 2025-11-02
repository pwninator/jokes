import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_admin_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

// Admin JokeCard config
const bool kAdminJokeCardIsAdminMode = true;
const bool kAdminJokeCardShowSaveButton = false;
const bool kAdminJokeCardShowShareButton = false;
const bool kAdminJokeCardShowAdminRatingButtons = true;
const bool kAdminJokeCardShowUsageStats = true;
const bool kAdminJokeCardShowSimilarSearchButton = true;
const String kAdminJokeCardContext = 'admin';

class JokeManagementScreen extends ConsumerStatefulWidget {
  const JokeManagementScreen({super.key});

  @override
  ConsumerState<JokeManagementScreen> createState() =>
      _JokeManagementScreenState();
}

class _JokeManagementScreenState extends ConsumerState<JokeManagementScreen> {
  bool _showSearch = false;
  final FocusNode _searchFocusNode = FocusNode();
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    // Initialize controller with current provider value
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        final currentQuery = ref
            .read(searchQueryProvider(SearchScope.jokeManagementSearch))
            .query;
        const String prefix = JokeConstants.searchQueryPrefix;
        if (currentQuery.length >= prefix.length &&
            currentQuery.substring(0, prefix.length) == prefix) {
          _searchController.text = currentQuery.substring(prefix.length);
        } else {
          _searchController.text = currentQuery;
        }
      }
    });
    _searchFocusNode.addListener(() {
      if (!_searchFocusNode.hasFocus) {
        final params = ref.read(
          searchQueryProvider(SearchScope.jokeManagementSearch),
        );
        final query = params.query.trim();
        if (mounted && query.isEmpty && !_showSearch) {
          setState(() {
            _showSearch = false;
          });
        }
      }
    });
    _scrollController.addListener(_onScrollCheckLoadMore);
    // After first frame, run a check to prefetch when list is short
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _onScrollCheckLoadMore();
    });
  }

  @override
  void dispose() {
    _searchFocusNode.dispose();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScrollCheckLoadMore() {
    // If in search mode, do nothing
    final searchParams = ref.read(
      searchQueryProvider(SearchScope.jokeManagementSearch),
    );
    if (searchParams.query.trim().isNotEmpty) return;

    final ids = ref.read(adminPagedIdsProvider);
    if (ids.isEmpty) return;

    // Pixels-based estimation of remaining items: compute average item extent
    // as (maxScrollExtent + viewport) / itemCount, then multiply by thresholdFromEnd.
    final thresholdFromEnd = 5;
    final position = _scrollController.position;
    final totalContentExtent =
        position.maxScrollExtent + position.viewportDimension;
    final avgItemExtent = ids.isNotEmpty
        ? totalContentExtent / ids.length
        : double.infinity;
    final thresholdPixels = avgItemExtent * thresholdFromEnd;
    final remainingPixels = position.maxScrollExtent - position.pixels;

    if (remainingPixels <= thresholdPixels) {
      final paging = ref.read(adminPagingProvider);
      if (!paging.isLoading && paging.hasMore) {
        ref.read(adminPagingProvider.notifier).loadMore();
      }
    }
  }

  String _getEmptyStateTitle(JokeFilterState filterState) {
    if (filterState.hasStateFilter) {
      final stateNames = filterState.selectedStates
          .map((s) => s.value)
          .join(', ');
      return 'No jokes found with selected states: $stateNames';
    } else {
      return 'No jokes yet!';
    }
  }

  String _getEmptyStateSubtitle(JokeFilterState filterState) {
    if (filterState.hasStateFilter) {
      return 'Try selecting different states or clearing the state filter';
    } else {
      return 'Tap the + button to add your first joke';
    }
  }

  Future<void> _showStateSelectionDialog(
    BuildContext context,
    Set<JokeState> selectedStates,
  ) async {
    final result = await showDialog<Set<JokeState>>(
      context: context,
      builder: (BuildContext context) {
        final tempSelectedStates = Set<JokeState>.from(selectedStates);
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text('Select Joke States'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: JokeState.values.map((state) {
                    return CheckboxListTile(
                      title: Text(state.value),
                      value: tempSelectedStates.contains(state),
                      onChanged: (bool? checked) {
                        setState(() {
                          if (checked ?? false) {
                            tempSelectedStates.add(state);
                          } else {
                            tempSelectedStates.remove(state);
                          }
                        });
                      },
                    );
                  }).toList(),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    Navigator.of(context).pop();
                  },
                  child: const Text('Cancel'),
                ),
                TextButton(
                  onPressed: () {
                    Navigator.of(context).pop(tempSelectedStates);
                  },
                  child: const Text('Apply'),
                ),
              ],
            );
          },
        );
      },
    );

    if (result != null) {
      ref.read(jokeFilterProvider.notifier).setSelectedStates(result);
    }
  }

  @override
  Widget build(BuildContext context) {
    final adminJokesAsync = ref.watch(adminJokesLiveProvider);
    final filterState = ref.watch(jokeFilterProvider);
    final searchParams = ref.watch(
      searchQueryProvider(SearchScope.jokeManagementSearch),
    );

    // Show search field if user explicitly wants to search OR if there's a query
    final showSearch = _showSearch || searchParams.query.trim().isNotEmpty;

    return AppBarConfiguredScreen(
      title: 'Joke Management',
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          context.push(AppRoutes.adminEditor);
        },
        tooltip: 'Add New Joke',
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          // Filter bar
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: 16.0,
              vertical: 8.0,
            ),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(
                bottom: BorderSide(
                  color: Theme.of(
                    context,
                  ).colorScheme.outline.withValues(alpha: 0.2),
                  width: 1,
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (showSearch)
                  SizedBox(
                    width: double.infinity,
                    child: TextField(
                      key: const Key('admin-search-field'),
                      controller: _searchController,
                      focusNode: _searchFocusNode,
                      decoration: InputDecoration(
                        hintText: 'Search jokes...',
                        prefixIcon: const Icon(Icons.search),
                        isDense: true,
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          tooltip: 'Clear',
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _searchController.clear();
                            ref
                                .read(
                                  searchQueryProvider(
                                    SearchScope.jokeManagementSearch,
                                  ).notifier,
                                )
                                .state = const SearchQuery(
                              query: '',
                              maxResults: JokeConstants.adminSearchMaxResults,
                              publicOnly: JokeConstants.adminSearchPublicOnly,
                              matchMode: JokeConstants.adminSearchMatchMode,
                            );
                            setState(() {
                              _showSearch = false;
                            });
                            FocusScope.of(context).unfocus();
                          },
                        ),
                      ),
                      maxLines: 1,
                      textInputAction: TextInputAction.search,
                      onSubmitted: (raw) {
                        final query = raw.trim();
                        ref
                            .read(
                              searchQueryProvider(
                                SearchScope.jokeManagementSearch,
                              ).notifier,
                            )
                            .state = SearchQuery(
                          query: "${JokeConstants.searchQueryPrefix}$query",
                          maxResults: JokeConstants.adminSearchMaxResults,
                          publicOnly: JokeConstants.adminSearchPublicOnly,
                          matchMode: JokeConstants.adminSearchMatchMode,
                        );
                        FocusScope.of(context).unfocus();
                      },
                    ),
                  ),
                const SizedBox(height: 8),
                Wrap(
                  key: const Key('admin-filter-chips-wrap'),
                  spacing: 4,
                  runSpacing: 0,
                  children: [
                    if (!showSearch)
                      FilterChip(
                        key: const Key('search-toggle-chip'),
                        label: Text(
                          'Search',
                          style: Theme.of(
                            context,
                          ).textTheme.bodySmall?.copyWith(fontSize: 12),
                        ),
                        labelPadding: const EdgeInsets.symmetric(horizontal: 0),
                        visualDensity: VisualDensity.compact,
                        selected: false,
                        onSelected: (_) {
                          setState(() {
                            _showSearch = true;
                          });
                          WidgetsBinding.instance.addPostFrameCallback((_) {
                            if (mounted) {
                              _searchFocusNode.requestFocus();
                            }
                          });
                        },
                        showCheckmark: false,
                        avatar: const Icon(Icons.search, size: 16),
                      ),
                    FilterChip(
                      key: const Key('state-filter-chip'),
                      label: Text(
                        filterState.hasStateFilter
                            ? 'State (${filterState.selectedStates.length})'
                            : 'State',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontSize: 12,
                          color: filterState.hasStateFilter
                              ? Theme.of(context).colorScheme.primary
                              : null,
                        ),
                      ),
                      labelPadding: const EdgeInsets.symmetric(horizontal: 0),
                      visualDensity: VisualDensity.compact,
                      selected: filterState.hasStateFilter,
                      onSelected: (_) {
                        _showStateSelectionDialog(
                          context,
                          filterState.selectedStates,
                        );
                      },
                      showCheckmark: false,
                      avatar: Icon(
                        Icons.filter_list,
                        size: 16,
                        color: filterState.hasStateFilter
                            ? Theme.of(context).colorScheme.primary
                            : null,
                      ),
                    ),
                    _AdminFilterChip(
                      key: const Key('popular-only-filter-chip'),
                      label: 'Popular',
                      selected:
                          filterState.adminScoreFilter ==
                          JokeAdminScoreFilter.popular,
                      onSelected: (_) {
                        ref
                            .read(jokeFilterProvider.notifier)
                            .toggleScoreFilter(JokeAdminScoreFilter.popular);
                      },
                    ),
                    _AdminFilterChip(
                      key: const Key('recent-only-filter-chip'),
                      label: 'Recent',
                      selected:
                          filterState.adminScoreFilter ==
                          JokeAdminScoreFilter.recent,
                      onSelected: (_) {
                        ref
                            .read(jokeFilterProvider.notifier)
                            .toggleScoreFilter(JokeAdminScoreFilter.recent);
                      },
                    ),
                    _AdminFilterChip(
                      key: const Key('best-only-filter-chip'),
                      label: 'Best',
                      selected:
                          filterState.adminScoreFilter ==
                          JokeAdminScoreFilter.best,
                      onSelected: (_) {
                        ref
                            .read(jokeFilterProvider.notifier)
                            .toggleScoreFilter(JokeAdminScoreFilter.best);
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Search + Jokes list
          Expanded(
            child: adminJokesAsync.when(
              data: (items) => items.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.mood_bad,
                            size: 64,
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurface.withValues(alpha: 0.4),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            _getEmptyStateTitle(filterState),
                            style: TextStyle(
                              fontSize: 18,
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurface.withValues(alpha: 0.6),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _getEmptyStateSubtitle(filterState),
                            style: TextStyle(
                              fontSize: 14,
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurface.withValues(alpha: 0.5),
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(8.0),
                      itemCount: items.length,
                      itemBuilder: (context, index) {
                        final jvd = items[index];
                        final joke = jvd.joke;
                        return JokeCard(
                          key: Key(joke.id),
                          joke: joke,
                          index: index,
                          isAdminMode: kAdminJokeCardIsAdminMode,
                          showSaveButton: kAdminJokeCardShowSaveButton,
                          showShareButton: kAdminJokeCardShowShareButton,
                          showAdminRatingButtons:
                              kAdminJokeCardShowAdminRatingButtons,
                          showUsageStats: kAdminJokeCardShowUsageStats,
                          jokeContext: kAdminJokeCardContext,
                          showSimilarSearchButton:
                              kAdminJokeCardShowSimilarSearchButton,
                          topRightBadgeText: jvd.vectorDistance
                              ?.toStringAsFixed(2),
                        );
                      },
                    ),
              loading: () => const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text('Loading jokes...'),
                  ],
                ),
              ),
              error: (error, stackTrace) => Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.error_outline,
                      size: 64,
                      color: Theme.of(context).colorScheme.error,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Error loading jokes',
                      style: TextStyle(
                        fontSize: 18,
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      error.toString(),
                      style: const TextStyle(fontSize: 14),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminFilterChip extends StatelessWidget {
  const _AdminFilterChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final bool selected;
  final ValueChanged<bool> onSelected;

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Text(
        label,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 12),
      ),
      labelPadding: const EdgeInsets.symmetric(horizontal: 0),
      visualDensity: VisualDensity.compact,
      selected: selected,
      onSelected: onSelected,
      showCheckmark: true,
    );
  }
}
