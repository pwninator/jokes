import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
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
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return; // Ensure the widget is still in the tree
      final imageService = ref.read(imageServiceProvider);

      // Preload images for the current joke
      _precacheJokeImages(widget.joke, imageService, context);

      // Preload images for the next jokes
      if (widget.jokesToPreload != null) {
        for (final jokeToPreload in widget.jokesToPreload!) {
          _precacheJokeImages(jokeToPreload, imageService, context);
        }
      }
    });
  }

  void _precacheJokeImages(
    Joke joke,
    ImageService imageService,
    BuildContext context,
  ) {
    // Preload setup image
    if (joke.setupImageUrl != null &&
        imageService.isValidImageUrl(joke.setupImageUrl)) {
      final processedSetupUrl = imageService.processImageUrl(
        joke.setupImageUrl!,
      );
      precacheImage(
        CachedNetworkImageProvider(processedSetupUrl),
        context,
      ).catchError((error, stackTrace) {
        // Silently handle preload errors - the actual image widget will show error state
        debugPrint(
          'Failed to preload setup image for joke ${joke.id}: $error\n$stackTrace',
        );
      });
    }

    // Preload punchline image
    if (joke.punchlineImageUrl != null &&
        imageService.isValidImageUrl(joke.punchlineImageUrl)) {
      final processedPunchlineUrl = imageService.processImageUrl(
        joke.punchlineImageUrl!,
      );
      precacheImage(
        CachedNetworkImageProvider(processedPunchlineUrl),
        context,
      ).catchError((error, stackTrace) {
        // Silently handle preload errors - the actual image widget will show error state
        debugPrint(
          'Failed to preload punchline image for joke ${joke.id}: $error\n$stackTrace',
        );
      });
    }
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

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Image carousel
          Flexible(
            child: GestureDetector(
              onTap: _onImageTap,
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

          // Regenerate button (only shown in admin mode)
          if (widget.isAdminMode)
            Padding(
              padding: const EdgeInsets.only(
                left: 16.0,
                right: 16.0,
                bottom: 16.0,
              ),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed:
                      isPopulating
                          ? null
                          : () async {
                            final notifier = ref.read(
                              jokePopulationProvider.notifier,
                            );
                            await notifier.populateJoke(widget.joke.id);
                          },
                  icon:
                      isPopulating
                          ? SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Theme.of(
                                  context,
                                ).colorScheme.onSurface.withValues(alpha: 0.6),
                              ),
                            ),
                          )
                          : const Icon(Icons.refresh),
                  label: Text(
                    isPopulating
                        ? 'Regenerating Images...'
                        : 'Regenerate Images',
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor:
                        Theme.of(context).colorScheme.primaryContainer,
                    foregroundColor:
                        Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
                ),
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
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0),
      child: Container(
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
