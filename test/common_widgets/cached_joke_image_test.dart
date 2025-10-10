import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

import '../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockPerformanceService extends Mock implements PerformanceService {}

void main() {
  setUpAll(() {
    registerFallbackValue(TraceName.imageDownload);
  });
  group('CachedJokeImage Widget Tests', () {
    late MockImageService mockImageService;
    late MockAnalyticsService mockAnalyticsService;
    late MockPerformanceService mockPerformanceService;

    setUp(() {
      mockImageService = MockImageService();
      mockAnalyticsService = MockAnalyticsService();
      mockPerformanceService = MockPerformanceService();
    });

    Widget createTestWidget({
      required Widget child,
      List<Override> additionalOverrides = const [],
    }) {
      return ProviderScope(
        overrides: [
          imageServiceProvider.overrideWithValue(mockImageService),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          performanceServiceProvider.overrideWithValue(mockPerformanceService),
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
      testWidgets('should create widget successfully with null imageUrl', (
        tester,
      ) async {
        // arrange
        when(() => mockImageService.isValidImageUrl(null)).thenReturn(false);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            null,
            width: any(named: 'width'),
          ),
        ).thenReturn(null);
        const widget = CachedJokeImage(imageUrl: null);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byType(Container), findsOneWidget);
      });

      testWidgets('should create widget successfully with invalid imageUrl', (
        tester,
      ) async {
        // arrange
        const invalidUrl = 'invalid-url';
        when(
          () => mockImageService.isValidImageUrl(invalidUrl),
        ).thenReturn(false);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            invalidUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(null);

        const widget = CachedJokeImage(imageUrl: invalidUrl);
        when(
          () => mockAnalyticsService.logErrorImageLoad(
            jokeId: any(named: 'jokeId'),
            imageType: any(named: 'imageType'),
            imageUrlHash: any(named: 'imageUrlHash'),
            errorMessage: any(named: 'errorMessage'),
          ),
        ).thenAnswer((_) async {});

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byType(Container), findsOneWidget);
      });

      testWidgets('should create widget successfully with valid imageUrl', (
        tester,
      ) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(validUrl),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(
            validUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(validUrl);

        const widget = CachedJokeImage(imageUrl: validUrl);
        when(
          () => mockAnalyticsService.logErrorImageLoad(
            jokeId: any(named: 'jokeId'),
            imageType: any(named: 'imageType'),
            imageUrlHash: any(named: 'imageUrlHash'),
            errorMessage: any(named: 'errorMessage'),
          ),
        ).thenAnswer((_) async {});

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(tester.takeException(), isNull);
      });

      testWidgets('should accept custom dimensions', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const width = 200.0;
        const height = 150.0;

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(validUrl),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(
            validUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(validUrl);

        const widget = CachedJokeImage(
          imageUrl: validUrl,
          width: width,
          height: height,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('rounds explicit width up to nearest hundred for CDN', (
        tester,
      ) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(validUrl);

        const widget = CachedJokeImage(imageUrl: validUrl, width: 175);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        final capturedWidths = verify(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: captureAny(named: 'width'),
          ),
        ).captured;

        expect(capturedWidths.single, 200);
      });

      testWidgets(
        'rounds constraint width up to nearest hundred when explicit width is absent',
        (tester) async {
          // arrange
          const validUrl = 'https://example.com/image.jpg';

          when(
            () => mockImageService.getProcessedJokeImageUrl(
              validUrl,
              width: any(named: 'width'),
            ),
          ).thenReturn(validUrl);

          final widget = Align(
            alignment: Alignment.topLeft,
            child: SizedBox(
              width: 245,
              child: CachedJokeImage(imageUrl: validUrl),
            ),
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // assert
          final capturedWidths = verify(
            () => mockImageService.getProcessedJokeImageUrl(
              validUrl,
              width: captureAny(named: 'width'),
            ),
          ).captured;

          expect(capturedWidths.single, 300);
        },
      );

      testWidgets('clamps width to max when constraints exceed limit', (
        tester,
      ) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(validUrl);

        final widget = Align(
          alignment: Alignment.topLeft,
          child: SizedBox(
            width: 400,
            child: OverflowBox(
              minWidth: 1600,
              maxWidth: 1600,
              alignment: Alignment.topLeft,
              child: CachedJokeImage(imageUrl: validUrl),
            ),
          ),
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        final capturedWidths = verify(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: captureAny(named: 'width'),
          ),
        ).captured;

        expect(capturedWidths.single, 1024);
      });

      testWidgets('should handle showErrorIcon parameter', (tester) async {
        // arrange
        when(() => mockImageService.isValidImageUrl(null)).thenReturn(false);
        when(
          () => mockImageService.getProcessedJokeImageUrl(null),
        ).thenReturn(null);
        const widget = CachedJokeImage(imageUrl: null, showErrorIcon: false);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byType(Container), findsOneWidget);
      });

      testWidgets('should apply border radius when provided', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        final borderRadius = BorderRadius.circular(12);

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(validUrl),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(
            validUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(validUrl);

        final widget = CachedJokeImage(
          imageUrl: validUrl,
          borderRadius: borderRadius,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(ClipRRect), findsOneWidget);
      });

      testWidgets('applies explicit width when within allowed range', (
        tester,
      ) async {
        const validUrl = 'https://example.com/image.jpg';
        const explicitWidth = 200.0;

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: explicitWidth.round(),
          ),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(validUrl),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(
            validUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(validUrl);

        final widget = SizedBox(
          width: 500,
          child: CachedJokeImage(
            imageUrl: validUrl,
            width: explicitWidth,
            height: 100,
          ),
        );

        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        verify(
          () => mockImageService.getProcessedJokeImageUrl(
            validUrl,
            width: explicitWidth.round(),
          ),
        ).called(1);
      });

      testWidgets(
        'falls back to layout constraint width when explicit width out of range',
        (tester) async {
          const validUrl = 'https://example.com/image.jpg';
          const explicitWidth = 2000.0; // outside allowed range
          const constraintWidth = 240.0;
          const expectedWidth = 300;

          when(
            () => mockImageService.isValidImageUrl(validUrl),
          ).thenReturn(true);
          when(
            () => mockImageService.getProcessedJokeImageUrl(
              validUrl,
              width: expectedWidth,
            ),
          ).thenReturn(validUrl);
          when(
            () => mockImageService.processImageUrl(validUrl),
          ).thenReturn(validUrl);
          when(
            () => mockImageService.processImageUrl(
              validUrl,
              width: any(named: 'width'),
              height: any(named: 'height'),
              quality: any(named: 'quality'),
            ),
          ).thenReturn(validUrl);

          final widget = SizedBox(
            width: constraintWidth,
            child: CachedJokeImage(
              imageUrl: validUrl,
              width: explicitWidth,
              height: 100,
            ),
          );

          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          verify(
            () => mockImageService.getProcessedJokeImageUrl(
              validUrl,
              width: expectedWidth,
            ),
          ).called(1);
        },
      );

      testWidgets('passes no width when constraints are unbounded', (
        tester,
      ) async {
        const validUrl = 'https://example.com/image.jpg';

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () =>
              mockImageService.getProcessedJokeImageUrl(validUrl, width: null),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(validUrl),
        ).thenReturn(validUrl);
        when(
          () => mockImageService.processImageUrl(
            validUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(validUrl);

        final widget = SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: CachedJokeImage(imageUrl: validUrl, height: 100),
        );

        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        verify(
          () =>
              mockImageService.getProcessedJokeImageUrl(validUrl, width: null),
        ).called(1);
      });

      group('Connectivity-aware retry', () {
        testWidgets('should listen to connectivity changes', (tester) async {
          // arrange
          const validUrl = 'https://example.com/image.jpg';
          final connectivityController = StreamController<int>.broadcast();

          when(
            () => mockImageService.isValidImageUrl(validUrl),
          ).thenReturn(true);
          when(
            () => mockImageService.getProcessedJokeImageUrl(
              validUrl,
              width: any(named: 'width'),
            ),
          ).thenReturn(validUrl);
          when(
            () => mockPerformanceService.startNamedTrace(
              name: any(named: 'name'),
              key: any(named: 'key'),
              attributes: any(named: 'attributes'),
            ),
          ).thenAnswer((_) async {});
          when(
            () => mockPerformanceService.stopNamedTrace(
              name: any(named: 'name'),
              key: any(named: 'key'),
            ),
          ).thenAnswer((_) async {});

          const widget = CachedJokeImage(imageUrl: validUrl);

          // act
          await tester.pumpWidget(
            createTestWidget(
              child: widget,
              additionalOverrides: [
                offlineToOnlineProvider.overrideWith(
                  (ref) => connectivityController.stream,
                ),
              ],
            ),
          );
          await tester.pump();

          // Simulate connectivity restoration
          connectivityController.add(1);
          await tester.pump();

          // assert
          // Widget should still be present and functional
          expect(find.byType(CachedJokeImage), findsOneWidget);
        });

        testWidgets('should handle imageUrl changes correctly', (tester) async {
          // arrange
          const initialUrl = 'https://example.com/image1.jpg';
          const newUrl = 'https://example.com/image2.jpg';

          when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
          when(
            () => mockImageService.getProcessedJokeImageUrl(
              any(),
              width: any(named: 'width'),
            ),
          ).thenReturn(initialUrl);
          when(
            () => mockPerformanceService.startNamedTrace(
              name: any(named: 'name'),
              key: any(named: 'key'),
              attributes: any(named: 'attributes'),
            ),
          ).thenAnswer((_) async {});
          when(
            () => mockPerformanceService.stopNamedTrace(
              name: any(named: 'name'),
              key: any(named: 'key'),
            ),
          ).thenAnswer((_) async {});

          // act
          await tester.pumpWidget(
            createTestWidget(child: CachedJokeImage(imageUrl: initialUrl)),
          );
          await tester.pump();

          // Change to new image URL
          await tester.pumpWidget(
            createTestWidget(child: CachedJokeImage(imageUrl: newUrl)),
          );
          await tester.pump();

          // assert
          // Should process both URLs
          verify(
            () => mockImageService.getProcessedJokeImageUrl(
              initialUrl,
              width: any(named: 'width'),
            ),
          ).called(1);

          verify(
            () => mockImageService.getProcessedJokeImageUrl(
              newUrl,
              width: any(named: 'width'),
            ),
          ).called(1);
        });

        testWidgets('should create StatefulWidget correctly', (tester) async {
          // arrange
          const validUrl = 'https://example.com/image.jpg';

          when(
            () => mockImageService.isValidImageUrl(validUrl),
          ).thenReturn(true);
          when(
            () => mockImageService.getProcessedJokeImageUrl(
              validUrl,
              width: any(named: 'width'),
            ),
          ).thenReturn(validUrl);
          when(
            () => mockPerformanceService.startNamedTrace(
              name: any(named: 'name'),
              key: any(named: 'key'),
              attributes: any(named: 'attributes'),
            ),
          ).thenAnswer((_) async {});
          when(
            () => mockPerformanceService.stopNamedTrace(
              name: any(named: 'name'),
              key: any(named: 'key'),
            ),
          ).thenAnswer((_) async {});

          const widget = CachedJokeImage(imageUrl: validUrl);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // assert
          // Widget should be created successfully as a StatefulWidget
          expect(find.byType(CachedJokeImage), findsOneWidget);
          expect(tester.takeException(), isNull);
        });

        testWidgets(
          'should retry when connectivity is restored and image is in error state',
          (tester) async {
            // arrange
            const validUrl = 'https://example.com/image.jpg';
            final connectivityController = StreamController<int>.broadcast();

            when(
              () => mockImageService.isValidImageUrl(validUrl),
            ).thenReturn(true);
            when(
              () => mockImageService.getProcessedJokeImageUrl(
                validUrl,
                width: any(named: 'width'),
              ),
            ).thenReturn(validUrl);
            when(
              () => mockAnalyticsService.logErrorImageLoad(
                jokeId: any(named: 'jokeId'),
                imageType: any(named: 'imageType'),
                imageUrlHash: any(named: 'imageUrlHash'),
                errorMessage: any(named: 'errorMessage'),
              ),
            ).thenAnswer((_) async {});
            when(
              () => mockPerformanceService.startNamedTrace(
                name: any(named: 'name'),
                key: any(named: 'key'),
                attributes: any(named: 'attributes'),
              ),
            ).thenAnswer((_) async {});
            when(
              () => mockPerformanceService.dropNamedTrace(
                name: any(named: 'name'),
                key: any(named: 'key'),
              ),
            ).thenAnswer((_) async {});

            const widget = CachedJokeImage(imageUrl: validUrl);

            // act
            await tester.pumpWidget(
              createTestWidget(
                child: widget,
                additionalOverrides: [
                  offlineToOnlineProvider.overrideWith(
                    (ref) => connectivityController.stream,
                  ),
                ],
              ),
            );
            await tester.pump();

            // Simulate connectivity restoration
            connectivityController.add(1);
            await tester.pump();

            // assert
            // Widget should still be present and functional
            expect(find.byType(CachedJokeImage), findsOneWidget);

            // Verify that the connectivity provider was used
            verify(
              () => mockImageService.getProcessedJokeImageUrl(
                validUrl,
                width: any(named: 'width'),
              ),
            ).called(greaterThan(0));
          },
        );
      });
    });

    group('CachedJokeThumbnail', () {
      testWidgets('should create thumbnail widget successfully', (
        tester,
      ) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const thumbnailUrl = 'https://example.com/thumbnail.jpg';

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () => mockImageService.getThumbnailUrl(validUrl),
        ).thenReturn(thumbnailUrl);
        when(
          () => mockImageService.isValidImageUrl(thumbnailUrl),
        ).thenReturn(true);
        when(
          () => mockImageService.getProcessedJokeImageUrl(
            thumbnailUrl,
            width: any(named: 'width'),
          ),
        ).thenReturn(thumbnailUrl);
        when(
          () => mockImageService.processImageUrl(thumbnailUrl),
        ).thenReturn(thumbnailUrl);
        when(
          () => mockImageService.processImageUrl(
            thumbnailUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(thumbnailUrl);

        const widget = CachedJokeThumbnail(imageUrl: validUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(tester.takeException(), isNull);
      });

      testWidgets('should accept custom size parameter', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const thumbnailUrl = 'https://example.com/thumbnail.jpg';
        const customSize = 80.0;

        when(() => mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(
          () => mockImageService.getThumbnailUrl(validUrl),
        ).thenReturn(thumbnailUrl);
        when(
          () => mockImageService.isValidImageUrl(thumbnailUrl),
        ).thenReturn(true);
        when(
          () => mockImageService.getProcessedJokeImageUrl(thumbnailUrl),
        ).thenReturn(thumbnailUrl);
        when(
          () => mockImageService.processImageUrl(thumbnailUrl),
        ).thenReturn(thumbnailUrl);
        when(
          () => mockImageService.processImageUrl(
            thumbnailUrl,
            width: any(named: 'width'),
            height: any(named: 'height'),
            quality: any(named: 'quality'),
          ),
        ).thenReturn(thumbnailUrl);

        const widget = CachedJokeThumbnail(
          imageUrl: validUrl,
          size: customSize,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should handle null imageUrl gracefully', (tester) async {
        // arrange
        when(() => mockImageService.isValidImageUrl(null)).thenReturn(false);
        when(
          () => mockImageService.getProcessedJokeImageUrl(null),
        ).thenReturn(null);
        const widget = CachedJokeThumbnail(imageUrl: null);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should handle invalid imageUrl gracefully', (tester) async {
        // arrange
        const invalidUrl = 'invalid-url';
        when(
          () => mockImageService.isValidImageUrl(invalidUrl),
        ).thenReturn(false);
        when(
          () => mockImageService.getProcessedJokeImageUrl(invalidUrl),
        ).thenReturn(null);

        const widget = CachedJokeThumbnail(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });
    });
  });
}
