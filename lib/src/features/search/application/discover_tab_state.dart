import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';

/// Viewer identifier shared across Discover tab surfaces.
const discoverViewerId = 'discover_category';

/// Viewer identifier shared across the Discover -> Search handoff.
const discoverSearchViewerId = 'search_user';

/// Reset Discover tab state so that returning users see the category grid again.
void resetDiscoverTabState(WidgetRef ref) {
  final activeCategory = ref.read(activeCategoryProvider);
  if (activeCategory == null) {
    // Still ensure the viewer index is reset so pagination resumes at the start.
    ref.read(jokeViewerPageIndexProvider(discoverViewerId).notifier).state = 0;
    return;
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
  ref.read(jokeViewerPageIndexProvider(discoverViewerId).notifier).state = 0;
}

void resetDiscoverSearchState(WidgetRef ref) {
  final searchNotifier = ref.read(
    searchQueryProvider(SearchScope.userJokeSearch).notifier,
  );
  searchNotifier.state = const SearchQuery(
    query: '',
    maxResults: JokeConstants.userSearchMaxResults,
    publicOnly: JokeConstants.userSearchPublicOnly,
    matchMode: JokeConstants.userSearchMatchMode,
    excludeJokeIds: [],
    label: JokeConstants.userSearchLabel,
  );

  ref.read(jokeViewerPageIndexProvider(discoverSearchViewerId).notifier).state =
      0;
}
