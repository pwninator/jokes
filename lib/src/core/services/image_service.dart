import 'package:flutter/foundation.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';

class ImageService {
  // Cache configuration
  static const Duration defaultCacheDuration = Duration(days: 30);
  static const int maxCacheSize = 100 * 1024 * 1024; // 100MB

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
      paramMap['format'] = 'webp'; // Force WebP instead of auto
      paramMap['quality'] = quality ?? '85'; // Good balance of quality/size

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

      debugPrint('Cloudflare URL optimized: $existingParams -> $newParams');
      return optimizedUrl;
    } catch (e) {
      debugPrint('Error optimizing Cloudflare URL: $e');
      return url; // Return original URL if optimization fails
    }
  }

  /// Gets a thumbnail version of the image URL
  String getThumbnailUrl(String url, {int size = 150}) {
    return processImageUrl(url, width: size, height: size, quality: '75');
  }

  /// Gets a full-size version of the image URL
  String getFullSizeUrl(String url) {
    return processImageUrl(url, quality: '85');
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
}
