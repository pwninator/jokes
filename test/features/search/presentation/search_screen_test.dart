import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  ProviderContainer createContainer({List<Override> overrides = const []}) {
    return ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          searchResultsViewerProvider(
            SearchScope.userJokeSearch,
          ).overrideWith((ref) => Stream.value(const <JokeWithDate>[])),
          ...overrides,
        ],
      ),
    );
  }

  Future<void> pumpSearch(
    WidgetTester tester,
    ProviderContainer container,
  ) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );
    await tester.pump();
  }

  testWidgets('focuses the search field on load', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final fieldFinder = find.byKey(const Key('search_screen-search-field'));
    final textField = tester.widget<TextField>(fieldFinder);
    expect(textField.focusNode?.hasFocus, isTrue);
  });

  testWidgets('opening the screen clears any existing query', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    final notifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = notifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}legacy',
      label: SearchLabel.category,
    );

    await pumpSearch(tester, container);

    final cleared = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(cleared.query, '');
    expect(cleared.label, JokeConstants.userSearchLabel);
    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
  });

  testWidgets('submitting <2 chars shows banner and preserves query', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'a');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.text('Please enter a longer search query'), findsOneWidget);
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.query, '');
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('renders single-result count', (tester) async {
    final container = createContainer(
      overrides: [
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => const [JokeSearchResult(id: '1', vectorDistance: 0.0)],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 's',
              punchlineText: 'p',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'cats');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);
  });

  testWidgets('renders pluralised result count', (tester) async {
    final container = createContainer(
      overrides: [
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => [
            const JokeSearchResult(id: '1', vectorDistance: 0.1),
            const JokeSearchResult(id: '2', vectorDistance: 0.2),
          ],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 'a',
              punchlineText: 'b',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
        jokeStreamByIdProvider('2').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '2',
              setupText: 'c',
              punchlineText: 'd',
              setupImageUrl: 'c',
              punchlineImageUrl: 'd',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'robots');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.text('2 results'), findsOneWidget);
  });

  testWidgets('shows placeholder when no query has been submitted', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
    expect(find.byKey(const Key('search-results-count')), findsNothing);
  });

  testWidgets('clear button resets provider and restores placeholder', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'space cows');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '${JokeConstants.searchQueryPrefix}space cows',
    );

    final clearBtn = find.byKey(const Key('search_screen-clear-button'));
    expect(clearBtn, findsOneWidget);

    await tester.tap(clearBtn);
    await tester.pump();

    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );
    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
  });

  testWidgets('manual typing sets search label to none', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'manual search');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(
      searchQuery.query,
      '${JokeConstants.searchQueryPrefix}manual search',
    );
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('prefilled similar search preserves query and shows count', (
    tester,
  ) async {
    final container = createContainer(
      overrides: [
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => const [JokeSearchResult(id: '1', vectorDistance: 0.0)],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 'setup',
              punchlineText: 'punch',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    // Programmatically set a Similar Search before opening screen
    final notifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = notifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}cats and dogs',
      label: SearchLabel.similarJokes,
    );

    await pumpSearch(tester, container);
    await tester.pumpAndSettle();

    // Text field shows the effective query (without prefix)
    final fieldFinder = find.byKey(const Key('search_screen-search-field'));
    final textField = tester.widget<TextField>(fieldFinder);
    expect(textField.controller?.text, 'cats and dogs');

    // Results count appears (since query preserved and provider returns 1)
    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);

    // Label remains similarJokes
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.label, SearchLabel.similarJokes);
  });
}
