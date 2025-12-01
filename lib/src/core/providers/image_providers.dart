import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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

/// Loads and parses the bundled image manifest using the provided asset bundle.
Future<Set<String>> loadImageAssetManifest(AssetBundle bundle) async {
  final jsonString = await bundle.loadString(
    ImageService.assetImageManifestPath,
  );
  final decoded = jsonDecode(jsonString);
  if (decoded is List) {
    final manifest = decoded.whereType<String>().toSet();
    AppLogger.info('Loaded image asset manifest: ${manifest.length} images');
    return manifest;
  }
  throw StateError('Invalid image asset manifest format');
}

/// Lazy-loads the bundled image manifest (list of asset tails).
/// MUST be overridden in production and tests.
final imageAssetManifestProvider = FutureProvider<Set<String>>((ref) async {
  throw StateError(
    'imageAssetManifestProvider must be overridden. Override with a manifest loader '
    'in production and provide test doubles in widget/unit tests.',
  );
});
