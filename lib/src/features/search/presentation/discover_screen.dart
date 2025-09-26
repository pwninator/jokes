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
  static const _viewerId = 'discover_category';
  VoidCallback? _resetViewer;
  String? _activeCategoryName;

  @override
  Widget build(BuildContext context) {
    final searchState = ref.watch(searchQueryProvider(SearchScope.category));
    final effectiveQuery = _effectiveQuery(searchState.query);
    final hasActiveQuery = effectiveQuery.isNotEmpty;
    final categoryName = hasActiveQuery
        ? (_activeCategoryName ?? _deriveCategoryName(effectiveQuery))
        : null;
    final title = categoryName ?? 'Discover';

    return PopScope(
      canPop: !hasActiveQuery,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        if (_clearCategorySearch()) return;
        if (context.canPop()) context.pop();
      },
      child: AdaptiveAppBarScreen(
        title: title,
        leading: hasActiveQuery
            ? IconButton(
                key: const Key('discover_screen-back-button'),
                icon: const Icon(Icons.arrow_back),
                onPressed: () {
                  if (_clearCategorySearch()) return;
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
            tooltip: 'Search',
            onPressed: () => context.push(AppRoutes.discoverSearch),
          ),
        ],
        automaticallyImplyLeading: false,
        body: Column(
          children: [
            _ResultsSummary(categoryName: categoryName),
            Expanded(
              child: hasActiveQuery
                  ? _CategoryResults(
                      viewerId: _viewerId,
                      onInitRegisterReset: (cb) => _resetViewer = cb,
                      categoryName: categoryName,
                    )
                  : _CategoryGrid(onCategorySelected: _onCategorySelected),
            ),
          ],
        ),
      ),
    );
  }

  void _onCategorySelected(WidgetRef ref, JokeCategory category) {
    final rawQuery = category.jokeDescriptionQuery.trim();
    if (rawQuery.isEmpty) return;

    setState(() {
      _activeCategoryName = category.displayName;
    });

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
    ref.read(jokeViewerPageIndexProvider(_viewerId).notifier).state = 0;
    _resetViewer?.call();
  }

  bool _clearCategorySearch() {
    final notifier = ref.read(
      searchQueryProvider(SearchScope.category).notifier,
    );
    final current = notifier.state;
    if (_effectiveQuery(current.query).isEmpty) {
      return false;
    }
    notifier.state = current.copyWith(
      query: '',
      excludeJokeIds: const [],
      label: SearchLabel.none,
    );
    ref.read(jokeViewerPageIndexProvider(_viewerId).notifier).state = 0;
    _resetViewer?.call();
    if (mounted) {
      setState(() {
        _activeCategoryName = null;
      });
    }
    return true;
  }

  String _effectiveQuery(String raw) {
    const prefix = JokeConstants.searchQueryPrefix;
    if (raw.startsWith(prefix)) {
      return raw.substring(prefix.length).trim();
    }
    return raw.trim();
  }

  String _deriveCategoryName(String query) {
    if (query.isEmpty) return 'Discover';
    return query[0].toUpperCase() + query.substring(1);
  }
}

class _CategoryResults extends ConsumerWidget {
  const _CategoryResults({
    required this.viewerId,
    required this.onInitRegisterReset,
    required this.categoryName,
  });

  final String viewerId;
  final ValueChanged<VoidCallback?> onInitRegisterReset;
  final String? categoryName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentQuery = ref
        .watch(searchQueryProvider(SearchScope.category))
        .query;
    final hasQuery = currentQuery.isNotEmpty;
    final emptyStateMessage = hasQuery
        ? (categoryName != null
              ? 'No jokes found in $categoryName'
              : 'No jokes found')
        : '';
    return JokeListViewer(
      jokesAsyncProvider: searchResultsViewerProvider(SearchScope.category),
      jokeContext: AnalyticsJokeContext.search,
      viewerId: viewerId,
      onInitRegisterReset: onInitRegisterReset,
      emptyState: emptyStateMessage.isEmpty
          ? const SizedBox.shrink()
          : Center(child: Text(emptyStateMessage)),
      showSimilarSearchButton: false,
    );
  }
}

class _ResultsSummary extends ConsumerWidget {
  const _ResultsSummary({required this.categoryName});

  final String? categoryName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (categoryName == null) return const SizedBox.shrink();

    final idsAsync = ref.watch(searchResultIdsProvider(SearchScope.category));
    return idsAsync.when(
      data: (list) {
        final count = list.length;
        final noun = count == 1 ? 'joke' : 'jokes';
        final label = '$count $noun';
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
