import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_startup_manager.dart';
import 'package:snickerdoodle/src/startup/startup_task.dart';
import 'package:snickerdoodle/src/utils/device_utils.dart';

/// Timeout duration for best effort blocking tasks.
///
/// All best effort tasks share this timeout. If they don't complete within
/// this time, the app will proceed to render but tasks continue in background.
const Duration bestEffortTimeout = Duration(seconds: 4);

const useEmulatorInDebugMode = true;

/// Critical blocking tasks that must complete before rendering the first frame.
///
/// These tasks have no timeout and will be retried on failure. The app cannot
/// function without these completing successfully.
///
/// Tasks in this list run in parallel with each other.
const List<StartupTask> criticalBlockingTasks = [
  StartupTask(
    id: 'emulators',
    execute: _initializeEmulators,
    traceName: TraceName.startupTaskEmulators,
  ),
  StartupTask(
    id: 'shared_prefs',
    execute: _initializeSharedPreferences,
    traceName: TraceName.startupTaskSharedPrefs,
  ),
  StartupTask(
    id: 'drift_db',
    execute: _initializeDrift,
    traceName: TraceName.startupTaskDrift,
  ),
];

/// Best effort blocking tasks that block the first frame for up to [bestEffortTimeout].
///
/// These tasks run in parallel and share a single timeout. After the timeout,
/// the app will render but tasks continue in the background. Failures are
/// logged but don't prevent the app from starting.
///
/// Tasks in this list run in parallel with each other and with background tasks.
const List<StartupTask> bestEffortBlockingTasks = [
  StartupTask(
    id: 'remote_config',
    execute: _initializeRemoteConfig,
    traceName: TraceName.startupTaskRemoteConfig,
  ),
  StartupTask(
    id: 'auth',
    execute: _initializeAuth,
    traceName: TraceName.startupTaskAuth,
  ),
  StartupTask(
    id: 'analytics',
    execute: _initializeAnalytics,
    traceName: TraceName.startupTaskAnalytics,
  ),
  StartupTask(
    id: 'app_usage',
    execute: _initializeAppUsage,
    traceName: TraceName.startupTaskAppUsage,
  ),
];

/// Background tasks that run without blocking the first frame.
///
/// These tasks start at the same time as best effort tasks but don't block
/// the app from rendering. Failures are logged but don't affect the app.
///
/// Tasks in this list run in parallel with each other and with best effort tasks.
const List<StartupTask> backgroundTasks = [
  StartupTask(
    id: 'notifications',
    execute: _initializeNotifications,
    traceName: TraceName.startupTaskNotifications,
  ),
];

// ============================================================================
// Task Implementations
// ============================================================================

/// Initialize Firebase and configure emulators in debug mode.
Future<void> _initializeEmulators(WidgetRef ref) async {
  // ignore: dead_code
  if (kDebugMode && useEmulatorInDebugMode) {
    final isPhysicalDevice = await DeviceUtils.isPhysicalDevice;
    if (!isPhysicalDevice) {
      AppLogger.debug("DEBUG: Using Firebase emulator");
      try {
        FirebaseFirestore.instance.useFirestoreEmulator('localhost', 8080);
        FirebaseFunctions.instance.useFunctionsEmulator('localhost', 5001);
        await FirebaseAuth.instance.useAuthEmulator('localhost', 9099);
      } catch (e) {
        AppLogger.warn('Firebase emulator connection error: $e');
      }
    }
  }
}

/// Initialize SharedPreferences
Future<void> _initializeSharedPreferences(WidgetRef ref) async {
  try {
    await ref.read(sharedPreferencesProvider.future);
  } catch (e, stack) {
    AppLogger.fatal(
      'SharedPreferences initialization failed: $e',
      stackTrace: stack,
    );
    rethrow; // Critical task should fail fast
  }
}

/// Initialize Drift database and warm up service
Future<void> _initializeDrift(WidgetRef ref) async {
  try {
    // Resolving the provider initializes DB and warms it up
    await ref.read(jokeInteractionsServiceProvider.future);
  } catch (e, stack) {
    AppLogger.fatal(
      'Drift database initialization failed: $e',
      stackTrace: stack,
    );
    rethrow; // Critical task should fail fast
  }
}

/// Initialize Remote Config (fetch and activate).
Future<void> _initializeRemoteConfig(WidgetRef ref) async {
  try {
    final service = ref.read(remoteConfigServiceProvider);
    await service.initialize();
  } catch (e, stack) {
    AppLogger.fatal(
      'Remote Config initialization failed: $e',
      stackTrace: stack,
    );
  }
}

/// Initialize auth startup manager (background auth state sync).
Future<void> _initializeAuth(WidgetRef ref) async {
  try {
    final manager = ref.read(authStartupManagerProvider);
    manager.start();
  } catch (e, stack) {
    AppLogger.fatal(
      'Auth startup initialization failed: $e',
      stackTrace: stack,
    );
  }
}

/// Initialize analytics service.
Future<void> _initializeAnalytics(WidgetRef ref) async {
  try {
    final service = ref.read(analyticsServiceProvider);
    await service.initialize();

    // User properties will be set automatically when auth state changes
    // via the analyticsUserTrackingProvider listener in the running app
  } catch (e, stack) {
    AppLogger.fatal('Analytics initialization failed: $e', stackTrace: stack);
  }
}

/// Log app usage for analytics.
Future<void> _initializeAppUsage(WidgetRef ref) async {
  try {
    final service = ref.read(appUsageServiceProvider);

    // Fire and forget
    unawaited(
      service.logAppUsage().catchError((Object e, StackTrace stack) {
        AppLogger.fatal('App usage logging failed: $e', stackTrace: stack);
      }),
    );
  } catch (e, stack) {
    AppLogger.fatal('App usage logging failed: $e', stackTrace: stack);
  }
}

/// Initialize notification service.
Future<void> _initializeNotifications(WidgetRef ref) async {
  try {
    final notificationService = NotificationService();
    await notificationService.initialize();
  } catch (e, stack) {
    AppLogger.fatal(
      'Notification service initialization failed: $e',
      stackTrace: stack,
    );
  }
}
