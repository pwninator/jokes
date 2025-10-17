import 'package:firebase_performance/firebase_performance.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';

part 'performance_service.g.dart';

/// Provider for PerformanceService (Firebase Performance)
@Riverpod(keepAlive: true)
PerformanceService performanceService(Ref ref) {
  final performance = ref.watch(firebasePerformanceProvider);
  return FirebasePerformanceService(performance: performance);
}

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
  sharePreparation,
  driftSetInteraction,
  driftGetInteraction,
  driftGetInteractionCount,
  driftGetSavedJokeInteractions,
  driftGetAllJokeInteractions,
  startupOverallBlocking,
  startupOverallBackground,
  startupTaskEmulators,
  startupTaskSharedPrefs,
  startupTaskRemoteConfig,
  startupTaskAuth,
  startupTaskAnalytics,
  startupTaskAppUsage,
  startupTaskDrift,
  startupTaskNotifications,
  startupTaskMigrateReactions,
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
      case TraceName.sharePreparation:
        return 'share_preparation';
      case TraceName.driftSetInteraction:
        return 'drift_set_interaction';
      case TraceName.driftGetInteraction:
        return 'drift_get_interaction';
      case TraceName.driftGetInteractionCount:
        return 'drift_get_interaction_count';
      case TraceName.driftGetSavedJokeInteractions:
        return 'drift_get_saved_joke_interactions';
      case TraceName.driftGetAllJokeInteractions:
        return 'drift_get_all_joke_interactions';
      case TraceName.startupOverallBlocking:
        return 'startup_overall_blocking';
      case TraceName.startupOverallBackground:
        return 'startup_overall_background';
      case TraceName.startupTaskEmulators:
        return 'startup_task_emulators';
      case TraceName.startupTaskSharedPrefs:
        return 'startup_task_shared_prefs';
      case TraceName.startupTaskRemoteConfig:
        return 'startup_task_remote_config';
      case TraceName.startupTaskAuth:
        return 'startup_task_auth';
      case TraceName.startupTaskAnalytics:
        return 'startup_task_analytics';
      case TraceName.startupTaskAppUsage:
        return 'startup_task_app_usage';
      case TraceName.startupTaskNotifications:
        return 'startup_task_notifications';
      case TraceName.startupTaskDrift:
        return 'startup_task_drift';
      case TraceName.startupTaskMigrateReactions:
        return 'startup_task_migrate_reactions';
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
  FirebasePerformanceService({required FirebasePerformance performance})
    : _performance = performance;

  final Map<String, Trace> _namedTraces = {};
  final Map<String, DateTime> _traceStartedAt = {};
  final FirebasePerformance _performance;

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
    final trace = _performance.newTrace(name.wireName);
    if (attributes != null && attributes.isNotEmpty) {
      attributes.forEach((k, v) => trace.putAttribute(k, v));
    }
    AppLogger.debug(
      'PERFORMANCE: starting trace ${name.wireName} key=${key ?? '(none)'} attrs=${attributes ?? {}}',
    );
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
    AppLogger.debug(
      'PERFORMANCE: put attributes on ${name.wireName} key=${key ?? '(none)'} attrs=$attributes',
    );
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
      // trace.getAttributes() doesn't work on web
      final attrStr = kIsWeb ? 'N/A' : trace.getAttributes().toString();
      AppLogger.debug(
        'PERFORMANCE: stopping trace ${name.wireName} key=${key ?? '(none)'} duration=${elapsedMs}ms attrs=$attrStr',
      );
      trace.stop();
    }
  }

  @override
  void dropNamedTrace({required TraceName name, String? key}) {
    final composed = _composeKey(name, key);
    if (_namedTraces.containsKey(composed)) {
      AppLogger.debug(
        'PERFORMANCE: dropping trace ${name.wireName} key=${key ?? '(none)'}',
      );
    }
    _namedTraces.remove(composed);
    _traceStartedAt.remove(composed);
  }
}
