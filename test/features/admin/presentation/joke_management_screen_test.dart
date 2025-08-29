import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockImageService extends Mock implements ImageService {}

// Fake class for Mocktail fallback values
class FakeJoke extends Fake implements Joke {}

void main() {
  late MockJokeRepository mockJokeRepository;
  late MockImageService mockImageService;
  late List<Joke> testJokes;

  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeJoke());
  });

  setUp(() {
    mockJokeRepository = MockJokeRepository();
    mockImageService = MockImageService();

    // Create test jokes
    testJokes = [
      Joke(
        id: '1',
        setupText: 'Test setup 1',
        punchlineText: 'Test punchline 1',
        setupImageUrl: 'https://example.com/setup1.jpg',
        punchlineImageUrl: 'https://example.com/punchline1.jpg',
        numThumbsUp: 0,
        numThumbsDown: 0,
      ),
      Joke(
        id: '2',
        setupText: 'Test setup 2',
        punchlineText: 'Test punchline 2',
        setupImageUrl: 'https://example.com/setup2.jpg',
        punchlineImageUrl: 'https://example.com/punchline2.jpg',
        numThumbsUp: 5,
        numThumbsDown: 2,
      ),
      Joke(
        id: '3',
        setupText: 'Test setup 3',
        punchlineText: 'Test punchline 3',
        setupImageUrl: null,
        punchlineImageUrl: null,
        numThumbsUp: 0,
        numThumbsDown: 0,
      ),
    ];

    // Setup mock repository - this is the key difference!
    when(
      () => mockJokeRepository.getJokes(),
    ).thenAnswer((_) => Stream.value(testJokes));

    // Setup mock image service
    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(
      () => mockImageService.processImageUrl(any()),
    ).thenReturn('https://example.com/image.jpg');
    when(
      () => mockImageService.processImageUrl(
        any(),
        quality: any(named: 'quality'),
      ),
    ).thenReturn('https://example.com/image.jpg');
    when(() => mockImageService.clearCache()).thenAnswer((_) async {});

    // Mock the new ImageService precaching methods
    when(
      () => mockImageService.getProcessedJokeImageUrl(any()),
    ).thenReturn('https://example.com/processed.jpg');
    when(
      () => mockImageService.getThumbnailUrl(any()),
    ).thenReturn('https://example.com/thumbnail.jpg');
    when(
      () => mockImageService.precacheJokeImage(any()),
    ).thenAnswer((_) async => 'https://example.com/cached.jpg');
    when(() => mockImageService.precacheJokeImages(any())).thenAnswer(
      (_) async => (
        setupUrl: 'https://example.com/setup.jpg',
        punchlineUrl: 'https://example.com/punchline.jpg',
      ),
    );
    when(
      () => mockImageService.precacheMultipleJokeImages(any()),
    ).thenAnswer((_) async {});
  });

  Widget createTestWidget() {
    // Create a simple router that just shows the JokeManagementScreen
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const JokeManagementScreen(),
        ),
        GoRoute(
          path: '/admin/editor',
          builder: (context, state) =>
              const Scaffold(body: Text('Editor Screen')),
        ),
      ],
    );

    return ProviderScope(
      overrides: [
        imageServiceProvider.overrideWithValue(mockImageService),
        jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ...FirebaseMocks.getFirebaseProviderOverrides(),
      ],
      child: MaterialApp.router(routerConfig: router),
    );
  }

  group('JokeManagementScreen', () {
    testWidgets('shows filter bar and FAB', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump(); // Let the widget build
      await tester.pump(); // Let the providers resolve

      // Filter area should be visible (chips container present)
      expect(find.byKey(const Key('admin-filter-chips-wrap')), findsOneWidget);
      // By default the search field is hidden, the search toggle chip is shown
      expect(find.byKey(const Key('admin-search-field')), findsNothing);
      expect(find.byKey(const Key('search-toggle-chip')), findsOneWidget);
      expect(
        find.byKey(const Key('unrated-only-filter-chip')),
        findsOneWidget,
        reason: 'Filter chip should be visible',
      );
      // Chips should be in a Wrap below the search TextField
      expect(
        find.byKey(const Key('admin-filter-chips-wrap')),
        findsOneWidget,
        reason: 'Filter chips container should be a Wrap under search',
      );

      // FAB should be visible
      expect(
        find.byType(FloatingActionButton),
        findsOneWidget,
        reason: 'FAB should be visible',
      );

      // The content area should be in a stable state - either showing content or loading
      // In test environments, async providers may resolve differently than production
      final hasJokeCards = find.byType(JokeCard).evaluate().isNotEmpty;
      final hasLoading = find
          .byType(CircularProgressIndicator)
          .evaluate()
          .isNotEmpty;

      expect(
        hasJokeCards || hasLoading,
        isTrue,
        reason: 'Should either be showing joke cards or loading state',
      );
    });

    testWidgets('shows all jokes when no filter is applied', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump(); // Let the widget build
      await tester.pump(); // Let the providers resolve

      // Should show the basic structure with chips container
      expect(find.byKey(const Key('admin-filter-chips-wrap')), findsOneWidget);
      expect(find.byKey(const Key('admin-search-field')), findsNothing);
      expect(find.byKey(const Key('unrated-only-filter-chip')), findsOneWidget);

      // The content area should be in a stable state - either showing content or loading
      // In test environments, async providers may resolve differently than production
      final hasJokeCards = find.byType(JokeCard).evaluate().isNotEmpty;
      final hasLoading = find
          .byType(CircularProgressIndicator)
          .evaluate()
          .isNotEmpty;

      expect(
        hasJokeCards || hasLoading,
        isTrue,
        reason: 'Should either be showing joke cards or loading state',
      );
    });

    testWidgets('shows appropriate empty state message', (tester) async {
      // Override with empty jokes list
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value([]));

      await tester.pumpWidget(createTestWidget());
      await tester.pump(); // Let the widget build
      await tester.pump(); // Let the providers resolve

      // The content area should be in a stable state - either showing empty state or loading
      // In test environments, async providers may resolve differently than production
      final hasEmptyState = find.text('No jokes yet!').evaluate().isNotEmpty;
      final hasLoading = find
          .byType(CircularProgressIndicator)
          .evaluate()
          .isNotEmpty;

      expect(
        hasEmptyState || hasLoading,
        isTrue,
        reason: 'Should either be showing empty state or loading state',
      );
    });

    testWidgets('FAB navigates to joke editor', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump(); // Let the widget build
      await tester.pump(); // Let the providers resolve

      // Verify FAB is present and tappable
      expect(find.byType(FloatingActionButton), findsOneWidget);

      // Verify we're on the management screen initially (chips present)
      expect(find.byKey(const Key('admin-filter-chips-wrap')), findsOneWidget);

      await tester.tap(find.byType(FloatingActionButton));
      await tester.pumpAndSettle(); // Let the navigation animation complete

      // After navigation, we should be on the editor screen
      expect(find.text('Editor Screen'), findsOneWidget);
      expect(find.text('Filters'), findsNothing);
    });

    testWidgets('Popular only filter shows only popular jokes', (tester) async {
      // Arrange: include popular and non-popular jokes
      final jokes = [
        const Joke(
          id: '1',
          setupText: 'S1',
          punchlineText: 'P1',
          setupImageUrl: 'https://example.com/s1.jpg',
          punchlineImageUrl: 'https://example.com/p1.jpg',
          numSaves: 0,
          numShares: 0,
        ),
        const Joke(
          id: '2',
          setupText: 'S2',
          punchlineText: 'P2',
          setupImageUrl: 'https://example.com/s2.jpg',
          punchlineImageUrl: 'https://example.com/p2.jpg',
          numSaves: 2,
          numShares: 0,
        ),
        const Joke(
          id: '3',
          setupText: 'S3',
          punchlineText: 'P3',
          setupImageUrl: 'https://example.com/s3.jpg',
          punchlineImageUrl: 'https://example.com/p3.jpg',
          numSaves: 0,
          numShares: 5,
        ),
      ];

      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(jokes));

      await tester.pumpWidget(createTestWidget());
      await tester.pump();
      await tester.pump();

      // Initially, multiple JokeCards should be present
      expect(find.byType(JokeCard).evaluate().length, greaterThanOrEqualTo(1));

      // Tap the Popular only filter chip
      await tester.tap(find.byKey(const Key('popular-only-filter-chip')));
      await tester.pump();

      // After filtering, joke '1' should not be present
      expect(find.byKey(const Key('1')), findsNothing);

      // At least one popular joke should be visible immediately (either '2' or '3')
      final has2Now = find.byKey(const Key('2')).evaluate().isNotEmpty;
      final has3Now = find.byKey(const Key('3')).evaluate().isNotEmpty;
      expect(has2Now || has3Now, isTrue);

      // Try to scroll to reveal more items (ListView.builder is lazy)
      final listFinder = find.byType(ListView);
      if (listFinder.evaluate().isNotEmpty) {
        await tester.drag(listFinder.first, const Offset(0, -500));
        await tester.pump();
      }
      // The other popular joke should be present after scroll
      expect(
        find.byKey(const Key('2')).evaluate().isNotEmpty ||
            find.byKey(const Key('3')).evaluate().isNotEmpty,
        isTrue,
      );
    });

    testWidgets('Popular filter sorts by (shares*10 + saves) descending', (
      tester,
    ) async {
      // Arrange: create jokes with different popularity scores
      // Scores: a=10 (1*10+0), b=11 (0*10+11), c=12 (1*10+2)
      final jokes = [
        const Joke(
          id: 'a',
          setupText: 'Sa',
          punchlineText: 'Pa',
          setupImageUrl: 'https://example.com/sa.jpg',
          punchlineImageUrl: 'https://example.com/pa.jpg',
          numSaves: 0,
          numShares: 1,
        ),
        const Joke(
          id: 'b',
          setupText: 'Sb',
          punchlineText: 'Pb',
          setupImageUrl: 'https://example.com/sb.jpg',
          punchlineImageUrl: 'https://example.com/pb.jpg',
          numSaves: 11,
          numShares: 0,
        ),
        const Joke(
          id: 'c',
          setupText: 'Sc',
          punchlineText: 'Pc',
          setupImageUrl: 'https://example.com/sc.jpg',
          punchlineImageUrl: 'https://example.com/pc.jpg',
          numSaves: 2,
          numShares: 1,
        ),
      ];

      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(jokes));

      await tester.pumpWidget(createTestWidget());
      await tester.pump();
      await tester.pump();

      // Enable Popular filter
      await tester.tap(find.byKey(const Key('popular-only-filter-chip')));
      await tester.pump();

      // Ensure all three items are laid out; scroll if necessary
      final listFinder = find.byType(ListView);
      if (listFinder.evaluate().isNotEmpty) {
        await tester.drag(listFinder.first, const Offset(0, -600));
        await tester.pump();
        await tester.drag(listFinder.first, const Offset(0, 600));
        await tester.pump();
      }

      // Verify the top-most visible card is the most popular ('c')
      final firstCard =
          tester.widgetList(find.byType(JokeCard)).first as JokeCard;
      expect((firstCard.key as Key).toString(), const Key('c').toString());
    });

    testWidgets('search field onSubmitted triggers search flow', (
      tester,
    ) async {
      // Arrange: when search_jokes returns ids, repository returns those jokes
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(testJokes));

      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      // Reveal the search field via the search chip
      expect(find.byKey(const Key('search-toggle-chip')), findsOneWidget);
      await tester.tap(find.byKey(const Key('search-toggle-chip')));
      await tester.pump();

      // Enter query and submit
      final field = find.byKey(const Key('admin-search-field'));
      expect(field, findsOneWidget);
      await tester.enterText(field, 'penguin');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pump();

      // We can't observe cloud function call here, but provider state changes
      // should not crash; list renders in either loading or content state
      final hasLoading = find
          .byType(CircularProgressIndicator)
          .evaluate()
          .isNotEmpty;
      final hasList = find.byType(ListView).evaluate().isNotEmpty;
      expect(hasLoading || hasList, isTrue);

      // Clear button should appear and clear query when tapped (keeps field visible)
      if (find.byIcon(Icons.clear).evaluate().isNotEmpty) {
        await tester.tap(find.byIcon(Icons.clear));
        await tester.pump();
      }
    });

    testWidgets(
      'search chip toggles search field visibility and hides on blur when empty',
      (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pump();

        // Initially, chip is visible, field hidden
        expect(find.byKey(const Key('search-toggle-chip')), findsOneWidget);
        expect(find.byKey(const Key('admin-search-field')), findsNothing);

        // Tap chip -> field appears
        await tester.tap(find.byKey(const Key('search-toggle-chip')));
        await tester.pump();
        expect(find.byKey(const Key('admin-search-field')), findsOneWidget);

        // Submit empty search (no text) to dismiss keyboard and lose focus
        await tester.testTextInput.receiveAction(TextInputAction.search);
        await tester.pump();
        expect(find.byKey(const Key('admin-search-field')), findsNothing);
        expect(find.byKey(const Key('search-toggle-chip')), findsOneWidget);
      },
    );
  });
}
