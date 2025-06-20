import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeImageCarousel extends StatefulWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onTap;

  const JokeImageCarousel({
    super.key,
    required this.joke,
    this.index,
    this.onTap,
  });

  @override
  State<JokeImageCarousel> createState() => _JokeImageCarouselState();
}

class _JokeImageCarouselState extends State<JokeImageCarousel> {
  late PageController _pageController;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _onPageChanged(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  void _onImageTap() {
    if (_currentIndex == 0) {
      // Currently showing setup image, go to punchline
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      // Currently showing punchline image, go back to setup
      _pageController.previousPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Image carousel
          Flexible(
            child: GestureDetector(
              onTap: widget.onTap ?? _onImageTap,
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight:
                      400, // Prevent infinite height in test environments
                  minHeight: 200, // Ensure minimum usable height
                ),
                child: AspectRatio(
                  aspectRatio: 1.0,
                  child: PageView(
                    controller: _pageController,
                    onPageChanged: _onPageChanged,
                    children: [
                      // Setup image
                      _buildImagePage(imageUrl: widget.joke.setupImageUrl),
                      // Punchline image
                      _buildImagePage(imageUrl: widget.joke.punchlineImageUrl),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // Page indicators and navigation hints
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Page indicators
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _buildPageIndicator(0),
                    const SizedBox(width: 8),
                    _buildPageIndicator(1),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImagePage({required String? imageUrl}) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(
          top: Radius.circular(8),
          bottom: Radius.circular(8),
        ),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          // Image
          ClipRRect(
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(8),
              bottom: Radius.circular(8),
            ),
            child: CachedJokeImage(
              imageUrl: imageUrl,
              fit: BoxFit.cover,
              showLoadingIndicator: true,
              showErrorIcon: true,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPageIndicator(int index) {
    final isActive = index == _currentIndex;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      width: isActive ? 24 : 8,
      height: 8,
      decoration: BoxDecoration(
        color:
            isActive
                ? Theme.of(context).colorScheme.primary
                : Theme.of(
                  context,
                ).colorScheme.onSurface.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(4),
      ),
    );
  }
}
