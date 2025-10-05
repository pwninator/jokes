import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_startup_manager.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/startup/startup_task.dart';
import 'package:snickerdoodle/src/utils/device_utils.dart';

import '../../firebase_options.dart';

/// Timeout duration for best effort blocking tasks.
///
/// All best effort tasks share this timeout. If they don't complete within
/// this time, the app will proceed to render but tasks continue in background.
const Duration bestEffortTimeout = Duration(seconds: 4);

/// Critical blocking tasks that must complete before rendering the first frame.
///
/// These tasks have no timeout and will be retried on failure. The app cannot
/// function without these completing successfully.
///
/// Tasks in this list run in parallel with each other.
const List<StartupTask> criticalBlockingTasks = [
  StartupTask(id: 'firebase', execute: _initializeFirebase),
  StartupTask(id: 'shared_prefs', execute: _initializeSharedPreferences),
];

/// Best effort blocking tasks that block the first frame for up to [bestEffortTimeout].
///
/// These tasks run in parallel and share a single timeout. After the timeout,
/// the app will render but tasks continue in the background. Failures are
/// logged but don't prevent the app from starting.
///
/// Tasks in this list run in parallel with each other and with background tasks.
const List<StartupTask> bestEffortBlockingTasks = [
  StartupTask(id: 'remote_config', execute: _initializeRemoteConfig),
  StartupTask(id: 'auth', execute: _initializeAuth),
  StartupTask(id: 'analytics', execute: _initializeAnalytics),
  StartupTask(id: 'app_usage', execute: _initializeAppUsage),
];

/// Background tasks that run without blocking the first frame.
///
/// These tasks start at the same time as best effort tasks but don't block
/// the app from rendering. Failures are logged but don't affect the app.
///
/// Tasks in this list run in parallel with each other and with best effort tasks.
const List<StartupTask> backgroundTasks = [
  StartupTask(id: 'notifications', execute: _initializeNotifications),
];

// ============================================================================
// Task Implementations
// ============================================================================

/// Initialize Firebase and configure emulators in debug mode.
Future<void> _initializeFirebase(StartupContext context) async {
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  const useEmulatorInDebugMode = true;
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

/// Initialize SharedPreferences and register it as a provider override.
Future<void> _initializeSharedPreferences(StartupContext context) async {
  final sharedPrefs = await SharedPreferences.getInstance();
  context.addOverride(
    settingsServiceProvider.overrideWithValue(SettingsService(sharedPrefs)),
  );
}

/// Initialize Remote Config (fetch and activate).
Future<void> _initializeRemoteConfig(StartupContext context) async {
  try {
    final service = context.container.read(remoteConfigServiceProvider);
    await service.initialize();
  } catch (e, stack) {
    AppLogger.warn('Remote Config initialization failed: $e');
    final crashService = context.container.read(crashReportingServiceProvider);
    await crashService.recordFatal(e, stack);
  }
}

/// Initialize auth startup manager (background auth state sync).
Future<void> _initializeAuth(StartupContext context) async {
  try {
    final manager = context.container.read(authStartupManagerProvider);
    manager.start();
  } catch (e, stack) {
    AppLogger.warn('Auth startup initialization failed: $e');
    final crashService = context.container.read(crashReportingServiceProvider);
    await crashService.recordFatal(e, stack);
  }
}

/// Initialize analytics service.
Future<void> _initializeAnalytics(StartupContext context) async {
  try {
    final service = context.container.read(analyticsServiceProvider);
    await service.initialize();

    // User properties will be set automatically when auth state changes
    // via the analyticsUserTrackingProvider listener in the running app
  } catch (e, stack) {
    AppLogger.warn('Analytics initialization failed: $e');
    final crashService = context.container.read(crashReportingServiceProvider);
    await crashService.recordFatal(e, stack);
  }
}

/// Log app usage for analytics.
Future<void> _initializeAppUsage(StartupContext context) async {
  try {
    final service = context.container.read(appUsageServiceProvider);
    await service.logAppUsage();
  } catch (e, stack) {
    AppLogger.warn('App usage logging failed: $e');
    final crashService = context.container.read(crashReportingServiceProvider);
    await crashService.recordFatal(e, stack);
  }
}

/// Initialize notification service.
Future<void> _initializeNotifications(StartupContext context) async {
  final crashService = context.container.read(crashReportingServiceProvider);
  try {
    final notificationService = NotificationService();
    await notificationService.initialize(crashReportingService: crashService);
  } catch (e, stack) {
    AppLogger.warn('Notification service initialization failed: $e');
    await crashService.recordFatal(e, stack);
  }
}
