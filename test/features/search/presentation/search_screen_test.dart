import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Submitting <2 chars shows banner and does not update query', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          // Prevent real cloud function calls during this test
          searchResultsViewerProvider(SearchScope.userJokeSearch).overrideWith(
            (ref) => const AsyncValue.data([]),
          ),
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
    final field = find.byKey(const Key('search-tab-search-field'));
    expect(field, findsOneWidget);
    await tester.enterText(field, 'a');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Verify MaterialBanner is shown
    expect(find.text('Please enter a longer search query'), findsOneWidget);

    // Provider should still have empty query
    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );
  });

  testWidgets('Shows results count for single result', (tester) async {
    final overrides = FirebaseMocks.getFirebaseProviderOverrides(
      additionalOverrides: [
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

    await tester.pumpWidget(
      ProviderScope(
        overrides: overrides,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search-tab-search-field'));
    await tester.enterText(field, 'cat');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);
  });

  testWidgets('Shows pluralized results count for multiple results', (
    tester,
  ) async {
    final overrides = FirebaseMocks.getFirebaseProviderOverrides(
      additionalOverrides: [
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

    await tester.pumpWidget(
      ProviderScope(
        overrides: overrides,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search-tab-search-field'));
    await tester.enterText(field, 'dog');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('3 results'), findsOneWidget);
  });

  testWidgets('Search results show 1-based index titles on JokeCards', (
    tester,
  ) async {
    final overrides = FirebaseMocks.getFirebaseProviderOverrides(
      additionalOverrides: [
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

    await tester.pumpWidget(
      ProviderScope(
        overrides: overrides,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );

    final field = find.byKey(const Key('search-tab-search-field'));
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

    final field = find.byKey(const Key('search-tab-search-field'));
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

    final fieldAfter = find.byKey(const Key('search-tab-search-field'));
    expect(fieldAfter, findsOneWidget);
    final textFieldWidget = tester.widget<TextField>(fieldAfter);
    expect(textFieldWidget.controller?.text, 'penguins');
  });
}
