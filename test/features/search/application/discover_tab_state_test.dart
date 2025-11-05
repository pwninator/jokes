import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/search/application/discover_tab_state.dart';

void main() {
  testWidgets('resetDiscoverTabState clears discover providers', (
    tester,
  ) async {
    final container = ProviderContainer();
    final category = JokeCategory(
      id: 'animals',
      displayName: 'Animal Jokes',
      jokeDescriptionQuery: 'animal',
      imageUrl: null,
      state: JokeCategoryState.approved,
      type: CategoryType.firestore,
    );

    container.read(activeCategoryProvider.notifier).state = category;

    final searchNotifier = container.read(
      searchQueryProvider(SearchScope.category).notifier,
    );
    searchNotifier.state = searchNotifier.state.copyWith(
      query: 'test query',
      excludeJokeIds: const ['a'],
      label: SearchLabel.category,
    );

    container
            .read(jokeViewerPageIndexProvider(discoverViewerId).notifier)
            .state =
        3;

    late WidgetRef capturedRef;
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: Consumer(
          builder: (context, ref, _) {
            capturedRef = ref;
            return const SizedBox.shrink();
          },
        ),
      ),
    );

    resetDiscoverTabState(capturedRef);
    await tester.pump();

    expect(container.read(activeCategoryProvider), isNull);
    final searchState = container.read(
      searchQueryProvider(SearchScope.category),
    );
    expect(searchState.query, '');
    expect(searchState.label, SearchLabel.none);
    expect(searchState.excludeJokeIds, isEmpty);
    expect(container.read(jokeViewerPageIndexProvider(discoverViewerId)), 0);
  });

  testWidgets('resetDiscoverSearchState clears user search query', (
    tester,
  ) async {
    final container = ProviderContainer();

    final searchNotifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    searchNotifier.state = searchNotifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}animals',
      excludeJokeIds: const ['abc'],
      label: SearchLabel.category,
    );

    container
            .read(jokeViewerPageIndexProvider(discoverSearchViewerId).notifier)
            .state =
        5;

    late WidgetRef capturedRef;
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: Consumer(
          builder: (context, ref, _) {
            capturedRef = ref;
            return const SizedBox.shrink();
          },
        ),
      ),
    );

    resetDiscoverSearchState(capturedRef);
    await tester.pump();

    final searchState = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchState.query, '');
    expect(searchState.label, JokeConstants.userSearchLabel);
    expect(searchState.excludeJokeIds, isEmpty);
    expect(
      container.read(jokeViewerPageIndexProvider(discoverSearchViewerId)),
      0,
    );
  });
}
