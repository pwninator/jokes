import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeListDataSource extends Mock implements JokeListDataSource {}

class _MockPerf extends Mock implements PerformanceService {}

// Test repository that properly handles streams
class _TestInteractionsRepo extends JokeInteractionsRepository {
  _TestInteractionsRepo({required super.db, required PerformanceService perf})
      : super(performanceService: perf);

  final _controllers = <String, StreamController<JokeInteraction?>>{};

  @override
  Stream<JokeInteraction?> watchJokeInteraction(String jokeId) {
    // Reuse existing controller for this jokeId or create a new one
    if (!_controllers.containsKey(jokeId)) {
      final controller = StreamController<JokeInteraction?>.broadcast();
      _controllers[jokeId] = controller;
      // Add initial value
      controller.add(null);
    }
    return _controllers[jokeId]!.stream;
  }

  void dispose() {
    for (final controller in _controllers.values) {
      controller.close();
    }
    _controllers.clear();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(FirebaseMocks.reset);

  ProviderContainer createContainer({List<Override> overrides = const []}) {
    return ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        // Override jokeInteractionsRepository to return working streams
        jokeInteractionsRepositoryProvider.overrideWith((ref) {
          return _TestInteractionsRepo(
            db: AppDatabase.inMemory(),
            perf: _MockPerf(),
          );
        }),
        // Override categoryInteractionsRepository
        categoryInteractionsRepositoryProvider.overrideWith((ref) {
          return CategoryInteractionsRepository(
            db: AppDatabase.inMemory(),
            performanceService: _MockPerf(),
          );
        }),
        ...overrides,
      ],
    );
  }

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

        final container = createContainer();
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

      final container = createContainer();
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

      final container = createContainer();
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

      final container = createContainer();
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
