import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
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

/// Lazy-loads the bundled image manifest (list of asset tails).
/// Returns an empty set if the manifest is missing or invalid.
final imageAssetManifestProvider = FutureProvider<Set<String>>((ref) async {
  try {
    final jsonString = await rootBundle.loadString(
      ImageService.assetImageManifestPath,
    );
    final decoded = jsonDecode(jsonString);
    if (decoded is List) {
      final manifest = decoded.whereType<String>().toSet();
      AppLogger.info('Loaded image asset manifest: ${manifest.length} images');
      return manifest;
    }
  } catch (_) {
    // Swallow errors; fallback to empty set.
  }
  return <String>{};
});
