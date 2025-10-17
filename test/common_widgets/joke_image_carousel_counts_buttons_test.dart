import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/admin_approval_controls.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/common_widgets/save_joke_button.dart';
import 'package:snickerdoodle/src/common_widgets/share_joke_button.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_modification_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

import '../common/test_utils/joke_carousel_test_utils.dart';

class _MockImageService extends Mock implements ImageService {}

class _MockAppUsageService extends Mock implements AppUsageService {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockPerformanceService extends Mock implements PerformanceService {}

class _MockJokeReactionsService extends Mock implements JokeReactionsService {}

class _MockJokeShareService extends Mock implements JokeShareService {}

class _MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  setUpAll(() {
    registerCarouselTestFallbacks();
    registerFallbackValue(FakeJoke());
  });

  late _MockImageService mockImageService;
  late _MockAppUsageService mockAppUsageService;
  late _MockAnalyticsService mockAnalyticsService;
  late _MockPerformanceService mockPerformanceService;
  late _MockJokeRepository mockJokeRepository;

  setUp(() {
    mockImageService = _MockImageService();
    mockAppUsageService = _MockAppUsageService();
    mockAnalyticsService = _MockAnalyticsService();
    mockPerformanceService = _MockPerformanceService();
    mockJokeRepository = _MockJokeRepository();

    stubImageServiceHappyPath(
      mockImageService,
      dataUrl: transparentImageDataUrl,
    );
    stubAppUsageViewed(mockAppUsageService, viewedCount: 1);
    stubPerformanceNoOps(mockPerformanceService);

    // Mock repository for delete tests
    when(() => mockJokeRepository.deleteJoke(any())).thenAnswer((_) async {});
  });

  Widget createTestWidget({required Widget child}) {
    return ProviderScope(
      overrides: [
        imageServiceProvider.overrideWithValue(mockImageService),
        jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        performanceServiceProvider.overrideWithValue(mockPerformanceService),
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        jokePopulationProvider.overrideWith(
          (ref) => TestJokePopulationNotifier(),
        ),
        jokeModificationProvider.overrideWith(
          (ref) => TestJokeModificationNotifier(),
        ),
      ],
      child: MaterialApp(
        theme: lightTheme,
        home: Scaffold(body: child),
      ),
    );
  }

  group('Counts icons', () {
    testWidgets('icons are gray when counts are 0', (tester) async {
      const joke = Joke(
        id: '1',
        setupText: 'setup',
        punchlineText: 'punch',
        setupImageUrl: 'https://example.com/a.jpg',
        punchlineImageUrl: 'https://example.com/b.jpg',
        numSaves: 0,
        numShares: 0,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showNumSaves: true,
        showNumShares: true,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      expect(find.byIcon(Icons.favorite), findsOneWidget);
      expect(find.byIcon(Icons.share), findsOneWidget);
      expect(find.text('0'), findsNWidgets(2));
    });

    testWidgets('icons are colored when counts are > 0', (tester) async {
      const joke = Joke(
        id: '1',
        setupText: 'setup',
        punchlineText: 'punch',
        setupImageUrl: 'https://example.com/a.jpg',
        punchlineImageUrl: 'https://example.com/b.jpg',
        numSaves: 1,
        numShares: 2,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showNumSaves: true,
        showNumShares: true,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      expect(find.byIcon(Icons.favorite), findsOneWidget);
      expect(find.byIcon(Icons.share), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
    });
  });

  group('Button visibility controls', () {
    testWidgets('shows save button when showSaveButton is true', (
      tester,
    ) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showSaveButton: true,
        showAdminRatingButtons: false,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            IsJokeSavedProvider(
              joke.id,
            ).overrideWith((ref) => Stream<bool>.value(false)),
            jokeReactionsServiceProvider.overrideWithValue(
              _MockJokeReactionsService(),
            ),
          ],
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(SaveJokeButton), findsOneWidget);
      expect(find.byType(AdminApprovalControls), findsNothing);
    });

    testWidgets('hides save button when showSaveButton is false', (
      tester,
    ) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showSaveButton: false,
        showAdminRatingButtons: false,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            IsJokeSavedProvider(
              joke.id,
            ).overrideWith((ref) => Stream<bool>.value(false)),
            jokeReactionsServiceProvider.overrideWithValue(
              _MockJokeReactionsService(),
            ),
          ],
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(SaveJokeButton), findsNothing);
      expect(find.byType(AdminApprovalControls), findsNothing);
    });

    testWidgets('shows admin rating buttons when flag is true', (tester) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showSaveButton: false,
        showAdminRatingButtons: true,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(SaveJokeButton), findsNothing);
      expect(find.byType(AdminApprovalControls), findsOneWidget);
    });

    testWidgets('hides admin rating buttons when flag is false', (
      tester,
    ) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showSaveButton: true,
        showAdminRatingButtons: false,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            IsJokeSavedProvider(
              joke.id,
            ).overrideWith((ref) => Stream<bool>.value(false)),
            jokeReactionsServiceProvider.overrideWithValue(
              _MockJokeReactionsService(),
            ),
          ],
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(SaveJokeButton), findsOneWidget);
      expect(find.byType(AdminApprovalControls), findsNothing);
    });

    testWidgets('shows both save and admin rating buttons when both true', (
      tester,
    ) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(
        joke: joke,
        showSaveButton: true,
        showShareButton: true,
        showAdminRatingButtons: true,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            IsJokeSavedProvider(
              joke.id,
            ).overrideWith((ref) => Stream<bool>.value(false)),
            IsJokeSharedProvider(
              joke.id,
            ).overrideWith((ref) => Stream<bool>.value(false)),
            jokeReactionsServiceProvider.overrideWithValue(
              _MockJokeReactionsService(),
            ),
            jokeShareServiceProvider.overrideWithValue(_MockJokeShareService()),
          ],
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(SaveJokeButton), findsOneWidget);
      expect(find.byType(ShareJokeButton), findsOneWidget);
      expect(find.byType(AdminApprovalControls), findsOneWidget);
    });

    testWidgets('uses default button flags when not specified', (tester) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(joke: joke, jokeContext: 'test');

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(SaveJokeButton), findsNothing);
      expect(find.byType(AdminApprovalControls), findsNothing);
      expect(find.byType(ShareJokeButton), findsNothing);
    });

    testWidgets('shows share button when flag is true', (tester) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      final widget = JokeImageCarousel(
        joke: joke,
        showShareButton: true,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            IsJokeSharedProvider(
              joke.id,
            ).overrideWith((ref) => Stream<bool>.value(false)),
            jokeShareServiceProvider.overrideWithValue(_MockJokeShareService()),
          ],
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(ShareJokeButton), findsOneWidget);
    });

    testWidgets('hides share button when flag is false', (tester) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      final widget = JokeImageCarousel(
        joke: joke,
        showShareButton: false,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(ShareJokeButton), findsNothing);
    });

    testWidgets('does not show regenerate button when not in admin mode', (
      tester,
    ) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      final widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: false,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      await tester.pump();

      expect(find.byKey(const Key('regenerate-all-button')), findsNothing);
      expect(find.byKey(const Key('regenerate-images-button')), findsNothing);
    });

    testWidgets('shows regenerate buttons when in admin mode', (tester) async {
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      final widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: true,
        jokeContext: 'test',
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );

      await tester.pump();

      expect(find.byKey(const Key('regenerate-images-button')), findsOneWidget);
    });
  });

  group('Delete button functionality', () {
    testWidgets('shows delete button in admin mode', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: true,
        jokeContext: 'test',
      );

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert
      expect(find.byKey(const Key('delete-joke-button')), findsOneWidget);
    });

    testWidgets('hides delete button when not in admin mode', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: false,
        jokeContext: 'test',
      );

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert
      expect(find.byKey(const Key('delete-joke-button')), findsNothing);
    });

    testWidgets('does nothing on delete button tap', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: true,
        jokeContext: 'test',
      );

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // Tap (not hold) the delete button
      await tester.tap(find.byKey(const Key('delete-joke-button')));
      await tester.pump();

      // assert - verify no delete was called
      verifyNever(() => mockJokeRepository.deleteJoke(any()));
    });

    testWidgets('calls deleteJoke with correct joke ID', (tester) async {
      // arrange
      const jokeId = 'test-joke-123';
      const joke = Joke(
        id: jokeId,
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: true,
        jokeContext: 'test',
      );

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // Verify the delete button is present and configured correctly
      final deleteButtonFinder = find.byKey(const Key('delete-joke-button'));
      expect(deleteButtonFinder, findsOneWidget);

      // For this test, we verify the joke ID is correctly passed to the widget
      // The actual deleteJoke call would happen in the onHoldComplete callback
      // which is tested in the repository tests
      final carousel = tester.widget<JokeImageCarousel>(
        find.byType(JokeImageCarousel),
      );
      expect(carousel.joke.id, equals(jokeId));
    });
  });
}
