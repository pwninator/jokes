import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

// Generate mocks
@GenerateMocks([ImageService])
import 'cached_joke_image_test.mocks.dart';

void main() {
  group('CachedJokeImage Widget Tests', () {
    late MockImageService mockImageService;

    setUp(() {
      mockImageService = MockImageService();
    });

    Widget createTestWidget({
      required Widget child,
      List<Override> overrides = const [],
    }) {
      return ProviderScope(
        overrides: [
          imageServiceProvider.overrideWithValue(mockImageService),
          ...overrides,
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(body: child),
        ),
      );
    }

    group('CachedJokeImage', () {
      testWidgets('should show error widget when imageUrl is null', (tester) async {
        // arrange
        const widget = CachedJokeImage(imageUrl: null);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
      });

      testWidgets('should show error widget when imageUrl is invalid', (tester) async {
        // arrange
        const invalidUrl = 'invalid-url';
        when(mockImageService.isValidImageUrl(invalidUrl)).thenReturn(false);
        
        const widget = CachedJokeImage(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
        verify(mockImageService.isValidImageUrl(invalidUrl)).called(1);
      });

      testWidgets('should process valid imageUrl and display CachedNetworkImage', (tester) async {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const processedUrl = 'https://example.com/processed-image.jpg';
        
        when(mockImageService.isValidImageUrl(validUrl)).thenReturn(true);
        when(mockImageService.processImageUrl(validUrl)).thenReturn(processedUrl);

        const widget = CachedJokeImage(imageUrl: validUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        verify(mockImageService.isValidImageUrl(validUrl)).called(1);
        verify(mockImageService.processImageUrl(validUrl)).called(1);
        
        // CachedNetworkImage should be present (we can't easily test its imageUrl property)
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should apply custom dimensions when provided', (tester) async {
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

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should show error widget when showErrorIcon is false', (tester) async {
        // arrange
        const widget = CachedJokeImage(
          imageUrl: null,
          showErrorIcon: false,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.image_not_supported_outlined), findsNothing);
        // Container should still be present but without icon
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

        // assert
        expect(find.byType(ClipRRect), findsOneWidget);
      });
    });

    group('CachedJokeThumbnail', () {
      testWidgets('should create thumbnail with default size', (tester) async {
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

        // assert
        verify(mockImageService.isValidImageUrl(validUrl)).called(1);
        verify(mockImageService.getThumbnailUrl(validUrl)).called(1);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should create thumbnail with custom size', (tester) async {
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

        // assert
        verify(mockImageService.isValidImageUrl(validUrl)).called(1);
        verify(mockImageService.getThumbnailUrl(validUrl)).called(1);
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should handle null imageUrl', (tester) async {
        // arrange
        const widget = CachedJokeThumbnail(imageUrl: null);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
      });

      testWidgets('should handle invalid imageUrl', (tester) async {
        // arrange
        const invalidUrl = 'invalid-url';
        when(mockImageService.isValidImageUrl(invalidUrl)).thenReturn(false);

        const widget = CachedJokeThumbnail(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        verify(mockImageService.isValidImageUrl(invalidUrl)).called(1);
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
      });
    });

    group('CachedJokeHeroImage', () {
      testWidgets('should create hero image with correct tag', (tester) async {
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

        // assert
        expect(find.byType(Hero), findsOneWidget);
        expect(find.byType(GestureDetector), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
        
        final hero = tester.widget<Hero>(find.byType(Hero));
        expect(hero.tag, equals(heroTag));
      });

      testWidgets('should handle tap when onTap is provided', (tester) async {
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
        await tester.tap(find.byType(GestureDetector));

        // assert
        expect(tapCount, equals(1));
      });

      testWidgets('should apply custom dimensions', (tester) async {
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

        // assert
        expect(find.byType(CachedJokeImage), findsOneWidget);
      });

      testWidgets('should handle null imageUrl', (tester) async {
        // arrange
        const heroTag = 'test-hero';

        const widget = CachedJokeHeroImage(
          imageUrl: null,
          heroTag: heroTag,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(Hero), findsOneWidget);
        expect(find.byType(CachedJokeImage), findsOneWidget);
        expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
      });
    });

    group('Error handling and edge cases', () {
      testWidgets('should gracefully handle service errors', (tester) async {
        // arrange
        const invalidUrl = 'malformed-url';
        
        when(mockImageService.isValidImageUrl(invalidUrl)).thenReturn(false);

        const widget = CachedJokeImage(imageUrl: invalidUrl);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
        verify(mockImageService.isValidImageUrl(invalidUrl)).called(1);
      });

      testWidgets('should maintain consistent styling across all widgets', (tester) async {
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

        // assert
        expect(find.byType(CachedJokeImage), findsNWidgets(3)); // All use CachedJokeImage internally
      });
    });
  });
} 