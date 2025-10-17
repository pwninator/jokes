import 'package:flutter/material.dart';
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
    registerFallbackValue(FakeJoke());
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

  group('Long press functionality', () {
    testWidgets(
      'does not show metadata dialog on long press in non-admin mode',
      (tester) async {
        // arrange
        final joke = Joke(
          id: 'test-joke-1',
          setupText: 'Setup text',
          punchlineText: 'Punchline text',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          generationMetadata: {'model': 'gpt-4', 'timestamp': '2024-01-01'},
        );

        final widget = JokeImageCarousel(
          joke: joke,
          isAdminMode: false,
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

        // Long press on the image
        await tester.longPress(find.byType(JokeImageCarousel));
        await tester.pump();

        // assert
        expect(find.byType(AlertDialog), findsNothing);
        expect(find.text('Generation Metadata'), findsNothing);
      },
    );

    testWidgets(
      'shows metadata dialog on long press in admin mode with metadata',
      (tester) async {
        // arrange
        final joke = Joke(
          id: 'test-joke-1',
          setupText: 'Setup text',
          punchlineText: 'Punchline text',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          generationMetadata: const {
            'generations': [
              {
                'label': 'Agent_CreativeBriefAgent',
                'model_name': 'gemini-2.5-flash',
                'cost': 0.001329,
                'generation_time_sec': 0,
                'retry_count': 0,
                'token_counts': {
                  'thought_tokens': 440,
                  'output_tokens': 34,
                  'input_tokens': 480,
                },
              },
              {
                'label': 'pun_agent_image_tool',
                'model_name': 'gpt-4.1-mini',
                'cost': 0.0014656000000000003,
                'generation_time_sec': 29.48288367400528,
                'retry_count': 0,
                'token_counts': {'output_tokens': 231, 'input_tokens': 2740},
              },
            ],
          },
        );

        final widget = JokeImageCarousel(
          joke: joke,
          isAdminMode: true,
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

        // Long press on the image carousel
        await tester.longPress(find.byType(JokeImageCarousel));
        await tester.pump(); // Allow dialog to show
        await tester.pump(
          const Duration(milliseconds: 100),
        ); // Allow dialog animation

        // assert
        expect(find.byType(AlertDialog), findsOneWidget);
        expect(find.text('Joke Details'), findsOneWidget);
        expect(find.text('Close'), findsOneWidget);
        // Check that some metadata content is displayed (not empty message)
        expect(
          find.text('No generation metadata available for this joke.'),
          findsNothing,
        );
        // Verify that there's a container with monospace text (formatted metadata)
        expect(find.byType(Container), findsAtLeastNWidgets(1));
      },
    );

    testWidgets(
      'shows no metadata message when metadata is null in admin mode',
      (tester) async {
        // arrange
        final joke = Joke(
          id: 'test-joke-1',
          setupText: 'Setup text',
          punchlineText: 'Punchline text',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          generationMetadata: null,
        );

        final widget = JokeImageCarousel(
          joke: joke,
          isAdminMode: true,
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

        // Long press on the image carousel
        await tester.longPress(find.byType(JokeImageCarousel));
        await tester.pump(); // Allow dialog to show
        await tester.pump(
          const Duration(milliseconds: 100),
        ); // Allow dialog animation

        // assert
        expect(find.byType(AlertDialog), findsOneWidget);
        expect(find.text('Joke Details'), findsOneWidget);
        expect(
          find.text('No generation metadata available for this joke.'),
          findsOneWidget,
        );
      },
    );

    testWidgets('shows fallback format for unexpected metadata structure', (
      tester,
    ) async {
      // arrange
      final joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
        generationMetadata: {
          'model': 'gpt-4',
          'timestamp': '2024-01-01T00:00:00Z',
          'parameters': {'temperature': 0.7},
        },
      );

      final widget = JokeImageCarousel(
        joke: joke,
        isAdminMode: true,
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

      // Long press on the image carousel
      await tester.longPress(find.byType(JokeImageCarousel));
      await tester.pump(); // Allow dialog to show
      await tester.pump(
        const Duration(milliseconds: 100),
      ); // Allow dialog animation

      // assert
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.text('Joke Details'), findsOneWidget);
      expect(find.text('Close'), findsOneWidget);
      // Check that some metadata content is displayed (not empty message)
      expect(
        find.text('No generation metadata available for this joke.'),
        findsNothing,
      );
      // Verify that there's a container with monospace text (formatted metadata)
      expect(find.byType(Container), findsAtLeastNWidgets(1));
    });
  });
}
