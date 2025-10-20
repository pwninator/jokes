import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
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

void main() {
  setUpAll(() {
    registerFallbackValue(FakeJoke());
    registerCarouselTestFallbacks();
  });

  late _MockImageService mockImageService;
  late _MockAppUsageService mockAppUsageService;
  late _MockAnalyticsService mockAnalyticsService;
  late _MockPerformanceService mockPerformanceService;

  const String dataUrl = transparentImageDataUrl;

  setUp(() {
    mockImageService = _MockImageService();
    mockAppUsageService = _MockAppUsageService();
    mockAnalyticsService = _MockAnalyticsService();
    mockPerformanceService = _MockPerformanceService();

    // Shared stubs
    stubImageServiceHappyPath(mockImageService, dataUrl: dataUrl);
    stubAppUsageViewed(mockAppUsageService, viewedCount: 1);
    stubPerformanceNoOps(mockPerformanceService);

    // Analytics no-ops so we can verify calls without side effects
    when(
      () => mockAnalyticsService.logJokeSetupViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mockAnalyticsService.logJokePunchlineViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mockAnalyticsService.logJokeViewed(
        any(),
        totalJokesViewed: any(named: 'totalJokesViewed'),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mockAnalyticsService.logJokeSearchSimilar(
        queryLength: any(named: 'queryLength'),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});
  });

  Widget wrap(Widget child) => wrapWithCarouselOverrides(
    child,
    imageService: mockImageService,
    appUsageService: mockAppUsageService,
    analyticsService: mockAnalyticsService,
    performanceService: mockPerformanceService,
  );

  const joke = Joke(
    id: 'j1',
    setupText: 's',
    punchlineText: 'p',
    setupImageUrl: 'https://example.com/a.jpg',
    punchlineImageUrl: 'https://example.com/b.jpg',
  );

  testWidgets('admin mode suppresses setup/punchline/view analytics and usage tracking', (
    tester,
  ) async {
    final w = JokeImageCarousel(
      joke: joke,
      isAdminMode: true,
      jokeContext: 'admin',
    );

    await tester.pumpWidget(wrap(w));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 2100));

    await tester.tap(find.byType(JokeImageCarousel));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 2100));

    verifyNever(
      () => mockAnalyticsService.logJokeSetupViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    );
    verifyNever(
      () => mockAnalyticsService.logJokePunchlineViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    );
    verifyNever(
      () => mockAnalyticsService.logJokeViewed(
        any(),
        totalJokesViewed: any(named: 'totalJokesViewed'),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    );
    verifyNever(
      () => mockAppUsageService.logJokeViewed(
        any(),
        context: any(named: 'context'),
      ),
    );
  });

  testWidgets('non-admin mode emits setup/punchline/view analytics', (
    tester,
  ) async {
    final w = JokeImageCarousel(
      joke: joke,
      isAdminMode: false,
      jokeContext: 'feed',
    );

    await tester.pumpWidget(wrap(w));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 2100));
    await tester.tap(find.byType(JokeImageCarousel));
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump(const Duration(milliseconds: 2100));

    verify(
      () => mockAnalyticsService.logJokeSetupViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).called(greaterThan(0));
  });

  testWidgets('non-REVEAL auto-logs punchline and fully viewed after setup', (
    tester,
  ) async {
    Future<void> runForMode(JokeViewerMode mode) async {
      final widget = SizedBox(
        width: 800,
        height: 600,
        child: JokeImageCarousel(
          joke: joke,
          isAdminMode: false,
          jokeContext: 'feed',
          mode: mode,
        ),
      );
      await tester.pumpWidget(wrap(widget));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 2100));
      await tester.pump(const Duration(milliseconds: 2100));
    }

    await runForMode(JokeViewerMode.bothAdaptive);

    verify(
      () => mockAnalyticsService.logJokePunchlineViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).called(greaterThan(0));
  });

  testWidgets('admin mode hides similar search button', (tester) async {
    final w = JokeImageCarousel(
      joke: joke,
      isAdminMode: true,
      showSimilarSearchButton: true,
      jokeContext: 'admin',
    );

    await tester.pumpWidget(wrap(w));
    await tester.pump();

    // Similar search button should not be shown in admin mode
    final similarButton = find.byKey(const Key('similar-search-button'));
    expect(similarButton, findsNothing);
  });

  // Note: Testing similar search analytics in non-admin mode requires complex
  // Firebase mocks for navigation. This is covered in the dedicated similar
  // search test file: joke_list_viewer_similar_button_test.dart
}
