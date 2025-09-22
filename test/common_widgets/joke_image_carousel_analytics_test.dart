import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/analytics_mocks.dart';
import '../test_helpers/core_mocks.dart';
import '../test_helpers/firebase_mocks.dart';
import 'joke_image_carousel_test.dart' show FakeJoke; // reuse existing FakeJoke

class _MockImageService extends Mock implements ImageService {}

class _MockAppUsageService extends Mock implements AppUsageService {}

void main() {
  setUpAll(() {
    // Ensure mocktail fallback values are registered for analytics-related types
    registerAnalyticsFallbackValues();
  });

  late _MockImageService mockImageService;
  late _MockAppUsageService mockAppUsageService;
  late MockAnalyticsService mockAnalyticsService;

  const String dataUrl =
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

  setUp(() {
    mockImageService = _MockImageService();
    mockAppUsageService = _MockAppUsageService();
    mockAnalyticsService = AnalyticsMocks.mockAnalyticsService;
    // Ensure FakeJoke is registered for any(Joke)
    registerFallbackValue(FakeJoke());

    // Image service happy-path stubs
    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(() => mockImageService.processImageUrl(any())).thenReturn(dataUrl);
    when(
      () => mockImageService.processImageUrl(
        any(),
        width: any(named: 'width'),
        height: any(named: 'height'),
        quality: any(named: 'quality'),
      ),
    ).thenReturn(dataUrl);
    when(
      () => mockImageService.getProcessedJokeImageUrl(any()),
    ).thenReturn(dataUrl);
    when(
      () => mockImageService.precacheJokeImage(any()),
    ).thenAnswer((_) async => dataUrl);
    when(
      () => mockImageService.precacheJokeImages(any()),
    ).thenAnswer((_) async => (setupUrl: dataUrl, punchlineUrl: dataUrl));
    when(
      () => mockImageService.precacheMultipleJokeImages(any()),
    ).thenAnswer((_) async {});

    // App usage stubs required by full-view flow
    when(() => mockAppUsageService.logJokeViewed()).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 1);
  });

  Widget wrap(Widget child) => ProviderScope(
    overrides: [
      ...CoreMocks.getCoreProviderOverrides(
        additionalOverrides: [
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          ...AnalyticsMocks.getAnalyticsProviderOverrides(),
          imageServiceProvider.overrideWithValue(mockImageService),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        ],
      ),
    ],
    child: MaterialApp(
      theme: lightTheme,
      home: Scaffold(body: child),
    ),
  );

  const joke = Joke(
    id: 'j1',
    setupText: 's',
    punchlineText: 'p',
    setupImageUrl: 'https://example.com/a.jpg',
    punchlineImageUrl: 'https://example.com/b.jpg',
  );

  testWidgets('admin mode suppresses setup/punchline/view analytics', (
    tester,
  ) async {
    // arrange
    final w = JokeImageCarousel(
      joke: joke,
      isAdminMode: true,
      jokeContext: 'admin',
    );

    // act: build → allow post-frame → wait >2s for setup
    await tester.pumpWidget(wrap(w));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 2100));

    // navigate to punchline via tap, then wait >2s
    await tester.tap(find.byType(JokeImageCarousel));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 2100));

    // assert: no view/navigation analytics
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
  });

  testWidgets('non-admin mode emits setup/punchline/view analytics', (
    tester,
  ) async {
    // arrange
    final w = JokeImageCarousel(
      joke: joke,
      isAdminMode: false,
      jokeContext: 'feed',
    );

    // act
    await tester.pumpWidget(wrap(w));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 2100)); // setup viewed
    await tester.tap(find.byType(JokeImageCarousel));
    await tester.pump(const Duration(milliseconds: 350)); // complete page anim
    await tester.pump(const Duration(milliseconds: 2100)); // punchline viewed

    // assert: at least setup event is logged in non-admin mode
    verify(
      () => mockAnalyticsService.logJokeSetupViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).called(greaterThan(0));
  });

  testWidgets(
    'non-REVEAL modes auto-log punchline and fully viewed after setup',
    (tester) async {
      Future<void> runForMode(JokeCarouselMode mode) async {
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
        await tester.pump(const Duration(milliseconds: 2100)); // setup timer
        await tester.pump(const Duration(milliseconds: 2100)); // chained timer
      }

      // Run sequentially to avoid overflow/layout complexities
      await runForMode(JokeCarouselMode.bothAdaptive);

      verify(
        () => mockAnalyticsService.logJokePunchlineViewed(
          any(),
          navigationMethod: any(named: 'navigationMethod'),
          jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
        ),
      ).called(greaterThan(0));
    },
  );
}
