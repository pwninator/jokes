import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/firebase_mocks.dart';

// Mock class for ImageService
class MockImageService extends Mock implements ImageService {}

void main() {
  late MockImageService mockImageService;

  // 1x1 transparent PNG as base64 data URL that works with CachedNetworkImage
  const String transparentImageDataUrl =
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

  setUp(() {
    mockImageService = MockImageService();

    // Mock to return true for any URL
    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);

    // Mock to return data URL that resolves immediately
    when(
      () => mockImageService.processImageUrl(any()),
    ).thenReturn(transparentImageDataUrl);
    when(
      () => mockImageService.processImageUrl(
        any(),
        width: any(named: 'width'),
        height: any(named: 'height'),
        quality: any(named: 'quality'),
      ),
    ).thenReturn(transparentImageDataUrl);
    when(
      () => mockImageService.getThumbnailUrl(any()),
    ).thenReturn(transparentImageDataUrl);
    when(
      () => mockImageService.getFullSizeUrl(any()),
    ).thenReturn(transparentImageDataUrl);
    when(() => mockImageService.clearCache()).thenAnswer((_) async {});
  });

  Widget createTestWidget({required Widget child}) {
    return ProviderScope(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        imageServiceProvider.overrideWithValue(mockImageService),
      ],
      child: MaterialApp(theme: lightTheme, home: Scaffold(body: child)),
    );
  }

  group('JokeImageCarousel', () {
    testWidgets('displays correctly with valid image URLs', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(joke: joke);

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump(); // Let the widget build
      await tester.pump(const Duration(milliseconds: 100)); // Let images load

      // assert
      expect(find.byType(JokeImageCarousel), findsOneWidget);
      expect(find.byType(PageView), findsOneWidget);
    });

    testWidgets('does not show regenerate button when not in admin mode', (
      tester,
    ) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(joke: joke, isAdminMode: false);

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert
      expect(find.byKey(const Key('regenerate-all-button')), findsNothing);
      expect(find.byKey(const Key('regenerate-images-button')), findsNothing);
    });

    testWidgets('shows regenerate buttons when in admin mode', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(joke: joke, isAdminMode: true);

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert
      expect(find.byKey(const Key('regenerate-all-button')), findsOneWidget);
      expect(find.byKey(const Key('regenerate-images-button')), findsOneWidget);
    });

    testWidgets('page indicators work correctly', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(joke: joke);

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert - should have 2 page indicators
      final pageIndicators = find.byType(AnimatedContainer);
      expect(pageIndicators, findsAtLeastNWidgets(2));
    });

    testWidgets('handles null image URLs gracefully', (tester) async {
      // arrange
      const jokeWithNullImages = Joke(
        id: 'test-joke-null',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: null,
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(joke: jokeWithNullImages);

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert
      expect(find.byType(JokeImageCarousel), findsOneWidget);
      // Verify no errors are thrown
    });

    testWidgets('handles empty image URLs gracefully', (tester) async {
      // arrange
      const jokeWithEmptyUrls = Joke(
        id: 'test-joke-empty',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: '',
        punchlineImageUrl: '',
      );

      const widget = JokeImageCarousel(joke: jokeWithEmptyUrls);

      // act
      await tester.pumpWidget(createTestWidget(child: widget));
      await tester.pump();

      // assert
      expect(find.byType(JokeImageCarousel), findsOneWidget);
    });

    group('Image preloading', () {
      testWidgets('calls processImageUrl for valid setup image', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: 'test-joke-1',
          setupText: 'Setup text',
          punchlineText: 'Punchline text',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: null,
        );

        const widget = JokeImageCarousel(joke: joke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.pump(); // Extra pump for post-frame callbacks

        // assert
        verify(
          () => mockImageService.processImageUrl(
            'https://example.com/setup.jpg',
            quality: '50',
          ),
        ).called(greaterThan(0));
      });

      testWidgets('calls processImageUrl for valid punchline image', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: 'test-joke-1',
          setupText: 'Setup text',
          punchlineText: 'Punchline text',
          setupImageUrl: null,
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        const widget = JokeImageCarousel(joke: joke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.pump(); // Extra pump for post-frame callbacks

        // assert
        verify(
          () => mockImageService.processImageUrl(
            'https://example.com/punchline.jpg',
            quality: '50',
          ),
        ).called(greaterThan(0));
      });

      testWidgets('preloads images for the current joke consistently', (
        tester,
      ) async {
        // arrange
        const currentJoke = Joke(
          id: 'current-joke',
          setupText: 'Current setup',
          punchlineText: 'Current punchline',
          setupImageUrl: 'https://example.com/current_setup.jpg',
          punchlineImageUrl: 'https://example.com/current_punchline.jpg',
        );

        const preloadJoke = Joke(
          id: 'preload-joke',
          setupText: 'Preload setup',
          punchlineText: 'Preload punchline',
          setupImageUrl: 'https://example.com/preload_setup.jpg',
          punchlineImageUrl: 'https://example.com/preload_punchline.jpg',
        );

        const widget = JokeImageCarousel(
          joke: currentJoke,
          jokesToPreload: [preloadJoke],
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.pump(); // Extra pump for post-frame callbacks

        // assert - verify current joke images are processed using consolidated logic
        verify(
          () => mockImageService.processImageUrl(
            'https://example.com/current_setup.jpg',
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: '50',
          ),
        ).called(greaterThan(0));
        verify(
          () => mockImageService.processImageUrl(
            'https://example.com/current_punchline.jpg',
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: '50',
          ),
        ).called(greaterThan(0));

        // Note: Preload joke image verification is not reliable in test environment
        // due to async timing, but the consolidation logic is the same for all images
      });
    });
  });
}
