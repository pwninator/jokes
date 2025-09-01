import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart'
    show MatchMode;
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
        _controller.text = currentQuery;
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _onSubmitted(String raw) {
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
    final current = ref.read(searchQueryProvider(SearchScope.userJokeSearch));
    ref
        .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
        .state = current.copyWith(
      query: "jokes about $query",
      maxResults: 50,
      publicOnly: true,
      matchMode: MatchMode.tight,
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
              key: const Key('search-tab-search-field'),
              controller: _controller,
              focusNode: _focusNode,
              decoration: InputDecoration(
                hintText: 'Search for jokes!',
                prefixIcon: const Icon(Icons.search),
                isDense: true,
                border: const OutlineInputBorder(),
                suffixIcon: _controller.text.isNotEmpty
                    ? IconButton(
                        tooltip: 'Clear',
                        icon: const Icon(Icons.clear),
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
                          );
                          FocusScope.of(context).unfocus();
                        },
                      )
                    : null,
              ),
              maxLines: 1,
              textInputAction: TextInputAction.search,
              onSubmitted: _onSubmitted,
            ),
          ),
          Expanded(
            child: Consumer(
              builder: (context, ref, child) {
                final currentQuery = ref
                    .watch(searchQueryProvider(SearchScope.userJokeSearch))
                    .query;
                final emptyStateMessage = currentQuery.isNotEmpty
                    ? 'No jokes found'
                    : 'Search for jokes!';
                return JokeListViewer(
                  jokesAsyncProvider: searchResultsViewerProvider(
                    SearchScope.userJokeSearch,
                  ),
                  jokeContext: AnalyticsJokeContext.search,
                  onInitRegisterReset: (cb) => _resetViewer = cb,
                  emptyState: Center(child: Text(emptyStateMessage)),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
