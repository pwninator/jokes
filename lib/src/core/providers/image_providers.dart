import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';

/// Provider for the ImageService
/// This enables dependency injection of the image service throughout the app
final imageServiceProvider = Provider<ImageService>((ref) {
  return ImageService();
});

/// Provider for image cache configuration
/// This can be used to access cache settings throughout the app
final imageCacheConfigProvider = Provider<Map<String, dynamic>>((ref) {
  return {
    'cacheDuration': ImageService.defaultCacheDuration,
    'maxCacheSize': ImageService.maxCacheSize,
  };
}); 