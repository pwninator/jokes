import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/book_creator/book_creator_providers.dart';
import 'package:snickerdoodle/src/features/book_creator/joke_selector_screen.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class MockNavigatorObserver extends Mock implements NavigatorObserver {}

class FakeRoute extends Fake implements Route<dynamic> {}

class FakeSelectedJokes extends SelectedJokes {
  FakeSelectedJokes(this.initialState);
  final List<Joke> initialState;

  @override
  List<Joke> build() => initialState;

  @override
  void toggleJokeSelection(Joke joke) {
    if (state.any((j) => j.id == joke.id)) {
      state = state.where((j) => j.id != joke.id).toList();
    } else {
      state = [...state, joke];
    }
  }
}

class FakeJokeSearchQuery extends JokeSearchQuery {
  FakeJokeSearchQuery(this.query);
  final String query;

  @override
  String build() => query;

  @override
  void setQuery(String query) {
    state = query;
  }
}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeRoute());
  });

  final mockJokes = List.generate(
    5,
    (index) => Joke(
      id: 'joke-$index',
      setupText: 'Setup $index',
      punchlineText: 'Punchline $index',
      numSaves: index * 10,
      numShares: index * 5,
    ),
  );

  Widget createTestWidget(List<Override> overrides) {
    return ProviderScope(
      overrides: [
        selectedJokesProvider.overrideWith(() => FakeSelectedJokes([])),
        ...overrides,
      ],
      child: const MaterialApp(home: JokeSelectorScreen()),
    );
  }

  group('JokeSelectorScreen', () {
    testWidgets('renders search field and button', (tester) async {
      await tester.pumpWidget(
        createTestWidget([
          searchedJokesProvider.overrideWith((ref) async => []),
        ]),
      );

      expect(
        find.byKey(const Key('joke_selector_screen-search-field')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('joke_selector_screen-select-jokes-button')),
        findsOneWidget,
      );
    });

    testWidgets('shows loading indicator while searching', (tester) async {
      await tester.pumpWidget(
        createTestWidget([
          searchedJokesProvider.overrideWith(
            (ref) => Future.delayed(const Duration(seconds: 1), () => []),
          ),
        ]),
      );

      await tester.enterText(
        find.byKey(const Key('joke_selector_screen-search-field')),
        'test',
      );
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('displays jokes when search is successful', (tester) async {
      await tester.pumpWidget(
        createTestWidget([
          searchedJokesProvider.overrideWith((ref) async => mockJokes),
          jokeSearchQueryProvider.overrideWith(
            () => FakeJokeSearchQuery('test'),
          ),
        ]),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('joke_selector_screen-jokes-list')),
        findsOneWidget,
      );
      expect(
        find.byKey(Key('joke_selector_screen-joke-tile-${mockJokes.first.id}')),
        findsOneWidget,
      );
    });

    testWidgets('toggles joke selection on tap', (tester) async {
      await tester.pumpWidget(
        createTestWidget([
          searchedJokesProvider.overrideWith((ref) async => mockJokes),
          jokeSearchQueryProvider.overrideWith(
            () => FakeJokeSearchQuery('test'),
          ),
          selectedJokesProvider.overrideWith(() => FakeSelectedJokes([])),
        ]),
      );
      await tester.pumpAndSettle();

      final element = tester.element(find.byType(JokeSelectorScreen));
      final container = ProviderScope.containerOf(element);

      final firstJokeTile = find.byKey(
        const Key('joke_selector_screen-joke-tile-joke-0'),
      );
      expect(firstJokeTile, findsOneWidget);
      expect(container.read(selectedJokesProvider), isEmpty);

      await tester.tap(firstJokeTile);
      await tester.pump();

      expect(container.read(selectedJokesProvider).length, 1);
      expect(container.read(selectedJokesProvider).first.id, 'joke-0');

      await tester.tap(firstJokeTile);
      await tester.pump();

      expect(container.read(selectedJokesProvider), isEmpty);
    });

    testWidgets('pops screen when "Select Jokes" is tapped', (tester) async {
      final mockObserver = MockNavigatorObserver();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            searchedJokesProvider.overrideWith((ref) async => []),
            selectedJokesProvider.overrideWith(() => FakeSelectedJokes([])),
          ],
          child: MaterialApp(
            home: const JokeSelectorScreen(),
            navigatorObservers: [mockObserver],
          ),
        ),
      );

      await tester.tap(
        find.byKey(const Key('joke_selector_screen-select-jokes-button')),
      );
      await tester.pumpAndSettle();

      verify(() => mockObserver.didPop(any(), any())).called(1);
    });
  });
}
