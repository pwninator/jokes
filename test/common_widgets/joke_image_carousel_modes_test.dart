import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:smooth_page_indicator/smooth_page_indicator.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

import '../common/test_utils/joke_carousel_test_utils.dart';

class _MockImageService extends Mock implements ImageService {}

class _MockAppUsageService extends Mock implements AppUsageService {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockPerformanceService extends Mock implements PerformanceService {}

class _FakeJoke extends Fake implements Joke {}

void main() {
  setUpAll(() {
    registerFallbackValue(_FakeJoke());
    registerCarouselTestFallbacks();
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

    stubImageServiceHappyPath(
      mockImageService,
      dataUrl: transparentImageDataUrl,
    );
    stubAppUsageViewed(mockAppUsageService, viewedCount: 1);
    stubPerformanceNoOps(mockPerformanceService);
  });

  testWidgets('REVEAL mode shows page indicators and uses PageView', (
    tester,
  ) async {
    // arrange
    const joke = Joke(
      id: 'reveal-joke',
      setupText: 'Setup',
      punchlineText: 'Punch',
      setupImageUrl: 'https://example.com/a.jpg',
      punchlineImageUrl: 'https://example.com/b.jpg',
    );

    const widget = JokeImageCarousel(
      joke: joke,
      jokeContext: 'test',
      mode: JokeViewerMode.reveal,
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

    // assert
    expect(find.byType(SmoothPageIndicator), findsOneWidget);
    expect(find.byType(PageView), findsOneWidget);
  });
  group('Adaptive layout', () {
    testWidgets('BOTH_ADAPTIVE is horizontal in wide constraints', (
      tester,
    ) async {
      final widget = SizedBox(
        width: 800,
        height: 400,
        child: const JokeImageCarousel(
          joke: Joke(
            id: '1',
            setupText: 's',
            punchlineText: 'p',
            setupImageUrl: 'a',
            punchlineImageUrl: 'b',
          ),
          jokeContext: 'test',
          mode: JokeViewerMode.bothAdaptive,
        ),
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
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(Row), findsWidgets);
    });

    testWidgets('BOTH_ADAPTIVE is vertical in tall constraints', (
      tester,
    ) async {
      final widget = SizedBox(
        width: 400,
        height: 800,
        child: const JokeImageCarousel(
          joke: Joke(
            id: '2',
            setupText: 's',
            punchlineText: 'p',
            setupImageUrl: 'a',
            punchlineImageUrl: 'b',
          ),
          jokeContext: 'test',
          mode: JokeViewerMode.bothAdaptive,
        ),
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
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(Column), findsWidgets);
    });
  });
}
