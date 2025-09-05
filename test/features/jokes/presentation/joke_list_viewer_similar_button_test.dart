import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

// Stub navigation helpers to avoid real routing in tests
class StubNavigationHelpers extends NavigationHelpers {
  StubNavigationHelpers(super.ref);
  @override
  void navigateToRoute(
    String route, {
    String method = 'programmatic',
    bool push = false,
  }) {
    // no-op for tests
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    registerAnalyticsFallbackValues();
  });

  testWidgets('Similar button visible only when flag enabled', (tester) async {
    final joke = const Joke(
      id: '1',
      setupText: 'A funny setup',
      punchlineText: 'A punchline',
      setupImageUrl: 'https://example.com/s.jpg',
      punchlineImageUrl: 'https://example.com/p.jpg',
      tags: ['animals'],
    );

    final overrides = FirebaseMocks.getFirebaseProviderOverrides();

    // With flag off
    await tester.pumpWidget(
      ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          home: JokeListViewer(
            jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
            jokeContext: 'daily_jokes',
            showSimilarSearchButton: false,
          ),
        ),
      ),
    );

    expect(find.text('Similar'), findsNothing);

    // With flag on
    await tester.pumpWidget(
      ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          home: JokeListViewer(
            jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
            jokeContext: 'daily_jokes',
            showSimilarSearchButton: true,
          ),
        ),
      ),
    );

    expect(find.text('Similar'), findsOneWidget);
  });

  testWidgets('Similar button updates search query and navigates', (
    tester,
  ) async {
    final analyticsMock = AnalyticsMocks.mockAnalyticsService;
    final joke = const Joke(
      id: '1',
      setupText: 'Penguin antics',
      punchlineText: 'A punchline',
      setupImageUrl: 'https://example.com/s.jpg',
      punchlineImageUrl: 'https://example.com/p.jpg',
      tags: ['penguins'],
    );

    final container = ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        analyticsServiceProvider.overrideWithValue(analyticsMock),
        navigationHelpersProvider.overrideWith(
          (ref) => StubNavigationHelpers(ref),
        ),
        // Avoid real cloud function calls
        searchResultIdsProvider(
          SearchScope.userJokeSearch,
        ).overrideWith((ref) async => const []),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: RailHost(
            railWidth: 180,
            child: JokeListViewer(
              jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
              jokeContext: 'daily_jokes',
              showSimilarSearchButton: true,
            ),
          ),
        ),
      ),
    );

    // Tap Similar (use key for reliable hit-testing)
    final similarFinder = find.byKey(const Key('similar-search-button'));
    await tester.ensureVisible(similarFinder);
    await tester.tap(similarFinder, warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 50));

    final query = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(
      query.query,
      '${JokeConstants.searchQueryPrefix}Penguin antics A punchline',
    );
    // Should exclude the initiating joke id
    expect(query.excludeJokeIds, ['1']);

    // Verify analytics call for joke_search_similar
    verify(
      () => analyticsMock.logJokeSearchSimilar(
        queryLength: any(named: 'queryLength'),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).called(1);
  });
}
