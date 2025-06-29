import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeImageCarousel extends ConsumerStatefulWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onSetupTap;
  final VoidCallback? onPunchlineTap;
  final Function(int)? onImageStateChanged;
  final bool isAdminMode;
  final List<Joke>? jokesToPreload;

  const JokeImageCarousel({
    super.key,
    required this.joke,
    this.index,
    this.onSetupTap,
    this.onPunchlineTap,
    this.onImageStateChanged,
    this.isAdminMode = false,
    this.jokesToPreload,
  });

  @override
  ConsumerState<JokeImageCarousel> createState() => _JokeImageCarouselState();
}

class _JokeImageCarouselState extends ConsumerState<JokeImageCarousel> {
  late PageController _pageController;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _preloadImages();

    // Initialize image state (starts at setup image = index 0)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.onImageStateChanged != null) {
        widget.onImageStateChanged!(0);
      }
    });
  }

  void _preloadImages() {
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return; // Ensure the widget is still in the tree
      final imageService = ref.read(imageServiceProvider);

      try {
        // Preload images for the current joke
        await CachedJokeImage.precacheJokeImages(
          widget.joke,
          context,
          imageService,
        );

        // Preload images for the next jokes
        if (widget.jokesToPreload != null && mounted) {
          await CachedJokeImage.precacheMultipleJokeImages(
            widget.jokesToPreload!,
            context,
            imageService,
          );
        }
      } catch (e) {
        // Silently handle any precaching errors
        debugPrint('Error during image precaching: $e');
      }
    });
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

    // Notify parent about image state change
    if (widget.onImageStateChanged != null) {
      widget.onImageStateChanged!(index);
    }
  }

  void _onImageTap() {
    if (_currentIndex == 0) {
      // Currently showing setup image
      // Call callback if provided (for tracking)
      if (widget.onSetupTap != null) {
        widget.onSetupTap!();
      }
      // Always do default behavior: go to punchline
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      // Currently showing punchline image
      if (widget.onPunchlineTap != null) {
        widget.onPunchlineTap!();
      } else {
        // Default behavior: go back to setup
        _pageController.previousPage(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final populationState = ref.watch(jokePopulationProvider);
    final isPopulating = populationState.populatingJokes.contains(
      widget.joke.id,
    );

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 14.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Image carousel
          Flexible(
            child: Card(
              child: GestureDetector(
                onTap: _onImageTap,
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: 200, // Ensure minimum usable height
                  ),
                  child: ClipRRect(
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(16),
                      bottom: Radius.circular(16),
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
                          _buildImagePage(
                            imageUrl: widget.joke.punchlineImageUrl,
                          ),
                        ],
                      ),
                    ),
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

          // Regenerate buttons (only shown in admin mode)
          if (widget.isAdminMode)
            Padding(
              padding: const EdgeInsets.only(
                left: 16.0,
                right: 16.0,
                bottom: 16.0,
              ),
              child: Row(
                children: [
                  // Regenerate All button (left)
                  Expanded(
                    child: ElevatedButton.icon(
                      key: const Key('regenerate-all-button'),
                      onPressed:
                          isPopulating
                              ? null
                              : () async {
                                final notifier = ref.read(
                                  jokePopulationProvider.notifier,
                                );
                                await notifier.populateJoke(
                                  widget.joke.id,
                                  imagesOnly: false,
                                );
                              },
                      icon:
                          isPopulating
                              ? SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(
                                    Theme.of(context).colorScheme.onSurface
                                        .withValues(alpha: 0.6),
                                  ),
                                ),
                              )
                              : const Icon(Icons.refresh),
                      label: Text(
                        isPopulating ? 'Regenerating...' : 'Redo All',
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor:
                            Theme.of(context).colorScheme.primaryContainer,
                        foregroundColor:
                            Theme.of(context).colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8.0),
                  // Regenerate Images button (right)
                  Expanded(
                    child: ElevatedButton.icon(
                      key: const Key('regenerate-images-button'),
                      onPressed:
                          isPopulating
                              ? null
                              : () async {
                                final notifier = ref.read(
                                  jokePopulationProvider.notifier,
                                );
                                await notifier.populateJoke(
                                  widget.joke.id,
                                  imagesOnly: true,
                                );
                              },
                      icon:
                          isPopulating
                              ? SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(
                                    Theme.of(context).colorScheme.onSurface
                                        .withValues(alpha: 0.6),
                                  ),
                                ),
                              )
                              : const Icon(Icons.image),
                      label: Text(
                        isPopulating ? 'Regenerating...' : 'Redo Images',
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor:
                            Theme.of(context).colorScheme.secondaryContainer,
                        foregroundColor:
                            Theme.of(context).colorScheme.onSecondaryContainer,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Error display (only shown in admin mode)
          if (widget.isAdminMode && populationState.error != null)
            Padding(
              padding: const EdgeInsets.only(
                left: 16.0,
                right: 16.0,
                bottom: 8.0,
              ),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12.0),
                decoration: BoxDecoration(
                  color: Theme.of(
                    context,
                  ).appColors.authError.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8.0),
                  border: Border.all(
                    color: Theme.of(
                      context,
                    ).appColors.authError.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.error_outline,
                      size: 16,
                      color: Theme.of(context).appColors.authError,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        populationState.error!,
                        style: TextStyle(
                          color: Theme.of(context).appColors.authError,
                          fontSize: 12,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () {
                        ref.read(jokePopulationProvider.notifier).clearError();
                      },
                      icon: Icon(
                        Icons.close,
                        size: 16,
                        color: Theme.of(context).appColors.authError,
                      ),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildImagePage({required String? imageUrl}) {
    return CachedJokeImage(
      imageUrl: imageUrl,
      fit: BoxFit.cover,
      showLoadingIndicator: true,
      showErrorIcon: true,
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
