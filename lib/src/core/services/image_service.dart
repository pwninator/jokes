import 'dart:io';
import 'dart:isolate';

import 'package:flutter/services.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class ImageService {
  // Watermark asset path
  static const String watermarkAssetPath =
      'assets/watermark/snickerdoodlejokes_watermark_01.png';

  // Cache configuration
  static const Duration defaultCacheDuration = Duration(days: 30);
  static const int maxCacheSize = 100 * 1024 * 1024; // 100MB

  static const String defaultImageFormat = 'webp';
  static const int defaultThumbnailQuality = 50;
  static const int defaultFullSizeQuality = 75;

  // Joke image specific constants
  static const int jokeImageQuality = 50;
  static const Map<String, String> jokeImageHttpHeaders = {
    'Accept': 'image/webp,image/avif,image/apng,image/*,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
  };

  /// Validates if the provided URL is a valid image URL
  bool isValidImageUrl(String? url) {
    if (url == null || url.trim().isEmpty) {
      return false;
    }

    try {
      final uri = Uri.parse(url);
      if (!uri.hasAbsolutePath) return false;

      // Check if it's a valid HTTP/HTTPS URL
      if (!uri.scheme.startsWith('http')) {
        return false;
      }

      // Check for common image extensions
      final path = uri.path.toLowerCase();
      final imageExtensions = [
        '.jpg',
        '.jpeg',
        '.png',
        '.gif',
        '.webp',
        '.bmp',
      ];

      return imageExtensions.any((ext) => path.endsWith(ext)) ||
          path.contains('image') || // For dynamic image URLs
          uri.queryParameters.containsKey(
            'format',
          ); // For URLs with format query
    } catch (e) {
      AppLogger.debug('Invalid image URL: $url, Error: $e');
      return false;
    }
  }

  /// Processes the image URL for optimization
  /// This can be extended to handle different image sizes, CDN optimization, etc.
  String processImageUrl(
    String url, {
    int? width,
    int? height,
    String? quality,
  }) {
    if (!isValidImageUrl(url)) {
      throw ArgumentError('Invalid image URL provided: $url');
    }

    // Optimize Cloudflare Images URLs
    if (url.contains('cdn-cgi/image/')) {
      return _optimizeCloudflareImageUrl(
        url,
        width: width,
        height: height,
        quality: quality,
      );
    }

    // For other URLs, return as-is for now
    // In the future, you could add logic for other CDNs
    return url;
  }

  /// Optimizes Cloudflare Images URLs with better compression and format
  String _optimizeCloudflareImageUrl(
    String url, {
    int? width,
    int? height,
    String? quality,
  }) {
    try {
      // Regex to match Cloudflare Images URL structure
      // Captures: (base_url)(parameters)(remaining_path)
      final regex = RegExp(r'^(.*?/cdn-cgi/image/)([^/]+)(/.*?)$');
      final match = regex.firstMatch(url);

      if (match == null) {
        return url; // Not a valid Cloudflare Images URL
      }

      final baseUrl = match.group(1)!;
      final existingParams = match.group(2)!;
      final remainingPath = match.group(3)!;

      // Parse existing parameters into a map
      final paramMap = <String, String>{};
      for (final param in existingParams.split(',')) {
        if (param.contains('=')) {
          final parts = param.split('=');
          if (parts.length == 2) {
            paramMap[parts[0]] = parts[1];
          }
        } else {
          // Handle parameters without values (like 'auto')
          paramMap[param] = '';
        }
      }

      // Apply optimizations
      paramMap['format'] = defaultImageFormat;
      paramMap['quality'] = quality ?? defaultFullSizeQuality.toString();

      // Set dimensions if provided
      if (width != null) {
        paramMap['width'] = width.toString();
      }
      if (height != null) {
        paramMap['height'] = height.toString();
      }

      // Rebuild parameters string
      final newParams = paramMap.entries
          .map((e) => e.value.isEmpty ? e.key : '${e.key}=${e.value}')
          .join(',');

      // Reconstruct the optimized URL
      final optimizedUrl = '$baseUrl$newParams$remainingPath';

      return optimizedUrl;
    } catch (e) {
      AppLogger.debug('Error optimizing Cloudflare URL: $e');
      return url; // Return original URL if optimization fails
    }
  }

  /// Gets a thumbnail version of the image URL
  String getThumbnailUrl(String url, {int size = 150}) {
    return processImageUrl(
      url,
      width: size,
      height: size,
      quality: defaultThumbnailQuality.toString(),
    );
  }

  /// Gets a full-size version of the image URL
  String getFullSizeUrl(String url) {
    return processImageUrl(url, quality: defaultFullSizeQuality.toString());
  }

  /// Clears the image cache
  Future<void> clearCache() async {
    try {
      await DefaultCacheManager().emptyCache();
      AppLogger.debug('Image cache cleared successfully');
    } catch (e) {
      AppLogger.debug('Error clearing image cache: $e');
    }
  }

  /// Returns the processed image URL for jokes, or null if invalid.
  ///
  /// [width] is an optional hint (in logical pixels) that will be forwarded to
  /// the CDN optimizer when available to improve resizing.
  String? getProcessedJokeImageUrl(String? imageUrl, {int? width}) {
    if (imageUrl == null || !isValidImageUrl(imageUrl)) {
      return null;
    }

    return processImageUrl(
      imageUrl,
      width: width,
      quality: jokeImageQuality.toString(),
    );
  }

  /// Precaches a single joke image with optimized configuration
  /// Uses disk caching for efficiency and works in both foreground and background
  /// Returns the processed URL if successful, null otherwise
  Future<String?> precacheJokeImage(String? imageUrl, {int? width}) async {
    final processedUrl = getProcessedJokeImageUrl(imageUrl, width: width);
    if (processedUrl == null) return null;

    try {
      // Download and cache to disk using DefaultCacheManager
      // CachedNetworkImage will find this in disk cache and load instantly
      await DefaultCacheManager().downloadFile(processedUrl);
      AppLogger.debug('Precached image: $processedUrl');
      return processedUrl;
    } catch (error, _) {
      // Silently handle preload errors - the actual image widget will show error state
      AppLogger.warn('Failed to precache image $imageUrl: $error');
      return null;
    }
  }

  /// Precaches both setup and punchline images for a joke
  /// Returns the processed URLs for both images
  Future<({String? setupUrl, String? punchlineUrl})> precacheJokeImages(
    Joke joke, {
    int? width,
  }) async {
    // Precache both images in parallel and get their processed URLs
    final results = await Future.wait([
      precacheJokeImage(joke.setupImageUrl, width: width),
      precacheJokeImage(joke.punchlineImageUrl, width: width),
    ]);

    return (setupUrl: results[0], punchlineUrl: results[1]);
  }

  /// Gets a cached file from URL as XFile for sharing
  /// Returns null if the file is not cached or there's an error
  Future<XFile?> getCachedFileFromUrl(String url) async {
    try {
      final imageFile = await DefaultCacheManager().getSingleFile(url);
      return XFile(imageFile.path);
    } catch (e) {
      AppLogger.debug('Error getting cached file from URL: $e');
      return null;
    }
  }

  /// Precaches images for multiple jokes
  Future<void> precacheMultipleJokeImages(
    List<Joke> jokes, {
    int? width,
  }) async {
    // Precache all jokes sequentially to avoid overwhelming the cache
    for (final joke in jokes) {
      try {
        await precacheJokeImages(joke, width: width);
      } catch (e) {
        AppLogger.warn('Failed to precache images for joke ${joke.id}: $e');
      }
    }
  }

  /// Adds a watermark overlay image to the provided file and returns a new XFile.
  /// If processing fails at any step, returns the original file to avoid blocking share.
  Future<XFile> addWatermarkToFile(
    XFile baseFile, {
    double targetWidthFraction = 0.35,
    int bottomPaddingPx = 16,
  }) async {
    try {
      final baseBytes = await baseFile.readAsBytes();
      final ByteData wmData = await rootBundle.load(watermarkAssetPath);
      final Uint8List wmBytes = wmData.buffer.asUint8List();

      // Offload CPU-heavy composition to a background isolate
      final Uint8List outBytes = await Isolate.run(() {
        return composeWatermarkSync(
          baseBytes,
          wmBytes,
          targetWidthFraction: targetWidthFraction,
          bottomPaddingPx: bottomPaddingPx,
        );
      });

      // Write to a temp file (use system temp to avoid platform channel dependency)
      final String tempDir = Directory.systemTemp.path;
      final String outPath = p.join(
        tempDir,
        'snickerdoodle_share_${DateTime.now().millisecondsSinceEpoch}_${p.basename(baseFile.path)}.png',
      );
      final outFile = File(outPath);
      await outFile.writeAsBytes(outBytes, flush: true);
      return XFile(outFile.path);
    } catch (e) {
      // Surface to crash reporting as non-fatal via caller-specific service when appropriate
      AppLogger.warn('addWatermarkToFile failed: $e');
      return baseFile;
    }
  }

  /// Convenience helper to watermark multiple files
  Future<List<XFile>> addWatermarkToFiles(List<XFile> files) async {
    final results = await Future.wait(
      files.map((file) => addWatermarkToFile(file)),
    );
    return results;
  }

  /// Stacks two images vertically and returns a new XFile.
  Future<XFile> stackImages(List<XFile> files) async {
    if (files.length != 2) {
      throw ArgumentError('Exactly two files must be provided to stackImages.');
    }
    final List<Uint8List> byteList = await Future.wait(
      [files[0].readAsBytes(), files[1].readAsBytes()],
    );

    final Uint8List outBytes =
        await Isolate.run(() => combineImagesSync(byteList));

    final String tempDir = Directory.systemTemp.path;
    final String outPath = p.join(
      tempDir,
      'snickerdoodle_share_stacked_${DateTime.now().millisecondsSinceEpoch}.png',
    );
    final outFile = File(outPath);
    await outFile.writeAsBytes(outBytes, flush: true);
    return XFile(outFile.path);
  }
}

/// Pure function to combine two images vertically
Uint8List combineImagesSync(List<Uint8List> byteList) {
  final img.Image? image1 = img.decodeImage(byteList[0]);
  final img.Image? image2 = img.decodeImage(byteList[1]);

  if (image1 == null || image2 == null) {
    throw StateError('Failed to decode one or both images');
  }

  final int newWidth = image1.width;
  final int newHeight = image1.height + image2.height;

  final img.Image combinedImage = img.Image(width: newWidth, height: newHeight);

  img.compositeImage(combinedImage, image1, dstX: 0, dstY: 0);
  img.compositeImage(combinedImage, image2, dstX: 0, dstY: image1.height);

  return Uint8List.fromList(img.encodePng(combinedImage));
}

/// Pure function: compose a watermark PNG over a base image and return PNG bytes.
/// Safe to call in an isolate. Throws if decoding fails.
Uint8List composeWatermarkSync(
  Uint8List baseBytes,
  Uint8List watermarkPngBytes, {
  double targetWidthFraction = 0.35,
  int bottomPaddingPx = 16,
}) {
  final img.Image? baseImage = img.decodeImage(baseBytes);
  if (baseImage == null) {
    throw StateError('Failed to decode base image');
  }
  final img.Image? wmImage = img.decodeImage(watermarkPngBytes);
  if (wmImage == null) {
    throw StateError('Failed to decode watermark image');
  }

  final int targetWidth = (baseImage.width * targetWidthFraction).round();
  final img.Image resizedWm = img.copyResize(
    wmImage,
    width: targetWidth.clamp(1, baseImage.width),
    interpolation: img.Interpolation.linear,
  );

  const int leftPaddingPx = 16;
  final int dstX = leftPaddingPx.clamp(0, baseImage.width - resizedWm.width);
  final int dstY = (baseImage.height - resizedWm.height - bottomPaddingPx)
      .clamp(0, baseImage.height - resizedWm.height)
      .toInt();

  final img.Image composed = img.compositeImage(
    baseImage.clone(),
    resizedWm,
    dstX: dstX,
    dstY: dstY,
  );

  return Uint8List.fromList(img.encodePng(composed));
}
