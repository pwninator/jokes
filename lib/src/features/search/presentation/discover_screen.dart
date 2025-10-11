import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_tile.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/search/application/discover_tab_state.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

/// Discover screen presents curated categories by default and lets users
/// drill into category searches before handing off to the dedicated search UI.
class DiscoverScreen extends ConsumerStatefulWidget {
  const DiscoverScreen({super.key});

  @override
  ConsumerState<DiscoverScreen> createState() => _DiscoverScreenState();
}

class _DiscoverScreenState extends ConsumerState<DiscoverScreen> {
  static const _viewerId = discoverViewerId;
  VoidCallback? _resetViewer;
  late final JokeListDataSource _dataSource;

  @override
  void initState() {
    super.initState();
    // Use unified category data source that routes by activeCategoryProvider
    _dataSource = CategoryDataSource(ref);
  }

  @override
  Widget build(BuildContext context) {
    final activeCategory = ref.watch(activeCategoryProvider);
    final hasActiveCategory = activeCategory != null;
    final categoryName = activeCategory?.displayName;
    final title = activeCategory?.displayName ?? 'Discover';

    return PopScope(
      canPop: !hasActiveCategory,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        if (_clearCategory()) return;
        if (context.canPop()) context.pop();
      },
      child: AdaptiveAppBarScreen(
        title: title,
        leading: hasActiveCategory
            ? IconButton(
                key: const Key('discover_screen-back-button'),
                icon: const Icon(Icons.arrow_back),
                onPressed: () {
                  if (_clearCategory()) return;
                  if (context.canPop()) {
                    context.pop();
                  }
                },
              )
            : null,
        actions: [
          IconButton(
            key: const Key('discover_screen-search-button'),
            icon: const Icon(Icons.search),
            style: IconButton.styleFrom(
              foregroundColor: Theme.of(context).colorScheme.primary,
            ),
            tooltip: 'Search',
            onPressed: () {
              resetDiscoverSearchState(ref);
              ref
                  .read(navigationHelpersProvider)
                  .navigateToRoute(
                    AppRoutes.discoverSearch,
                    push: true,
                    method: 'discover_search_button',
                  );
            },
          ),
        ],
        automaticallyImplyLeading: false,
        body: Column(
          children: [
            _ResultsSummary(category: activeCategory, dataSource: _dataSource),
            Expanded(
              child: hasActiveCategory
                  ? _CategoryResults(
                      viewerId: _viewerId,
                      onInitRegisterReset: (cb) => _resetViewer = cb,
                      categoryName: categoryName,
                      dataSource: _dataSource,
                    )
                  : _CategoryGrid(onCategorySelected: _onCategorySelected),
            ),
          ],
        ),
      ),
    );
  }

  void _onCategorySelected(WidgetRef ref, JokeCategory category) {
    // Set active category so the unified data source routes and resets
    ref.read(activeCategoryProvider.notifier).state = category;

    // Update search query only for search-type categories
    if (category.type == CategoryType.search) {
      final rawQuery = (category.jokeDescriptionQuery ?? '').trim();
      if (rawQuery.isNotEmpty) {
        final notifier = ref.read(
          searchQueryProvider(SearchScope.category).notifier,
        );
        final current = notifier.state;
        notifier.state = current.copyWith(
          query: '${JokeConstants.searchQueryPrefix}$rawQuery',
          maxResults: JokeConstants.userSearchMaxResults,
          publicOnly: JokeConstants.userSearchPublicOnly,
          matchMode: JokeConstants.userSearchMatchMode,
          excludeJokeIds: const [],
          label: SearchLabel.category,
        );
      }
    }
    ref.read(jokeViewerPageIndexProvider(_viewerId).notifier).state = 0;
    _resetViewer?.call();
  }

  bool _clearCategory() {
    final activeCategory = ref.read(activeCategoryProvider);
    if (activeCategory == null) {
      return false;
    }

    final searchQueryNotifier = ref.read(
      searchQueryProvider(SearchScope.category).notifier,
    );
    final currentQuery = searchQueryNotifier.state;
    searchQueryNotifier.state = currentQuery.copyWith(
      query: '',
      excludeJokeIds: const [],
      label: SearchLabel.none,
    );

    ref.read(activeCategoryProvider.notifier).state = null;
    ref.read(jokeViewerPageIndexProvider(_viewerId).notifier).state = 0;
    _resetViewer?.call();
    return true;
  }
}

class _CategoryResults extends ConsumerStatefulWidget {
  const _CategoryResults({
    required this.viewerId,
    required this.onInitRegisterReset,
    required this.categoryName,
    required this.dataSource,
  });

  final String viewerId;
  final ValueChanged<VoidCallback?> onInitRegisterReset;
  final String? categoryName;
  final JokeListDataSource dataSource;

  @override
  ConsumerState<_CategoryResults> createState() => _CategoryResultsState();
}

class _CategoryResultsState extends ConsumerState<_CategoryResults> {
  @override
  Widget build(BuildContext context) {
    final currentQuery = ref
        .watch(searchQueryProvider(SearchScope.category))
        .query;
    final hasQuery = currentQuery.isNotEmpty;

    // Empty state is only shown when data is empty (not loading)
    // JokeListViewer handles loading state automatically
    final emptyStateMessage = hasQuery
        ? (widget.categoryName != null
              ? 'No jokes found in ${widget.categoryName}'
              : 'No jokes found')
        : '';

    // Use popular context if active category type is popular
    final active = ref.watch(activeCategoryProvider);
    final jokeContext = (active?.type == CategoryType.popular)
        ? AnalyticsJokeContext.popular
        : AnalyticsJokeContext.category;
    return JokeListViewer(
      dataSource: widget.dataSource,
      jokeContext: jokeContext,
      viewerId: widget.viewerId,
      onInitRegisterReset: widget.onInitRegisterReset,
      emptyState: emptyStateMessage.isEmpty
          ? const SizedBox.shrink()
          : Center(child: Text(emptyStateMessage)),
    );
  }
}

class _ResultsSummary extends ConsumerWidget {
  const _ResultsSummary({required this.category, required this.dataSource});

  final JokeCategory? category;
  final JokeListDataSource dataSource;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Don't show count for Popular category because there are many jokes
    // so the partial count is misleading
    if (category == null || category!.type == CategoryType.popular) {
      return const SizedBox.shrink();
    }

    final countInfo = ref.watch(dataSource.resultCount);
    final count = countInfo.count;
    final hasMore = countInfo.hasMore;

    // Don't show count until we have at least one joke loaded
    if (count == 0) return const SizedBox.shrink();

    final hasMoreLabel = hasMore ? '+' : '';
    final noun = count == 1 ? 'joke' : 'jokes';
    final label = '$count$hasMoreLabel $noun';

    return Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 6.0),
        child: Text(
          label,
          key: const Key('search-results-count'),
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ),
    );
  }
}

class _CategoryGrid extends ConsumerWidget {
  const _CategoryGrid({required this.onCategorySelected});

  final void Function(WidgetRef ref, JokeCategory category) onCategorySelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categoriesAsync = ref.watch(discoverCategoriesProvider);

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

            int columns = (availableWidth / targetTileWidth).round().clamp(
              1,
              8,
            );

            double tileWidth() =>
                (availableWidth - (columns - 1) * spacing) / columns;

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
                key: const Key('discover_screen-categories-grid'),
                crossAxisCount: columns,
                mainAxisSpacing: spacing,
                crossAxisSpacing: spacing,
                itemCount: approved.length,
                itemBuilder: (context, index) {
                  final category = approved[index];
                  return JokeCategoryTile(
                    category: category,
                    showStateBorder: false,
                    borderColor: category.borderColor,
                    onTap: () => onCategorySelected(ref, category),
                  );
                },
              ),
            );
          },
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, st) => Center(child: Text('Error loading categories: $e')),
    );
  }
}
