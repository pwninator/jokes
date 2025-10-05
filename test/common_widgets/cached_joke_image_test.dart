import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

import '../test_helpers/firebase_mocks.dart';

class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  late MockImageService mockImageService;
  late MockAnalyticsService mockAnalyticsService;

  setUpAll(() {
    registerFallbackValue(BoxConstraints());
  });

  setUp(() {
    mockImageService = MockImageService();
    mockAnalyticsService = MockAnalyticsService();

    // Default mock behaviors
    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(() => mockImageService.getProcessedJokeImageUrl(any(),
        width: any(named: 'width'))).thenReturn('https://example.com/processed.jpg');
    when(() => mockAnalyticsService.logErrorImageLoad(
          jokeId: any(named: 'jokeId'),
          imageType: any(named: 'imageType'),
          imageUrlHash: any(named: 'imageUrlHash'),
          errorMessage: any(named: 'errorMessage'),
        )).thenAnswer((_) async {});
  });

  Widget createTestWidget({
    required Widget child,
    List<Override> additionalOverrides = const [],
  }) {
    return ProviderScope(
      overrides: [
        imageServiceProvider.overrideWithValue(mockImageService),
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        ...FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: additionalOverrides,
        ),
      ],
      child: MaterialApp(
        theme: lightTheme,
        home: Scaffold(body: child),
      ),
    );
  }

  group('CachedJokeImage', () {
    const validUrl = 'https://example.com/image.jpg';

    testWidgets('renders correctly with valid URL, custom dimensions, and border radius', (tester) async {
      const width = 200.0;
      const height = 150.0;
      final borderRadius = BorderRadius.circular(12);

      await tester.pumpWidget(createTestWidget(
        child: CachedJokeImage(
          imageUrl: validUrl,
          width: width,
          height: height,
          borderRadius: borderRadius,
        ),
      ));
      await tester.pump();

      expect(find.byType(CachedJokeImage), findsOneWidget);
      expect(find.byType(ClipRRect), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('handles null and invalid URLs gracefully', (tester) async {
      when(() => mockImageService.isValidImageUrl(any())).thenReturn(false);
      when(() => mockImageService.getProcessedJokeImageUrl(any(), width: any(named: 'width')))
          .thenReturn(null);

      await tester.pumpWidget(createTestWidget(
        child: const CachedJokeImage(imageUrl: null, showErrorIcon: true),
      ));
      await tester.pump();

      // Should show a container with the correct error icon
      expect(find.byType(Container), findsOneWidget);
      expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);

      // Now test with showErrorIcon: false
      await tester.pumpWidget(createTestWidget(
        child: const CachedJokeImage(imageUrl: 'invalid-url', showErrorIcon: false),
      ));
      await tester.pump();

      // Should show a container but no error icon
      expect(find.byType(Container), findsOneWidget);
      expect(find.byIcon(Icons.image_not_supported_outlined), findsNothing);
    });

    group('CDN Width Calculation', () {
      testWidgets('rounds explicit width up to nearest hundred', (tester) async {
        await tester.pumpWidget(createTestWidget(
          child: const CachedJokeImage(imageUrl: validUrl, width: 175),
        ));
        await tester.pump();

        final captured = verify(() => mockImageService.getProcessedJokeImageUrl(validUrl,
            width: captureAny(named: 'width'))).captured;
        expect(captured.single, 200);
      });

      testWidgets('rounds layout constraint width up to nearest hundred', (tester) async {
        await tester.pumpWidget(createTestWidget(
          child: const Align(
            alignment: Alignment.topLeft,
            child: SizedBox(
              width: 245,
              child: CachedJokeImage(imageUrl: validUrl),
            ),
          ),
        ));
        await tester.pump();

        final captured = verify(() => mockImageService.getProcessedJokeImageUrl(validUrl,
            width: captureAny(named: 'width'))).captured;
        expect(captured.single, 300);
      });

      testWidgets('clamps width to max when constraints are too large', (tester) async {
        await tester.pumpWidget(createTestWidget(
          child: Align(
            alignment: Alignment.topLeft,
            child: OverflowBox(
              minWidth: 1600,
              maxWidth: 1600,
              child: CachedJokeImage(imageUrl: validUrl),
            ),
          ),
        ));
        await tester.pump();

        final captured = verify(() => mockImageService.getProcessedJokeImageUrl(validUrl,
            width: captureAny(named: 'width'))).captured;
        expect(captured.single, 1024);
      });

      testWidgets('passes no width when constraints are unbounded', (tester) async {
        await tester.pumpWidget(createTestWidget(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: CachedJokeImage(imageUrl: validUrl, height: 100),
          ),
        ));
        await tester.pump();

        verify(() => mockImageService.getProcessedJokeImageUrl(validUrl, width: null)).called(1);
      });
    });
  });

  group('CachedJokeThumbnail', () {
    testWidgets('renders correctly for valid URL and handles null URL', (tester) async {
      const validUrl = 'https://example.com/image.jpg';
      const thumbnailUrl = 'https://example.com/thumbnail.jpg';
      const customSize = 80.0;

      // --- Success case ---
      when(() => mockImageService.getThumbnailUrl(validUrl)).thenReturn(thumbnailUrl);

      await tester.pumpWidget(createTestWidget(
        child: const CachedJokeThumbnail(imageUrl: validUrl, size: customSize),
      ));
      await tester.pump();

      expect(find.byType(CachedJokeThumbnail), findsOneWidget);
      final cachedImage = tester.widget<CachedJokeImage>(find.byType(CachedJokeImage));
      expect(cachedImage.width, customSize);
      expect(cachedImage.height, customSize);
      verify(() => mockImageService.getThumbnailUrl(validUrl)).called(1);

      // --- Null URL case ---
      clearInteractions(mockImageService);
      when(() => mockImageService.isValidImageUrl(null)).thenReturn(false);
      when(() => mockImageService.getProcessedJokeImageUrl(null, width: any(named: 'width')))
          .thenReturn(null);

      await tester.pumpWidget(createTestWidget(
        child: const CachedJokeThumbnail(imageUrl: null),
      ));
      await tester.pump();

      expect(find.byType(Container), findsOneWidget);
      // The underlying CachedJokeImage should show an error icon by default
      expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
      verifyNever(() => mockImageService.getThumbnailUrl(any()));
    });
  });
}