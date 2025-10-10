import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

class CachedJokeImage extends ConsumerStatefulWidget {
  static const int _minProcessedWidth = 50;
  static const int _maxProcessedWidth = 1024;
  const CachedJokeImage({
    super.key,
    required this.imageUrl,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.borderRadius,
    this.showLoadingIndicator = true,
    this.showErrorIcon = true,
    this.onFirstImagePaint,
  });

  final String? imageUrl;
  final double? width;
  final double? height;
  final BoxFit fit;
  final BorderRadius? borderRadius;
  final bool showLoadingIndicator;
  final bool showErrorIcon;
  final void Function(int? width)? onFirstImagePaint;

  @override
  ConsumerState<CachedJokeImage> createState() => _CachedJokeImageState();
}

class _CachedJokeImageState extends ConsumerState<CachedJokeImage> {
  bool _hasError = false;
  int _retryKey = 0;

  @override
  void didUpdateWidget(CachedJokeImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.imageUrl != oldWidget.imageUrl) {
      setState(() => _hasError = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Listen to connectivity changes to trigger retry when coming back online
    ref.listen(offlineToOnlineProvider, (previous, next) {
      if (_hasError) {
        setState(() => _retryKey++);
      }
    });

    return LayoutBuilder(
      builder: (context, constraints) {
        final effectiveWidth = _resolveEffectiveWidth(constraints.maxWidth);

        final imageService = ref.read(imageServiceProvider);
        final perf = ref.read(performanceServiceProvider);

        // Use ImageService for URL processing
        final processedUrl = imageService.getProcessedJokeImageUrl(
          widget.imageUrl,
          width: effectiveWidth,
        );
        if (processedUrl == null) {
          return _buildErrorWidget(context);
        }

        bool invokedFirstPaint = false;

        String? downloadTraceKey;
        Widget imageWidget = CachedNetworkImage(
          key: ValueKey('${widget.imageUrl}-$_retryKey'),
          imageUrl: processedUrl,
          width: widget.width,
          height: widget.height,
          fit: widget.fit,
          httpHeaders: ImageService.jokeImageHttpHeaders,
          // Use progressIndicatorBuilder instead of placeholder to avoid Octo assertion
          placeholder: null,
          progressIndicatorBuilder: (context, url, progress) {
            // When progress is first reported (<1.0), start download trace if not started
            if (progress.progress != null && progress.progress! < 1.0) {
              if (downloadTraceKey == null) {
                downloadTraceKey = url.hashCode.toRadixString(16);
                perf.startNamedTrace(
                  name: TraceName.imageDownload,
                  key: downloadTraceKey!,
                  attributes: {'url_hash': downloadTraceKey!},
                );
              }
            }
            return widget.showLoadingIndicator
                ? _buildLoadingWidget(context)
                : const SizedBox.shrink();
          },
          imageBuilder: (context, imageProvider) {
            // Called when the actual image data is ready; schedule callback after paint
            if (!invokedFirstPaint && widget.onFirstImagePaint != null) {
              invokedFirstPaint = true;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                widget.onFirstImagePaint?.call(effectiveWidth);
              });
            }
            // If a download trace is active for this URL, stop it now (download complete)
            if (downloadTraceKey != null) {
              perf.stopNamedTrace(
                name: TraceName.imageDownload,
                key: downloadTraceKey!,
              );
              downloadTraceKey = null;
            }
            // Clear error state on successful image load
            if (_hasError) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) {
                  setState(() => _hasError = false);
                }
              });
            }
            return Image(
              image: imageProvider,
              width: widget.width,
              height: widget.height,
              fit: widget.fit,
            );
          },
          errorWidget: widget.showErrorIcon
              ? (context, url, error) {
                  final analytics = ref.read(analyticsServiceProvider);
                  // Hash the url lightly to avoid logging full URLs
                  final urlHash = url.hashCode.toRadixString(16);
                  analytics.logErrorImageLoad(
                    imageType: null,
                    imageUrlHash: urlHash,
                    errorMessage: error.toString(),
                  );
                  // Drop any active download trace since it failed
                  if (downloadTraceKey != null) {
                    perf.dropNamedTrace(
                      name: TraceName.imageDownload,
                      key: downloadTraceKey!,
                    );
                    downloadTraceKey = null;
                  }
                  // Set error state if not already in error
                  if (!_hasError) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (mounted) {
                        setState(() => _hasError = true);
                      }
                    });
                  }
                  return _buildErrorWidget(context);
                }
              : (context, url, error) {
                  final analytics = ref.read(analyticsServiceProvider);
                  final urlHash = url.hashCode.toRadixString(16);
                  analytics.logErrorImageLoad(
                    imageType: null,
                    imageUrlHash: urlHash,
                    errorMessage: error.toString(),
                  );
                  if (downloadTraceKey != null) {
                    perf.dropNamedTrace(
                      name: TraceName.imageDownload,
                      key: downloadTraceKey!,
                    );
                    downloadTraceKey = null;
                  }
                  // Set error state if not already in error
                  if (!_hasError) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (mounted) {
                        setState(() => _hasError = true);
                      }
                    });
                  }
                  return const SizedBox.shrink();
                },
          fadeInDuration: const Duration(milliseconds: 300),
          fadeOutDuration: const Duration(milliseconds: 100),
        );

        // Log image info with size
        _logImageInfo(processedUrl);

        // Apply border radius if specified
        if (widget.borderRadius != null) {
          imageWidget = ClipRRect(
            borderRadius: widget.borderRadius!,
            child: imageWidget,
          );
        }

        return imageWidget;
      },
    );
  }

  int? _resolveEffectiveWidth(double constraintWidth) {
    int? targetWidth;

    final explicitWidth = widget.width;
    if (explicitWidth != null &&
        explicitWidth.isFinite &&
        explicitWidth >= CachedJokeImage._minProcessedWidth &&
        explicitWidth <= CachedJokeImage._maxProcessedWidth) {
      targetWidth = explicitWidth.round();
    } else if (constraintWidth.isFinite) {
      targetWidth = constraintWidth.round().clamp(
        CachedJokeImage._minProcessedWidth,
        CachedJokeImage._maxProcessedWidth,
      );
    } else {
      return null;
    }

    final roundedWidth = _roundUpToNearestHundred(targetWidth);
    final clampedWidth = roundedWidth.clamp(
      CachedJokeImage._minProcessedWidth,
      CachedJokeImage._maxProcessedWidth,
    );
    return clampedWidth;
  }

  int _roundUpToNearestHundred(int value) {
    return ((value + 99) ~/ 100) * 100;
  }

  void _logImageInfo(String url) async {
    if (!kDebugMode) return;

    try {
      final fileInfo = await DefaultCacheManager().getFileFromCache(url);
      if (fileInfo != null) {
        final sizeInBytes = await fileInfo.file.length();
        final sizeInKB = (sizeInBytes / 1024).toStringAsFixed(1);
        AppLogger.debug(
          "Loading image (CachedJokeImage): $url (${sizeInKB}KB)",
        );
      } else {
        AppLogger.debug(
          "Loading image (CachedJokeImage): $url (size unknown - not cached)",
        );
      }
    } catch (e) {
      AppLogger.debug("Loading image (CachedJokeImage): $url (size error: $e)");
    }
  }

  Widget _buildLoadingWidget(BuildContext context) {
    return Container(
      width: widget.width,
      height: widget.height,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: widget.borderRadius,
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
      width: widget.width,
      height: widget.height,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: widget.borderRadius,
        border: Border.all(
          color: Theme.of(context).colorScheme.outline,
          width: 1,
        ),
      ),
      child: widget.showErrorIcon
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
