import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
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
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();

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
      query: query,
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
                          setState(() {});
                          FocusScope.of(context).unfocus();
                        },
                      )
                    : null,
              ),
              maxLines: 1,
              textInputAction: TextInputAction.search,
              onSubmitted: _onSubmitted,
              onChanged: (_) => setState(() {}),
            ),
          ),
          Expanded(
            child: JokeListViewer(
              jokesAsyncProvider: searchResultsViewerProvider(
                SearchScope.userJokeSearch,
              ),
              jokeContext: AnalyticsJokeContext.search,
              onInitRegisterReset: (cb) => _resetViewer = cb,
              showCtaWhenEmpty: false,
              emptyState: const Center(child: Text('Search for jokes!')),
            ),
          ),
        ],
      ),
    );
  }
}
