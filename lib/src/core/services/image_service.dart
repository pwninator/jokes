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

    // For now, return the URL as-is
    // In the future, you could add logic to:
    // - Add query parameters for resizing
    // - Transform URLs for CDN optimization
    // - Add cache-busting parameters if needed
    return url;
  }

  /// Gets a thumbnail version of the image URL
  String getThumbnailUrl(String url, {int size = 150}) {
    return processImageUrl(url, width: size, height: size);
  }

  /// Gets a full-size version of the image URL
  String getFullSizeUrl(String url) {
    return processImageUrl(url);
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
