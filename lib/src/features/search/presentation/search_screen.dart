import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_tile.dart';
import 'package:snickerdoodle/src/features/search/presentation/special_tiles.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  VoidCallback? _resetViewer;
  final FocusNode _focusNode = FocusNode();
  final TextEditingController _controller = TextEditingController();
  bool _hasHandledFocusTrigger = false;

  @override
  void initState() {
    super.initState();
    // Add listener to trigger rebuild when controller text changes
    _controller.addListener(() {
      if (mounted) setState(() {});
    });

    // Initialize controller with current provider value for persistence
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(keyboardResizeProvider.notifier).state = false;

      if (mounted) {
        final currentQuery = ref
            .read(searchQueryProvider(SearchScope.userJokeSearch))
            .query;
        const String prefix = JokeConstants.searchQueryPrefix;
        if (currentQuery.length >= prefix.length &&
            currentQuery.substring(0, prefix.length) == prefix) {
          _controller.text = currentQuery.substring(prefix.length);
        } else {
          _controller.text = currentQuery;
        }
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _onSubmitted(String raw, {required SearchLabel label}) {
    final query = raw.trim();
    if (query.length < 2) {
      ScaffoldMessenger.of(context).clearMaterialBanners();
      ScaffoldMessenger.of(context).showMaterialBanner(
        const MaterialBanner(
          content: Text('Please enter a longer search query'),
          actions: [SizedBox.shrink()],
        ),
      );
      return;
    }
    ref.read(jokeViewerPageIndexProvider('search_user').notifier).state = 0;

    final current = ref.read(searchQueryProvider(SearchScope.userJokeSearch));
    ref
        .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
        .state = current.copyWith(
      query: "${JokeConstants.searchQueryPrefix}$query",
      maxResults: JokeConstants.userSearchMaxResults,
      publicOnly: JokeConstants.userSearchPublicOnly,
      matchMode: JokeConstants.userSearchMatchMode,
      excludeJokeIds: const [],
      label: label,
    );
    // Reset viewer to first result
    _resetViewer?.call();
    FocusScope.of(context).unfocus();
  }

  @override
  Widget build(BuildContext context) {
    // Check for focus trigger from navigation
    final focusTrigger = ref.watch(searchFieldFocusTriggerProvider);

    // If focus trigger is true and we haven't handled it yet, focus the search field
    if (focusTrigger && !_hasHandledFocusTrigger) {
      _hasHandledFocusTrigger = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _focusNode.requestFocus();
        }
      });
    }

    // If focus trigger is false, reset our handled flag
    if (!focusTrigger) {
      _hasHandledFocusTrigger = false;
    }

    return AdaptiveAppBarScreen(
      title: 'Search',
      body: Column(
        children: [
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
            child: TextField(
              key: const Key('search_screen-search-field'),
              controller: _controller,
              focusNode: _focusNode,
              decoration: InputDecoration(
                hintText: 'Search for jokes!',
                prefixIcon: const Icon(Icons.search),
                isDense: true,
                border: const OutlineInputBorder(),
                suffixIcon: _controller.text.isNotEmpty
                    ? Padding(
                        padding: const EdgeInsets.only(right: 8.0),
                        child: IconButton(
                          key: const Key('search_screen-clear-button'),
                          tooltip: 'Clear',
                          icon: const Icon(Icons.close),
                          padding: EdgeInsets.all(4),
                          iconSize: 20,
                          style: IconButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.primary.withValues(alpha: 0.5),
                            foregroundColor: Theme.of(
                              context,
                            ).colorScheme.primary,
                            shape: const CircleBorder(),
                            visualDensity: VisualDensity.compact,
                          ),
                          onPressed: () {
                            _controller.clear();
                            final current = ref.read(
                              searchQueryProvider(SearchScope.userJokeSearch),
                            );
                            ref
                                .read(
                                  searchQueryProvider(
                                    SearchScope.userJokeSearch,
                                  ).notifier,
                                )
                                .state = current.copyWith(
                              query: '',
                              maxResults: JokeConstants.userSearchMaxResults,
                              publicOnly: JokeConstants.userSearchPublicOnly,
                              matchMode: JokeConstants.userSearchMatchMode,
                              excludeJokeIds: const [],
                              label: JokeConstants.userSearchLabel,
                            );
                            FocusScope.of(context).unfocus();
                          },
                        ),
                      )
                    : null,
                // Ensure the suffix icon area size is enforced by the InputDecorator
                suffixIconConstraints: const BoxConstraints.tightFor(
                  width: 40,
                  height: 40,
                ),
              ),
              maxLines: 1,
              textInputAction: TextInputAction.search,
              onSubmitted: (value) =>
                  _onSubmitted(value, label: SearchLabel.none),
            ),
          ),
          // Results count label under the search bar
          Consumer(
            builder: (context, ref, _) {
              final currentQuery = ref
                  .watch(searchQueryProvider(SearchScope.userJokeSearch))
                  .query
                  .trim();
              if (currentQuery.length < 2) {
                return const SizedBox.shrink();
              }
              final resultsAsync = ref.watch(
                searchResultsViewerProvider(SearchScope.userJokeSearch),
              );
              return resultsAsync.when(
                data: (list) {
                  final count = list.length;
                  final label = count == 1 ? '1 result' : '$count results';
                  return Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16.0,
                        vertical: 6.0,
                      ),
                      child: Text(
                        label,
                        key: const Key('search-results-count'),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  );
                },
                loading: () => const SizedBox.shrink(),
                error: (error, stackTrace) => const SizedBox.shrink(),
              );
            },
          ),
          Expanded(
            child: Consumer(
              builder: (context, ref, child) {
                final bool isSearchEmpty = _controller.text.trim().isEmpty;
                if (isSearchEmpty) {
                  final categoriesAsync =
                      ref.watch(categoriesWithSpecialTilesProvider);
                  return categoriesAsync.when(
                    data: (categories) {
                      final approved = categories
                          .where((c) => c.state == JokeCategoryState.approved)
                          .toList();

                      if (approved.isEmpty) {
                        return const Center(child: Text('Search for jokes!'));
                      }

                      const double minTileWidth = 150.0;
                      const double maxTileWidth = 250.0;
                      const double targetTileWidth = 200.0;

                      return LayoutBuilder(
                        builder: (context, constraints) {
                          const horizontalPadding = 16.0;
                          const spacing = 12.0;
                          final availableWidth =
                              constraints.maxWidth - (horizontalPadding * 2);

                          int columns = (availableWidth / targetTileWidth)
                              .round()
                              .clamp(1, 8);

                          double tileWidth() =>
                              (availableWidth - (columns - 1) * spacing) /
                              columns;

                          while (tileWidth() > maxTileWidth && columns < 12) {
                            columns += 1;
                          }
                          while (tileWidth() < minTileWidth && columns > 1) {
                            columns -= 1;
                          }

                          return Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: horizontalPadding,
                            ),
                            child: MasonryGridView.count(
                              key: const Key('search-categories-grid'),
                              crossAxisCount: columns,
                              mainAxisSpacing: spacing,
                              crossAxisSpacing: spacing,
                              itemCount: approved.length,
                              itemBuilder: (context, index) {
                                final cat = approved[index];
                                return JokeCategoryTile(
                                  category: cat,
                                  showStateBorder: false,
                                  onTap: () {
                                    if (cat.id
                                        .startsWith(specialTileIdPrefix)) {
                                      final tileNumber =
                                          cat.id.substring(specialTileIdPrefix.length);
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(
                                        SnackBar(
                                          content: Text(tileNumber),
                                        ),
                                      );
                                    } else {
                                      final rawQuery =
                                          cat.jokeDescriptionQuery.trim();
                                      if (rawQuery.isEmpty) return;
                                      _controller.text = rawQuery;
                                      _onSubmitted(
                                        rawQuery,
                                        label: SearchLabel.category,
                                      );
                                    }
                                  },
                                );
                              },
                            ),
                          );
                        },
                      );
                    },
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (e, st) =>
                        Center(child: Text('Error loading categories: $e')),
                  );
                }

                final currentQuery = ref
                    .watch(searchQueryProvider(SearchScope.userJokeSearch))
                    .query;
                final emptyStateMessage = currentQuery.isNotEmpty
                    ? 'No jokes found'
                    : '';
                return JokeListViewer(
                  jokesAsyncProvider: searchResultsViewerProvider(
                    SearchScope.userJokeSearch,
                  ),
                  jokeContext: AnalyticsJokeContext.search,
                  viewerId: 'search_user',
                  onInitRegisterReset: (cb) => _resetViewer = cb,
                  emptyState: emptyStateMessage.isEmpty
                      ? const SizedBox.shrink()
                      : Center(child: Text(emptyStateMessage)),
                  showSimilarSearchButton: false,
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
