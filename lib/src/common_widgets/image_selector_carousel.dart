import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';

class ImageSelectorCarousel extends ConsumerStatefulWidget {
  final List<String> imageUrls;
  final String? selectedImageUrl;
  final String title;
  final Function(String?) onImageSelected;
  final double height;

  const ImageSelectorCarousel({
    super.key,
    required this.imageUrls,
    this.selectedImageUrl,
    required this.title,
    required this.onImageSelected,
    this.height = 120,
  });

  @override
  ConsumerState<ImageSelectorCarousel> createState() =>
      _ImageSelectorCarouselState();
}

class _ImageSelectorCarouselState extends ConsumerState<ImageSelectorCarousel> {
  late PageController _pageController;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();

    // Set initial index to selected image
    final initialIndex = widget.selectedImageUrl != null
        ? widget.imageUrls.indexOf(widget.selectedImageUrl!)
        : 0;
    _currentIndex = (initialIndex >= 0) ? initialIndex : 0;

    // Create PageController with initial page
    _pageController = PageController(
      initialPage: _currentIndex,
      viewportFraction: 0.4,
    );
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _onPageChanged(int index) {
    if (index == _currentIndex) {
      return;
    }

    setState(() {
      _currentIndex = index;
    });

    if (widget.selectedImageUrl != widget.imageUrls[index]) {
      widget.onImageSelected(widget.imageUrls[index]);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.imageUrls.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title
        Text(
          widget.title,
          style: Theme.of(
            context,
          ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),

        // Carousel
        Container(
          height: widget.height,
          decoration: BoxDecoration(
            border: Border.all(
              color: Theme.of(
                context,
              ).colorScheme.outline.withValues(alpha: 0.3),
            ),
            borderRadius: BorderRadius.circular(8),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: PageView.builder(
              controller: _pageController,
              onPageChanged: _onPageChanged,
              itemCount: widget.imageUrls.length,
              itemBuilder: (context, index) {
                return _buildImagePage(widget.imageUrls[index], index);
              },
            ),
          ),
        ),

        const SizedBox(height: 8),

        // Page indicators
        if (widget.imageUrls.length > 1)
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(
              widget.imageUrls.length,
              (index) => _buildPageIndicator(index),
            ),
          ),
      ],
    );
  }

  Widget _buildImagePage(String imageUrl, int index) {
    final isSelected = index == _currentIndex;

    return Center(
      child: AspectRatio(
        aspectRatio: 1.0, // Assuming square images, adjust if needed
        child: Stack(
          children: [
            // Image
            CachedJokeImage(
              imageUrl: imageUrl,
              fit: BoxFit.cover,
              showLoadingIndicator: true,
              showErrorIcon: true,
            ),

            // Selection indicator overlay
            if (isSelected)
              Positioned.fill(
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: Theme.of(context).colorScheme.primary,
                      width: 3,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildPageIndicator(int index) {
    final isActive = index == _currentIndex;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 2),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: isActive ? 20 : 8,
        height: 8,
        decoration: BoxDecoration(
          color: isActive
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}
