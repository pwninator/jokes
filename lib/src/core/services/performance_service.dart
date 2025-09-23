import 'package:firebase_performance/firebase_performance.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Service to manage Firebase Performance custom traces.
///
/// Notes on cancellation semantics:
/// - "Dropping" a trace means we intentionally never call stop() so it
///   is not reported. We simply forget the reference.
/// - Only successful flows (first image shown) or empty-result flows should
///   call stop() so they appear in the dashboard.
/// Centralized names for Firebase Performance traces used in the app
enum TraceName {
  searchToFirstImage,
  imageDownload,
  carouselToVisible,
  cfCall,
  fsRead,
  fsWrite,
  fsWriteBatch,
}

extension TraceNameWire on TraceName {
  String get wireName {
    switch (this) {
      case TraceName.searchToFirstImage:
        return 'search_to_first_image';
      case TraceName.imageDownload:
        return 'image_download';
      case TraceName.carouselToVisible:
        return 'carousel_to_visible';
      case TraceName.cfCall:
        return 'cf_call';
      case TraceName.fsRead:
        return 'fs_read';
      case TraceName.fsWrite:
        return 'fs_write';
      case TraceName.fsWriteBatch:
        return 'fs_write_batch';
    }
  }
}

abstract class PerformanceService {
  /// Generic traces API (named/keyed) for reuse across features
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  });
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  });
  void stopNamedTrace({required TraceName name, String? key});
  void dropNamedTrace({required TraceName name, String? key});
}

class FirebasePerformanceService implements PerformanceService {
  final Map<String, Trace> _namedTraces = {};
  final Map<String, DateTime> _traceStartedAt = {};

  String _composeKey(TraceName name, String? key) =>
      key == null ? name.wireName : '${name.wireName}::$key';

  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {
    final composed = _composeKey(name, key);
    // Drop any previous in-flight trace with same name/key
    _namedTraces.remove(composed);
    final trace = FirebasePerformance.instance.newTrace(name.wireName);
    if (attributes != null && attributes.isNotEmpty) {
      attributes.forEach((k, v) => trace.putAttribute(k, v));
    }
    if (kDebugMode) {
      AppLogger.debug(
        'PERFORMANCE: starting trace ${name.wireName} key=${key ?? '(none)'} attrs=${attributes ?? {}}',
      );
    }
    trace.start();
    _namedTraces[composed] = trace;
    _traceStartedAt[composed] = DateTime.now();
  }

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {
    final composed = _composeKey(name, key);
    final trace = _namedTraces[composed];
    if (trace == null) return;
    attributes.forEach((k, v) => trace.putAttribute(k, v));
    if (kDebugMode) {
      AppLogger.debug(
        'PERFORMANCE: put attributes on ${name.wireName} key=${key ?? '(none)'} attrs=$attributes',
      );
    }
  }

  @override
  void stopNamedTrace({required TraceName name, String? key}) {
    final composed = _composeKey(name, key);
    final trace = _namedTraces.remove(composed);
    final startedAt = _traceStartedAt.remove(composed);
    if (trace != null) {
      final elapsedMs = startedAt == null
          ? 'unknown'
          : DateTime.now().difference(startedAt).inMilliseconds.toString();
      if (kDebugMode) {
        AppLogger.debug(
          'PERFORMANCE: stopping trace ${name.wireName} key=${key ?? '(none)'} duration=${elapsedMs}ms attrs=${trace.getAttributes()}',
        );
      }
      trace.stop();
    }
  }

  @override
  void dropNamedTrace({required TraceName name, String? key}) {
    final composed = _composeKey(name, key);
    if (kDebugMode && _namedTraces.containsKey(composed)) {
      AppLogger.debug(
        'PERFORMANCE: dropping trace ${name.wireName} key=${key ?? '(none)'}',
      );
    }
    _namedTraces.remove(composed);
    _traceStartedAt.remove(composed);
  }
}
