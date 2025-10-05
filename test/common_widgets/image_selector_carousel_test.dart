import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';

void main() {
  const imageUrls = [
    'https://example.com/image1.jpg',
    'https://example.com/image2.jpg',
    'https://example.com/image3.jpg',
  ];

  Widget createTestWidget({
    required List<String> images,
    String? selectedImage,
    required Function(String?) onImageSelected,
  }) {
    return ProviderScope(
      child: MaterialApp(
        home: Scaffold(
          body: ImageSelectorCarousel(
            imageUrls: images,
            selectedImageUrl: selectedImage,
            title: 'Test Images',
            onImageSelected: onImageSelected,
          ),
        ),
      ),
    );
  }

  group('ImageSelectorCarousel Rendering', () {
    testWidgets('renders correctly based on the number of images', (tester) async {
      // --- Case 1: No images ---
      await tester.pumpWidget(createTestWidget(
        images: [],
        onImageSelected: (_) {},
      ));
      // Should not render the title or carousel if there are no images
      expect(find.text('Test Images'), findsNothing);
      expect(find.byType(PageView), findsNothing);

      // --- Case 2: One image ---
      await tester.pumpWidget(createTestWidget(
        images: [imageUrls.first],
        onImageSelected: (_) {},
      ));
      expect(find.text('Test Images'), findsOneWidget);
      expect(find.byType(PageView), findsOneWidget);
      // Page indicators should not be shown for a single image
      expect(find.byType(AnimatedContainer), findsNothing);

      // --- Case 3: Multiple images ---
      await tester.pumpWidget(createTestWidget(
        images: imageUrls,
        onImageSelected: (_) {},
      ));
      expect(find.text('Test Images'), findsOneWidget);
      expect(find.byType(PageView), findsOneWidget);
      // Page indicators should be shown for multiple images
      expect(
        find.byType(AnimatedContainer),
        findsNWidgets(imageUrls.length),
      );
    });
  });

  group('ImageSelectorCarousel Interaction', () {
    testWidgets('handles initial selection and user swipes correctly', (tester) async {
      String? selectedImage;
      // --- Case 1: Initialize with a selected image ---
      await tester.pumpWidget(createTestWidget(
        images: imageUrls,
        selectedImage: imageUrls[1], // Pre-select the second image
        onImageSelected: (url) => selectedImage = url,
      ));

      await tester.pump(); // Let initialization complete

      // onImageSelected should NOT be called on initial build
      expect(selectedImage, isNull, reason: 'Callback should not be called on initial build');

      // Verify the second page indicator is active
      final PageView pageView = tester.widget(find.byType(PageView));
      expect(pageView.controller!.initialPage, 1);

      // --- Case 2: User swipes to a new image ---
      // Swipe from the second to the third image
      await tester.drag(find.byType(PageView), const Offset(-400, 0));
      // Replace pumpAndSettle with manual pumps to avoid timeout
      await tester.pump(); // Start scroll animation
      await tester.pump(const Duration(seconds: 1)); // Wait for animation to finish

      // onImageSelected should now be called with the new image URL
      expect(
        selectedImage,
        imageUrls[2],
        reason: 'Callback should be called with the new image URL after a swipe',
      );
    });
  });
}