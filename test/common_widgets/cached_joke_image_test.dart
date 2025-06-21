import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';

import '../test_helpers/firebase_mocks.dart';
import 'cached_joke_image_test.mocks.dart';

@GenerateMocks([ImageService])
void main() {
  group('CachedJokeImage Widget Tests', () {
    late MockImageService mockImageService;

    setUp(() {
      mockImageService = MockImageService();
    });

    Widget createTestWidget({
      required Widget child,
      List<Override> additionalOverrides = const [],
    }) {
      return ProviderScope(
        overrides: [
          imageServiceProvider.overrideWithValue(mockImageService),
          ...FirebaseMocks.getFirebaseProviderOverrides(
            additionalOverrides: additionalOverrides,
          ),
        ],
        child: MaterialApp(theme: lightTheme, home: Scaffold(body: child)),
      );
    }

    group('CachedJokeImage', () {
      testWidgets('should create widget successfully with null imageUrl', (
        tester,
      ) async {
        // arrange
        when(mockImageService.isValidImageUrl(null)).thenReturn(false);
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
        when(mockImageService.isValidImageUrl(invalidUrl)).thenReturn(false);

        const widget = CachedJokeImage(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byType(Container), findsOneWidget);
      });

      testWidgets(
        'should create widget successfully with valid imageUrl',
        (tester) async {
          // arrange
          const validUrl = 'https://example.com/image.jpg';

          when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
          when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);

          const widget = CachedJokeImage(imageUrl: validUrl);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // assert
          expect(find.byType(CachedJokeImage), findsOneWidget);
          
          // Widget should be created successfully without throwing
          expect(tester.takeException(), isNull);
        },
      );

      testWidgets('should accept custom dimensions', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const width = 200.0;
        const height = 150.0;

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);

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
        // Widget should be created successfully with custom dimensions
      });

      testWidgets('should handle showErrorIcon parameter', (tester) async {
        // arrange
        when(mockImageService.isValidImageUrl(null)).thenReturn(false);
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

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);

        final widget = CachedJokeImage(
          imageUrl: validUrl,
          borderRadius: borderRadius,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        // When border radius is provided, widget should be wrapped in ClipRRect
        expect(find.byType(ClipRRect), findsOneWidget);
      });
    });

    group('CachedJokeThumbnail', () {
      testWidgets('should create thumbnail widget successfully', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const thumbnailUrl = 'https://example.com/thumbnail.jpg';

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.getThumbnailUrl(validUrl)).thenReturn(thumbnailUrl);
        when(mockImageService.isValidImageUrl(thumbnailUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(thumbnailUrl)).thenReturn(thumbnailUrl);

        const widget = CachedJokeThumbnail(imageUrl: validUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
        // Widget should be created successfully without throwing
        expect(tester.takeException(), isNull);
      });

      testWidgets('should accept custom size parameter', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const thumbnailUrl = 'https://example.com/thumbnail.jpg';
        const customSize = 80.0;

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.getThumbnailUrl(validUrl)).thenReturn(thumbnailUrl);
        when(mockImageService.isValidImageUrl(thumbnailUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(thumbnailUrl)).thenReturn(thumbnailUrl);

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
        when(mockImageService.isValidImageUrl(null)).thenReturn(false);
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
        when(mockImageService.isValidImageUrl(invalidUrl)).thenReturn(false);

        const widget = CachedJokeThumbnail(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });
    });

    group('CachedJokeHeroImage', () {
      testWidgets('should create hero image with correct structure', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const heroTag = 'test-hero';

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);

        const widget = CachedJokeHeroImage(
          imageUrl: validUrl,
          heroTag: heroTag,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeHeroImage), findsOneWidget);
        expect(find.byType(Hero), findsOneWidget);
        expect(find.byType(GestureDetector), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);

        final hero = tester.widget<Hero>(find.byType(Hero));
        expect(hero.tag, equals(heroTag));
      });

      testWidgets('should handle tap callback', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const heroTag = 'test-hero';
        var tapCount = 0;

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);

        final widget = CachedJokeHeroImage(
          imageUrl: validUrl,
          heroTag: heroTag,
          onTap: () => tapCount++,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.tap(find.byType(GestureDetector));

        // assert
        expect(tapCount, equals(1));
      });

      testWidgets('should accept custom dimensions', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const heroTag = 'test-hero';
        const width = 300.0;
        const height = 200.0;

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);

        const widget = CachedJokeHeroImage(
          imageUrl: validUrl,
          heroTag: heroTag,
          width: width,
          height: height,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeHeroImage), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should handle null imageUrl gracefully', (tester) async {
        // arrange
        const heroTag = 'test-hero';
        when(mockImageService.isValidImageUrl(null)).thenReturn(false);

        const widget = CachedJokeHeroImage(imageUrl: null, heroTag: heroTag);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeHeroImage), findsOneWidget);
        expect(find.byType(Hero), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });
    });

    group('Widget creation and structure', () {
      testWidgets('should handle ImageService errors gracefully', (tester) async {
        // arrange
        const invalidUrl = 'malformed-url';
        when(mockImageService.isValidImageUrl(invalidUrl)).thenReturn(false);

        const widget = CachedJokeImage(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        // Widget should handle service errors gracefully without throwing
        expect(tester.takeException(), isNull);
      });

      testWidgets('should maintain consistent widget hierarchy', (
        tester,
      ) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(validUrl);
        when(mockImageService.getThumbnailUrl(validUrl)).thenReturn(validUrl);

        final widgets = Column(
          children: const [
            CachedJokeImage(imageUrl: validUrl),
            CachedJokeThumbnail(imageUrl: validUrl),
            CachedJokeHeroImage(imageUrl: validUrl, heroTag: 'test'),
          ],
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widgets));
        await tester.pump();

        // assert
        expect(find.byType(CachedJokeImage), findsNWidgets(3));
        expect(find.byType(CachedJokeThumbnail), findsOneWidget);
        expect(find.byType(CachedJokeHeroImage), findsOneWidget);
        expect(find.byType(Hero), findsOneWidget);
      });

      testWidgets('widgets should build without throwing exceptions', (
        tester,
      ) async {
        // arrange
        const widgets = [
          CachedJokeImage(imageUrl: null),
          CachedJokeImage(imageUrl: 'invalid-url'),
          CachedJokeImage(imageUrl: 'https://example.com/valid.jpg'),
          CachedJokeThumbnail(imageUrl: null),
          CachedJokeThumbnail(imageUrl: 'invalid-url'),
          CachedJokeThumbnail(imageUrl: 'https://example.com/valid.jpg'),
          CachedJokeHeroImage(imageUrl: null, heroTag: 'hero1'),
          CachedJokeHeroImage(imageUrl: 'invalid-url', heroTag: 'hero2'),
          CachedJokeHeroImage(imageUrl: 'https://example.com/valid.jpg', heroTag: 'hero3'),
        ];

        // Mock all possible calls
        when(mockImageService.isValidImageUrl(null)).thenReturn(false);
        when(mockImageService.isValidImageUrl('invalid-url')).thenReturn(false);
        when(mockImageService.isValidImageUrl('https://example.com/valid.jpg')).thenReturn(true);
        when(mockImageService.processImageUrl('https://example.com/valid.jpg')).thenReturn('https://example.com/valid.jpg');
        when(mockImageService.getThumbnailUrl('https://example.com/valid.jpg')).thenReturn('https://example.com/valid.jpg');

        // Test each widget individually
        for (final widget in widgets) {
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // assert
          expect(tester.takeException(), isNull, reason: 'Widget should not throw: ${widget.runtimeType}');
        }
      });
    });
  });
}
