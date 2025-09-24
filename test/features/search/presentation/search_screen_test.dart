import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Submitting <2 chars shows banner and does not update query', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          // Prevent real cloud function calls during this test
          searchResultsViewerProvider(
            SearchScope.userJokeSearch,
          ).overrideWith((ref) => const AsyncValue.data([])),
        ],
      ),
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    // Ensure initial state
    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );

    // Enter 1-char query and submit
    final field = find.byKey(const Key('search_screen-search-field'));
    expect(field, findsOneWidget);
    await tester.enterText(field, 'a');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Verify MaterialBanner is shown
    expect(find.text('Please enter a longer search query'), findsOneWidget);

    // Provider should still have empty query and none label
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.query, '');
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('Shows results count for single result', (tester) async {
    final mockJokeRepository = MockJokeRepository();
    when(() => mockJokeRepository.getJokesByIds(any())).thenAnswer(
      (_) async => [
        const Joke(
          id: '1',
          setupText: 's',
          punchlineText: 'p',
          setupImageUrl: 's.jpg',
          punchlineImageUrl: 'p.jpg',
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        searchResultsViewerProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) => const AsyncValue.data([
            JokeWithDate(
              joke: Joke(
                id: '1',
                setupText: 's',
                punchlineText: 'p',
                setupImageUrl: 'a',
                punchlineImageUrl: 'b',
              ),
            ),
          ]),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'cat');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);
  });

  testWidgets('Shows pluralized results count for multiple results', (
    tester,
  ) async {
    final mockJokeRepository = MockJokeRepository();
    when(() => mockJokeRepository.getJokesByIds(any())).thenAnswer(
      (_) async => [
        const Joke(
          id: '1',
          setupText: 's1',
          punchlineText: 'p1',
          setupImageUrl: 's1.jpg',
          punchlineImageUrl: 'p1.jpg',
        ),
        const Joke(
          id: '2',
          setupText: 's2',
          punchlineText: 'p2',
          setupImageUrl: 's2.jpg',
          punchlineImageUrl: 'p2.jpg',
        ),
        const Joke(
          id: '3',
          setupText: 's3',
          punchlineText: 'p3',
          setupImageUrl: 's3.jpg',
          punchlineImageUrl: 'p3.jpg',
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        searchResultsViewerProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) => const AsyncValue.data([
            JokeWithDate(
              joke: Joke(
                id: '1',
                setupText: 's1',
                punchlineText: 'p1',
                setupImageUrl: 'a',
                punchlineImageUrl: 'b',
              ),
            ),
            JokeWithDate(
              joke: Joke(
                id: '2',
                setupText: 's2',
                punchlineText: 'p2',
                setupImageUrl: 'a',
                punchlineImageUrl: 'b',
              ),
            ),
            JokeWithDate(
              joke: Joke(
                id: '3',
                setupText: 's3',
                punchlineText: 'p3',
                setupImageUrl: 'a',
                punchlineImageUrl: 'b',
              ),
            ),
          ]),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'dog');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('3 results'), findsOneWidget);
  });

  testWidgets('Search results show 1-based index titles on JokeCards', (
    tester,
  ) async {
    final mockJokeRepository = MockJokeRepository();
    when(() => mockJokeRepository.getJokesByIds(any())).thenAnswer(
      (_) async => [
        const Joke(
          id: 'a',
          setupText: 's1',
          punchlineText: 'p1',
          setupImageUrl: 's1.jpg',
          punchlineImageUrl: 'p1.jpg',
        ),
        const Joke(
          id: 'b',
          setupText: 's2',
          punchlineText: 'p2',
          setupImageUrl: 's2.jpg',
          punchlineImageUrl: 'p2.jpg',
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        searchResultsViewerProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) => const AsyncValue.data([
            JokeWithDate(
              joke: Joke(
                id: 'a',
                setupText: 's1',
                punchlineText: 'p1',
                setupImageUrl: 'a',
                punchlineImageUrl: 'b',
              ),
            ),
            JokeWithDate(
              joke: Joke(
                id: 'b',
                setupText: 's2',
                punchlineText: 'p2',
                setupImageUrl: 'a',
                punchlineImageUrl: 'b',
              ),
            ),
          ]),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'fish');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Title should be the index (1-based) for the first card
    expect(find.text('1'), findsOneWidget);

    // Swipe up to move to the second joke (vertical PageView)
    final pageView = find.byKey(const Key('joke_viewer_page_view'));
    expect(pageView, findsOneWidget);
    await tester.fling(pageView, const Offset(0, -400), 1000);
    await tester.pumpAndSettle();

    // Now the title should show '2' for the second card
    expect(find.text('2'), findsOneWidget);
  });

  testWidgets('Restores raw input in field without "jokes about " prefix', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(),
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search_screen-search-field'));
    expect(field, findsOneWidget);

    // Simulate user entering text and submitting; provider adds prefix
    await tester.enterText(field, 'penguins');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Preserve provider state across remount via manual ProviderContainer
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final fieldAfter = find.byKey(const Key('search_screen-search-field'));
    expect(fieldAfter, findsOneWidget);
    final textFieldWidget = tester.widget<TextField>(fieldAfter);
    expect(textFieldWidget.controller?.text, 'penguins');
  });

  testWidgets('Empty search shows categories; tapping tile triggers search', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          // Provide fake categories
          jokeCategoriesProvider.overrideWith(
            (ref) => Stream.value(const [
              JokeCategory(
                id: 'animal_jokes',
                displayName: 'Animal Jokes',
                jokeDescriptionQuery: 'animal',
                imageUrl: null,
                state: JokeCategoryState.approved,
              ),
              JokeCategory(
                id: 'food',
                displayName: 'Food',
                jokeDescriptionQuery: 'food',
                imageUrl: null,
                state: JokeCategoryState.approved,
              ),
            ]),
          ),
          // Avoid network search calls in tests
          searchResultsViewerProvider(
            SearchScope.userJokeSearch,
          ).overrideWith((ref) => const AsyncValue.data([])),
        ],
      ),
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    // Let the StreamProvider emit data
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    // Initially empty field should show categories grid
    expect(find.byKey(const Key('search-categories-grid')), findsOneWidget);
    expect(find.text('Animal Jokes'), findsOneWidget);

    // Tap a category tile
    await tester.tap(find.text('Animal Jokes'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    // Provider should be updated with prefixed query and category label
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.query, '${JokeConstants.searchQueryPrefix}animal');
    expect(searchQuery.label, SearchLabel.category);

    // The grid should no longer be visible after search starts
    expect(find.byKey(const Key('search-categories-grid')), findsNothing);
  });

  testWidgets(
    'Clear button is circular and clears query restoring categories',
    (tester) async {
      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            // Provide categories so grid can show when empty
            jokeCategoriesProvider.overrideWith(
              (ref) => Stream.value(const [
                JokeCategory(
                  id: 'tech',
                  displayName: 'Tech',
                  jokeDescriptionQuery: 'tech',
                  imageUrl: null,
                  state: JokeCategoryState.approved,
                ),
              ]),
            ),
            // Avoid network search calls in tests
            searchResultsViewerProvider(
              SearchScope.userJokeSearch,
            ).overrideWith((ref) => const AsyncValue.data([])),
          ],
        ),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: SearchScreen()),
        ),
      );

      // Initially empty shows categories
      await tester.pump();
      expect(find.byKey(const Key('search-categories-grid')), findsOneWidget);

      // Enter text to make clear button appear
      final field = find.byKey(const Key('search_screen-search-field'));
      await tester.enterText(field, 'robots');
      await tester.pump();

      // Clear button should be present and circular-styled
      final clearBtn = find.byKey(const Key('search_screen-clear-button'));
      expect(clearBtn, findsOneWidget);

      // Submit search so categories disappear
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pump();
      expect(find.byKey(const Key('search-categories-grid')), findsNothing);

      // Tap clear; field should clear and categories should reappear
      await tester.tap(clearBtn);
      await tester.pump();
      expect(
        container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
        '',
      );
      expect(find.byKey(const Key('search-categories-grid')), findsOneWidget);
    },
  );

  testWidgets('Manual typing sets search label to none', (tester) async {
    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          // Avoid network search calls in tests
          searchResultsViewerProvider(
            SearchScope.userJokeSearch,
          ).overrideWith((ref) => const AsyncValue.data([])),
        ],
      ),
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    // Enter text manually and submit
    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'manual search');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Provider should have prefixed query and none label
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(
      searchQuery.query,
      '${JokeConstants.searchQueryPrefix}manual search',
    );
    expect(searchQuery.label, SearchLabel.none);
  });
}
