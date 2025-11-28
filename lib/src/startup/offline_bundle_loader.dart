import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Provider that loads the latest bundled Firestore data (if present in assets).
final offlineBundleLoaderProvider = Provider<OfflineBundleLoader>((ref) {
  return OfflineBundleLoader(
    firestore: FirebaseFirestore.instance,
    assetBundle: rootBundle,
  );
});

class OfflineBundleLoader {
  OfflineBundleLoader({
    required FirebaseFirestore firestore,
    required AssetBundle assetBundle,
  })  : _firestore = firestore,
        _assetBundle = assetBundle;

  final FirebaseFirestore _firestore;
  final AssetBundle _assetBundle;

  static const String _bundlePath = 'assets/data_bundles/firestore_bundle.txt';

  /// Load the most recent Firestore bundle from assets (if any).
  ///
  /// Returns true when a bundle was found and fully loaded, false otherwise.
  Future<bool> loadLatestBundle() async {
    try {
      final bytes = await _loadAssetBytes(_bundlePath);
      final task = _firestore.loadBundle(bytes);
      await task.stream.last;
      AppLogger.info('OFFLINE_BUNDLE: Loaded Firestore bundle from $_bundlePath');
      return true;
    } catch (e, stack) {
      AppLogger.error(
        'OFFLINE_BUNDLE: Failed to load bundle: $e',
        stackTrace: stack,
      );
      return false;
    }
  }

  Future<Uint8List> _loadAssetBytes(String assetPath) async {
    final data = await _assetBundle.load(assetPath);
    return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
  }
}
