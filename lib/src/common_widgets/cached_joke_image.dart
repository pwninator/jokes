import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class CachedJokeImage extends ConsumerWidget {
  const CachedJokeImage({
    super.key,
    required this.imageUrl,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.borderRadius,
    this.showLoadingIndicator = true,
    this.showErrorIcon = true,
  });

  final String? imageUrl;
  final double? width;
  final double? height;
  final BoxFit fit;
  final BorderRadius? borderRadius;
  final bool showLoadingIndicator;
  final bool showErrorIcon;

  // Because of the sketchy style of the joke images, lower quality is ok
  static const int imageQuality = 50;

  // Shared HTTP headers used for both widget display and precaching
  static const Map<String, String> httpHeaders = {
    'Accept': 'image/webp,image/avif,image/apng,image/*,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
  };

  /// Returns the processed image URL using shared configuration, or null if invalid
  static String? _getProcessedImageUrl(
    String? imageUrl,
    ImageService imageService,
  ) {
    if (imageUrl == null || !imageService.isValidImageUrl(imageUrl)) {
      return null;
    }

    return imageService.processImageUrl(
      imageUrl,
      quality: imageQuality.toString(),
    );
  }

  /// Precaches a single joke image with the same configuration as the widget
  /// Uses disk caching for efficiency and works in both foreground and background
  /// Returns the processed URL if successful, null otherwise
  static Future<String?> precacheJokeImage(
    String? imageUrl,
    ImageService imageService,
  ) async {
    final processedUrl = _getProcessedImageUrl(imageUrl, imageService);
    if (processedUrl == null) return null;

    try {
      // Download and cache to disk using DefaultCacheManager
      // CachedNetworkImage will find this in disk cache and load instantly
      await DefaultCacheManager().downloadFile(processedUrl);
      debugPrint('Precached image: $processedUrl');
      return processedUrl;
    } catch (error, stackTrace) {
      // Silently handle preload errors - the actual image widget will show error state
      debugPrint('Failed to precache image $imageUrl: $error\n$stackTrace');
      return null;
    }
  }

  /// Precaches both setup and punchline images for a joke
  /// Returns the processed URLs for both images
  static Future<({String? setupUrl, String? punchlineUrl})> precacheJokeImages(
    Joke joke,
    ImageService imageService,
  ) async {
    // Precache both images in parallel and get their processed URLs
    final results = await Future.wait([
      precacheJokeImage(joke.setupImageUrl, imageService),
      precacheJokeImage(joke.punchlineImageUrl, imageService),
    ]);
    
    return (setupUrl: results[0], punchlineUrl: results[1]);
  }

  /// Precaches images for multiple jokes
  static Future<void> precacheMultipleJokeImages(
    List<Joke> jokes,
    ImageService imageService,
  ) async {
    // Precache all jokes sequentially to avoid overwhelming the cache
    for (final joke in jokes) {
      try {
        await precacheJokeImages(joke, imageService);
      } catch (e) {
        debugPrint('Failed to precache images for joke ${joke.id}: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final imageService = ref.read(imageServiceProvider);

    // Use shared URL processing logic
    final processedUrl = _getProcessedImageUrl(imageUrl, imageService);
    if (processedUrl == null) {
      return _buildErrorWidget(context);
    }

    Widget imageWidget = CachedNetworkImage(
      imageUrl: processedUrl,
      width: width,
      height: height,
      fit: fit,
      httpHeaders: httpHeaders,
      placeholder:
          showLoadingIndicator
              ? (context, url) => _buildLoadingWidget(context)
              : null,
      errorWidget:
          showErrorIcon
              ? (context, url, error) => _buildErrorWidget(context)
              : (context, url, error) => const SizedBox.shrink(),
      fadeInDuration: const Duration(milliseconds: 300),
      fadeOutDuration: const Duration(milliseconds: 100),
    );

    // Log image info with size
    _logImageInfo(processedUrl);

    // Apply border radius if specified
    if (borderRadius != null) {
      imageWidget = ClipRRect(borderRadius: borderRadius!, child: imageWidget);
    }

    return imageWidget;
  }

  void _logImageInfo(String url) async {
    try {
      final fileInfo = await DefaultCacheManager().getFileFromCache(url);
      if (fileInfo != null) {
        final sizeInBytes = await fileInfo.file.length();
        final sizeInKB = (sizeInBytes / 1024).toStringAsFixed(1);
        debugPrint("Loading image (CachedJokeImage): $url (${sizeInKB}KB)");
      } else {
        debugPrint(
          "Loading image (CachedJokeImage): $url (size unknown - not cached)",
        );
      }
    } catch (e) {
      debugPrint("Loading image (CachedJokeImage): $url (size error: $e)");
    }
  }

  Widget _buildLoadingWidget(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: borderRadius,
      ),
      child: Center(
        child: SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation<Color>(
              Theme.of(context).colorScheme.primary,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildErrorWidget(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: borderRadius,
        border: Border.all(
          color: Theme.of(context).colorScheme.outline,
          width: 1,
        ),
      ),
      child:
          showErrorIcon
              ? Center(
                child: Icon(
                  Icons.image_not_supported_outlined,
                  size: 32,
                  color: Theme.of(
                    context,
                  ).colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              )
              : null,
    );
  }
}

/// Specialized version for thumbnails
class CachedJokeThumbnail extends ConsumerWidget {
  const CachedJokeThumbnail({
    super.key,
    required this.imageUrl,
    this.size = 100,
  });

  final String? imageUrl;
  final double size;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final imageService = ref.read(imageServiceProvider);
    final thumbnailUrl =
        imageUrl != null && imageService.isValidImageUrl(imageUrl)
            ? imageService.getThumbnailUrl(imageUrl!)
            : null;

    return CachedJokeImage(
      imageUrl: thumbnailUrl,
      width: size,
      height: size,
      fit: BoxFit.cover,
      borderRadius: BorderRadius.circular(8),
    );
  }
}

/// Specialized version for full-size images with hero animation support
class CachedJokeHeroImage extends ConsumerWidget {
  const CachedJokeHeroImage({
    super.key,
    required this.imageUrl,
    required this.heroTag,
    this.width,
    this.height,
    this.onTap,
  });

  final String? imageUrl;
  final String heroTag;
  final double? width;
  final double? height;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final imageWidget = CachedJokeImage(
      imageUrl: imageUrl,
      width: width,
      height: height,
      fit: BoxFit.contain,
      borderRadius: BorderRadius.circular(12),
    );

    return Hero(
      tag: heroTag,
      child: GestureDetector(onTap: onTap, child: imageWidget),
    );
  }
}
