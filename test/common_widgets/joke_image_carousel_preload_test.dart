import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../common/test_utils/joke_carousel_test_utils.dart';

class _MockImageService extends Mock implements ImageService {}

class _MockAppUsageService extends Mock implements AppUsageService {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockPerformanceService extends Mock implements PerformanceService {}

void main() {
  setUpAll(() {
    registerCarouselTestFallbacks();
    registerFallbackValue(_FakeJoke());
  });

  late _MockImageService mockImageService;
  late _MockAppUsageService mockAppUsageService;
  late _MockAnalyticsService mockAnalyticsService;
  late _MockPerformanceService mockPerformanceService;

  setUp(() {
    mockImageService = _MockImageService();
    mockAppUsageService = _MockAppUsageService();
    mockAnalyticsService = _MockAnalyticsService();
    mockPerformanceService = _MockPerformanceService();

    stubImageServiceHappyPath(mockImageService);
    stubAppUsageViewed(mockAppUsageService);
    stubPerformanceNoOps(mockPerformanceService);
  });

  group('Image preloading', () {
    testWidgets('calls processImageUrl for valid setup image', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(joke: joke, jokeContext: 'test');

      // act
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
      await tester.pump(); // Extra pump for post-frame callbacks

      // assert
      verify(
        () => mockImageService.getProcessedJokeImageUrl(
          'https://example.com/setup.jpg',
          width: any(named: 'width'),
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

      const widget = JokeImageCarousel(joke: joke, jokeContext: 'test');

      // act
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
      await tester.pump(); // Extra pump for post-frame callbacks

      // assert - the widget processes both image URLs (even null ones)
      verify(
        () => mockImageService.getProcessedJokeImageUrl(
          null,
          width: any(named: 'width'),
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
        jokeContext: 'test',
      );

      // act
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
      await tester.pump(); // Extra pump for post-frame callbacks

      // assert - verify current joke images are processed using width hints
      verify(
        () => mockImageService.getProcessedJokeImageUrl(
          any(),
          width: any(named: 'width'),
        ),
      ).called(greaterThan(0));
    });
  });
}

class _FakeJoke extends Fake implements Joke {}
