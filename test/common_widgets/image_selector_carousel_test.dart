import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';

void main() {
  group('ImageSelectorCarousel', () {
    testWidgets('should not render when imageUrls is empty', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: ImageSelectorCarousel(
                imageUrls: const [],
                title: 'Test Images',
                onImageSelected: (_) {},
              ),
            ),
          ),
        ),
      );

      expect(find.byType(ImageSelectorCarousel), findsOneWidget);
      expect(find.text('Test Images'), findsNothing);
    });

    testWidgets('should render with images and title', (tester) async {
      const imageUrls = [
        'https://example.com/image1.jpg',
        'https://example.com/image2.jpg',
      ];

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: ImageSelectorCarousel(
                imageUrls: imageUrls,
                title: 'Test Images',
                onImageSelected: (_) {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test Images'), findsOneWidget);
      expect(find.byType(PageView), findsOneWidget);
    });

    testWidgets('should show page indicators when multiple images', (
      tester,
    ) async {
      const imageUrls = [
        'https://example.com/image1.jpg',
        'https://example.com/image2.jpg',
        'https://example.com/image3.jpg',
      ];

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: ImageSelectorCarousel(
                imageUrls: imageUrls,
                title: 'Test Images',
                onImageSelected: (_) {},
              ),
            ),
          ),
        ),
      );

      // Should show 3 page indicators
      expect(find.byType(AnimatedContainer), findsWidgets);
    });

    testWidgets('should not call onImageSelected on initial load', (
      tester,
    ) async {
      const imageUrls = [
        'https://example.com/image1.jpg',
        'https://example.com/image2.jpg',
      ];

      String? selectedImage;

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: ImageSelectorCarousel(
                imageUrls: imageUrls,
                title: 'Test Images',
                onImageSelected: (imageUrl) {
                  selectedImage = imageUrl;
                },
              ),
            ),
          ),
        ),
      );

      // Wait for initial frame and initialization to complete
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 1));

      // Should not call onImageSelected on initial load
      expect(selectedImage, isNull);
    });

    testWidgets('should call onImageSelected when user swipes', (tester) async {
      const imageUrls = [
        'https://example.com/image1.jpg',
        'https://example.com/image2.jpg',
      ];

      String? selectedImage;

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: ImageSelectorCarousel(
                imageUrls: imageUrls,
                title: 'Test Images',
                onImageSelected: (imageUrl) {
                  selectedImage = imageUrl;
                },
              ),
            ),
          ),
        ),
      );

      // Wait for initial frame and initialization to complete
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 1));

      // Initially should not call onImageSelected
      expect(selectedImage, isNull);

      // Swipe to next page (this triggers user interaction)
      await tester.drag(find.byType(PageView), const Offset(-600, 0));
      await tester.pump();

      // Should now select second image
      expect(selectedImage, equals(imageUrls[1]));
    });

    testWidgets('should initialize with selected image but not call callback', (
      tester,
    ) async {
      const imageUrls = [
        'https://example.com/image1.jpg',
        'https://example.com/image2.jpg',
      ];

      String? selectedImage;

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: ImageSelectorCarousel(
                imageUrls: imageUrls,
                selectedImageUrl: imageUrls[1], // Start with second image
                title: 'Test Images',
                onImageSelected: (imageUrl) {
                  selectedImage = imageUrl;
                },
              ),
            ),
          ),
        ),
      );

      // Wait for initial frame and initialization to complete
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 1));

      // Should not call onImageSelected on initial load, even with selectedImageUrl
      expect(selectedImage, isNull);
    });
  });
}
