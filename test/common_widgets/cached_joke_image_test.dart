import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

import '../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockImageService extends Mock implements ImageService {}

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
        when(() => mockImageService.isValidImageUrl(null)).thenReturn(false);
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

        const widget = CachedJokeImage(imageUrl: invalidUrl);

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
          () => mockImageService.processImageUrl(validUrl),
        ).thenReturn(validUrl);

        const widget = CachedJokeImage(imageUrl: validUrl);

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
          () => mockImageService.processImageUrl(validUrl),
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

      testWidgets('should handle showErrorIcon parameter', (tester) async {
        // arrange
        when(() => mockImageService.isValidImageUrl(null)).thenReturn(false);
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
          () => mockImageService.processImageUrl(validUrl),
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
          () => mockImageService.processImageUrl(thumbnailUrl),
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
          () => mockImageService.processImageUrl(thumbnailUrl),
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
