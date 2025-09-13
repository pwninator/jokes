import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:share_plus/share_plus.dart';
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
      debugPrint('Invalid image URL: $url, Error: $e');
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
      debugPrint('Error optimizing Cloudflare URL: $e');
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
      debugPrint('Image cache cleared successfully');
    } catch (e) {
      debugPrint('Error clearing image cache: $e');
    }
  }

  /// Returns the processed image URL for jokes, or null if invalid
  String? getProcessedJokeImageUrl(String? imageUrl) {
    if (imageUrl == null || !isValidImageUrl(imageUrl)) {
      return null;
    }

    return processImageUrl(imageUrl, quality: jokeImageQuality.toString());
  }

  /// Precaches a single joke image with optimized configuration
  /// Uses disk caching for efficiency and works in both foreground and background
  /// Returns the processed URL if successful, null otherwise
  Future<String?> precacheJokeImage(String? imageUrl) async {
    final processedUrl = getProcessedJokeImageUrl(imageUrl);
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
  Future<({String? setupUrl, String? punchlineUrl})> precacheJokeImages(
    Joke joke,
  ) async {
    // Precache both images in parallel and get their processed URLs
    final results = await Future.wait([
      precacheJokeImage(joke.setupImageUrl),
      precacheJokeImage(joke.punchlineImageUrl),
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
      debugPrint('Error getting cached file from URL: $e');
      return null;
    }
  }

  /// Precaches images for multiple jokes
  Future<void> precacheMultipleJokeImages(List<Joke> jokes) async {
    // Precache all jokes sequentially to avoid overwhelming the cache
    for (final joke in jokes) {
      try {
        await precacheJokeImages(joke);
      } catch (e) {
        debugPrint('Failed to precache images for joke ${joke.id}: $e');
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
      final baseImage = img.decodeImage(baseBytes);
      if (baseImage == null) {
        return baseFile;
      }

      // Load watermark asset
      final ByteData wmData = await rootBundle.load(watermarkAssetPath);
      final wmImage = img.decodeImage(wmData.buffer.asUint8List());
      if (wmImage == null) {
        return baseFile;
      }

      // Resize watermark to a fraction of base width
      final int targetWidth = (baseImage.width * targetWidthFraction).round();
      final img.Image resizedWm = img.copyResize(
        wmImage,
        width: targetWidth.clamp(1, baseImage.width),
        interpolation: img.Interpolation.linear,
      );

      // Compute placement: bottom-left with padding
      const int leftPaddingPx = 16;
      final int dstX = leftPaddingPx.clamp(
        0,
        baseImage.width - resizedWm.width,
      );
      final int dstY = (baseImage.height - resizedWm.height - bottomPaddingPx)
          .clamp(0, baseImage.height - resizedWm.height)
          .toInt();

      // Composite watermark onto base image with alpha blending
      final img.Image composed = img.compositeImage(
        baseImage.clone(),
        resizedWm,
        dstX: dstX,
        dstY: dstY,
      );

      // Encode to PNG
      final outBytes = img.encodePng(composed);

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
      debugPrint('addWatermarkToFile failed: $e');
      return baseFile;
    }
  }

  /// Convenience helper to watermark multiple files
  Future<List<XFile>> addWatermarkToFiles(List<XFile> files) async {
    final List<XFile> results = [];
    for (final file in files) {
      results.add(await addWatermarkToFile(file));
    }
    return results;
  }
}
