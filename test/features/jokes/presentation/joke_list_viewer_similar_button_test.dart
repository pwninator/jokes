import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

// Mock classes
class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

class MockPerformanceService extends Mock implements PerformanceService {}

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
  setUpAll(() {
    registerAnalyticsFallbackValues();
    registerFallbackValue(MockJokeInteractionsRepository());
    registerFallbackValue(MockCategoryInteractionsRepository());
    registerFallbackValue(MockPerformanceService());
  });

  late MockJokeInteractionsRepository mockJokeInteractionsRepository;
  late MockCategoryInteractionsRepository mockCategoryInteractionsRepository;

  setUp(() {
    mockJokeInteractionsRepository = MockJokeInteractionsRepository();
    mockCategoryInteractionsRepository = MockCategoryInteractionsRepository();

    // Stub default behavior
    when(
      () => mockJokeInteractionsRepository.watchJokeInteraction(any()),
    ).thenAnswer((_) => Stream.value(null));
    when(
      () => mockCategoryInteractionsRepository.setViewed(any()),
    ).thenAnswer((_) async => true);
  });

  group('JokeListViewer Similar Button', () {
    testWidgets('Similar button visible only when flag enabled', (
      tester,
    ) async {
      // Arrange: Create test joke
      final joke = const Joke(
        id: '1',
        setupText: 'A funny setup',
        punchlineText: 'A punchline',
        setupImageUrl: 'https://example.com/s.jpg',
        punchlineImageUrl: 'https://example.com/p.jpg',
        tags: ['animals'],
      );

      final overrides = [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
      ];

      // Act & Assert: With flag off
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: JokeListViewer(
              key: const Key('joke_list_viewer_similar_button_test-flag_off'),
              jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
              jokeContext: 'daily_jokes',
              viewerId: 'sim_button_off',
              showSimilarSearchButton: false,
            ),
          ),
        ),
      );

      expect(find.text('Similar'), findsNothing);

      // Act & Assert: With flag on
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: JokeListViewer(
              key: const Key('joke_list_viewer_similar_button_test-flag_on'),
              jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
              jokeContext: 'daily_jokes',
              viewerId: 'sim_button_on',
              showSimilarSearchButton: true,
            ),
          ),
        ),
      );

      expect(find.text('Similar'), findsOneWidget);
    });

    testWidgets('Similar button updates search query and logs analytics', (
      tester,
    ) async {
      // Arrange: Create test joke and analytics mock
      final analyticsMock = AnalyticsMocks.mockAnalyticsService;
      final joke = const Joke(
        id: '1',
        setupText: 'Penguin antics',
        punchlineText: 'A punchline',
        setupImageUrl: 'https://example.com/s.jpg',
        punchlineImageUrl: 'https://example.com/p.jpg',
        tags: ['penguins'],
      );

      final overrides = [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        analyticsServiceProvider.overrideWithValue(analyticsMock),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
        navigationHelpersProvider.overrideWith(
          (ref) => StubNavigationHelpers(ref),
        ),
        // Avoid real cloud function calls
        searchResultIdsProvider(
          SearchScope.userJokeSearch,
        ).overrideWith((ref) async => const []),
      ];

      // Act: Build widget
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: RailHost(
              railWidth: 180,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_similar_button_test-navigation',
                ),
                jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
                jokeContext: 'daily_jokes',
                viewerId: 'sim_button_nav',
                showSimilarSearchButton: true,
              ),
            ),
          ),
        ),
      );

      // Act: Tap Similar button
      final similarFinder = find.byKey(const Key('similar-search-button'));
      await tester.ensureVisible(similarFinder);
      await tester.tap(similarFinder, warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 50));

      // Assert: Verify search query was updated
      final container = ProviderScope.containerOf(
        tester.element(similarFinder),
      );
      final query = container.read(
        searchQueryProvider(SearchScope.userJokeSearch),
      );
      expect(
        query.query,
        '${JokeConstants.searchQueryPrefix}Penguin antics A punchline',
      );
      // Should exclude the initiating joke id
      expect(query.excludeJokeIds, ['1']);

      // Assert: Verify analytics call for joke_search_similar
      verify(
        () => analyticsMock.logJokeSearchSimilar(
          queryLength: any(named: 'queryLength'),
          jokeContext: any(named: 'jokeContext'),
        ),
      ).called(1);
    });

    testWidgets('Similar button handles empty joke text gracefully', (
      tester,
    ) async {
      // Arrange: Create joke with empty text
      final joke = const Joke(
        id: '1',
        setupText: '',
        punchlineText: '',
        setupImageUrl: 'https://example.com/s.jpg',
        punchlineImageUrl: 'https://example.com/p.jpg',
        tags: ['empty'],
      );

      final overrides = [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
        navigationHelpersProvider.overrideWith(
          (ref) => StubNavigationHelpers(ref),
        ),
      ];

      // Act: Build widget
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: JokeListViewer(
              key: const Key('joke_list_viewer_similar_button_test-empty_text'),
              jokesAsyncValue: AsyncValue.data([JokeWithDate(joke: joke)]),
              jokeContext: 'daily_jokes',
              viewerId: 'sim_button_empty',
              showSimilarSearchButton: true,
            ),
          ),
        ),
      );

      // Act: Tap Similar button
      final similarFinder = find.byKey(const Key('similar-search-button'));
      await tester.ensureVisible(similarFinder);
      await tester.tap(similarFinder, warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 50));

      // Assert: Should not crash and should not update search query
      final container = ProviderScope.containerOf(
        tester.element(similarFinder),
      );
      final query = container.read(
        searchQueryProvider(SearchScope.userJokeSearch),
      );
      // Query should remain unchanged (empty or default)
      expect(query.query, isEmpty);
    });
  });
}
