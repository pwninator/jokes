import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeListDataSource extends Mock implements JokeListDataSource {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(FirebaseMocks.reset);

  Future<void> pumpFrames(
    WidgetTester tester, {
    int iterations = 5,
    Duration step = const Duration(milliseconds: 50),
  }) async {
    for (var i = 0; i < iterations; i++) {
      await tester.pump(step);
    }
  }

  group('JokeListViewer Incremental Loading', () {
    testWidgets(
      'shows loading indicator on first-load when data source is loading',
      (tester) async {
        final mockDataSource = MockJokeListDataSource();

        // Build providers to simulate first-load loading state
        final loadingItemsProvider = Provider<AsyncValue<List<JokeWithDate>>>(
          (ref) => const AsyncValue<List<JokeWithDate>>.loading(),
        );
        final hasMoreProvider = Provider<bool>((ref) => true);
        final isLoadingProvider = Provider<bool>((ref) => true);

        when(() => mockDataSource.items).thenReturn(loadingItemsProvider);
        when(() => mockDataSource.hasMore).thenReturn(hasMoreProvider);
        when(() => mockDataSource.isLoading).thenReturn(isLoadingProvider);
        when(() => mockDataSource.loadMore()).thenAnswer((_) async {});

        final container = ProviderContainer(
          overrides: FirebaseMocks.getFirebaseProviderOverrides(),
        );
        addTearDown(container.dispose);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Scaffold(
                body: JokeListViewer(
                  viewerId: 'test',
                  jokeContext: 'test',
                  dataSource: mockDataSource,
                ),
              ),
            ),
          ),
        );

        await tester.pump();

        // Should show a CircularProgressIndicator during first-load
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        // And not show the empty-state text
        expect(find.text('No jokes found! Try adding some.'), findsNothing);
      },
    );
    testWidgets('triggers loadMore when user scrolls to threshold', (
      tester,
    ) async {
      // Create a mock data source
      final mockDataSource = MockJokeListDataSource();

      // Create 10 sample jokes
      final jokes = List.generate(
        10,
        (i) => JokeWithDate(
          joke: Joke(
            id: 'joke$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
            setupImageUrl: 'setup$i.png',
            punchlineImageUrl: 'punchline$i.png',
          ),
        ),
      );

      // Set up the mock to return jokes
      final itemsProvider = Provider<AsyncValue<List<JokeWithDate>>>(
        (ref) => AsyncValue.data(jokes),
      );
      final hasMoreProvider = Provider<bool>((ref) => true);
      final isLoadingProvider = Provider<bool>((ref) => false);

      when(() => mockDataSource.items).thenReturn(itemsProvider);
      when(() => mockDataSource.hasMore).thenReturn(hasMoreProvider);
      when(() => mockDataSource.isLoading).thenReturn(isLoadingProvider);
      when(() => mockDataSource.loadMore()).thenAnswer((_) async => {});

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(),
      );
      addTearDown(container.dispose);

      // Build the viewer
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                viewerId: 'test',
                jokeContext: 'test',
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      // Build a couple frames (avoid pumpAndSettle due to timers/animations)
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Verify first joke rendered (via JokeCard key by id)
      expect(find.byKey(const Key('joke0')), findsOneWidget);

      // Scroll to joke at index 5 (threshold is 5, so remaining = 10-1-5 = 4 <= 5)
      final pageView = find.byKey(const Key('joke_viewer_page_view'));
      expect(pageView, findsOneWidget);

      // Simulate scrolling by calling the page controller
      final pageController =
          tester.widget<PageView>(pageView).controller as PageController;

      // Jump to page 5
      pageController.jumpToPage(5);
      await pumpFrames(tester);

      // Verify viewer reported viewing index to data source (threshold logic lives in notifier)
      verify(() => mockDataSource.updateViewingIndex(5)).called(1);
    });

    testWidgets('does not trigger loadMore when hasMore is false', (
      tester,
    ) async {
      final mockDataSource = MockJokeListDataSource();

      final jokes = List.generate(
        10,
        (i) => JokeWithDate(
          joke: Joke(
            id: 'joke$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
            setupImageUrl: 'setup$i.png',
            punchlineImageUrl: 'punchline$i.png',
          ),
        ),
      );

      final itemsProvider = Provider<AsyncValue<List<JokeWithDate>>>(
        (ref) => AsyncValue.data(jokes),
      );
      final hasMoreProvider = Provider<bool>((ref) => false); // No more jokes
      final isLoadingProvider = Provider<bool>((ref) => false);

      when(() => mockDataSource.items).thenReturn(itemsProvider);
      when(() => mockDataSource.hasMore).thenReturn(hasMoreProvider);
      when(() => mockDataSource.isLoading).thenReturn(isLoadingProvider);
      when(() => mockDataSource.loadMore()).thenAnswer((_) async => {});

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                viewerId: 'test',
                jokeContext: 'test',
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      await pumpFrames(tester);

      // Scroll to page 5
      final pageView = find.byKey(const Key('joke_viewer_page_view'));
      final pageController =
          tester.widget<PageView>(pageView).controller as PageController;

      pageController.jumpToPage(5);
      await pumpFrames(tester);

      // Verify loadMore was NOT called (hasMore is false)
      verifyNever(() => mockDataSource.loadMore());
    });

    testWidgets('does not trigger loadMore when isLoading is true', (
      tester,
    ) async {
      final mockDataSource = MockJokeListDataSource();

      final jokes = List.generate(
        10,
        (i) => JokeWithDate(
          joke: Joke(
            id: 'joke$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
            setupImageUrl: 'setup$i.png',
            punchlineImageUrl: 'punchline$i.png',
          ),
        ),
      );

      final itemsProvider = Provider<AsyncValue<List<JokeWithDate>>>(
        (ref) => AsyncValue.data(jokes),
      );
      final hasMoreProvider = Provider<bool>((ref) => true);
      final isLoadingProvider = Provider<bool>(
        (ref) => true,
      ); // Already loading

      when(() => mockDataSource.items).thenReturn(itemsProvider);
      when(() => mockDataSource.hasMore).thenReturn(hasMoreProvider);
      when(() => mockDataSource.isLoading).thenReturn(isLoadingProvider);
      when(() => mockDataSource.loadMore()).thenAnswer((_) async => {});

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                viewerId: 'test',
                jokeContext: 'test',
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      await pumpFrames(tester);

      // Scroll to page 5
      final pageView = find.byKey(const Key('joke_viewer_page_view'));
      final pageController =
          tester.widget<PageView>(pageView).controller as PageController;

      pageController.jumpToPage(5);
      await pumpFrames(tester);

      // Verify loadMore was NOT called (isLoading is true)
      verifyNever(() => mockDataSource.loadMore());
    });
  });
}
