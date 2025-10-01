import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/generic_paging_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/search_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  static const _emptyStateMessage = 'Type a search to get started';

  VoidCallback? _resetViewer;
  final FocusNode _focusNode = FocusNode();
  final TextEditingController _controller = TextEditingController();
  late final PagingDataSource _dataSource;

  @override
  void initState() {
    super.initState();

    _controller.addListener(() {
      if (mounted) {
        setState(() {});
      }
    });

    // Create the data source once and reuse it across rebuilds
    _dataSource = UserJokeSearchDataSource(ref);

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      ref.read(keyboardResizeProvider.notifier).state = false;

      // If a query is already present (e.g., set programmatically for Similar Search),
      // preserve it and reflect it in the text field instead of clearing.
      final existing = ref.read(
        searchQueryProvider(SearchScope.userJokeSearch),
      );
      if (existing.query.isNotEmpty &&
          existing.label == SearchLabel.similarJokes) {
        _controller.text = _effectiveQuery(existing.query);
      } else {
        _clearSearchState();
        _focusNode.requestFocus();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _clearSearchState() {
    final notifier = ref.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = SearchQuery(
      query: '',
      maxResults: JokeConstants.userSearchMaxResults,
      publicOnly: JokeConstants.userSearchPublicOnly,
      matchMode: JokeConstants.userSearchMatchMode,
      excludeJokeIds: const [],
      label: JokeConstants.userSearchLabel,
    );
    ref.read(jokeViewerPageIndexProvider('search_user').notifier).state = 0;
    _controller.text = '';
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

    ref
        .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
        .state = SearchQuery(
      query: '${JokeConstants.searchQueryPrefix}$query',
      maxResults: JokeConstants.userSearchMaxResults,
      publicOnly: JokeConstants.userSearchPublicOnly,
      matchMode: JokeConstants.userSearchMatchMode,
      excludeJokeIds: const [],
      label: label,
    );

    _resetViewer?.call();
    FocusScope.of(context).unfocus();
  }

  @override
  Widget build(BuildContext context) {
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
                          padding: const EdgeInsets.all(4),
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
                            _clearSearchState();
                            FocusScope.of(context).unfocus();
                          },
                        ),
                      )
                    : null,
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
          Consumer(
            builder: (context, ref, _) {
              final trimmedQuery = _effectiveQuery(
                ref
                    .watch(searchQueryProvider(SearchScope.userJokeSearch))
                    .query,
              );
              if (trimmedQuery.length < 2) {
                return const SizedBox.shrink();
              }

              final countInfo = ref.watch(_dataSource.resultCount);
              final count = countInfo.count;
              if (count == 0) return const SizedBox.shrink();
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
          ),
          Expanded(
            child: Consumer(
              builder: (context, ref, _) {
                final state = ref.watch(
                  searchQueryProvider(SearchScope.userJokeSearch),
                );
                final effectiveQuery = _effectiveQuery(state.query);

                if (effectiveQuery.isEmpty) {
                  return const _SearchPlaceholder();
                }

                final emptyStateMessage = state.query.isNotEmpty
                    ? 'No jokes found'
                    : '';
                return JokeListViewer(
                  dataSource: _dataSource,
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

  String _effectiveQuery(String raw) {
    const prefix = JokeConstants.searchQueryPrefix;
    return (raw.startsWith(prefix) ? raw.substring(prefix.length) : raw).trim();
  }
}

class _SearchPlaceholder extends StatelessWidget {
  const _SearchPlaceholder();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        _SearchScreenState._emptyStateMessage,
        key: Key('search_screen-empty-state'),
      ),
    );
  }
}
