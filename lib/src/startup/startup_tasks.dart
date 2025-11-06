import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/admob_service.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_reactions_migration_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_startup_manager.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
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
    id: 'migrate_reactions',
    execute: _migrateReactionsToDrift,
    traceName: TraceName.startupTaskMigrateReactions,
  ),
  StartupTask(
    id: 'sync_feed_jokes',
    execute: _syncFeedJokes,
    traceName: TraceName.startupTaskSyncFeedJokes,
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
  StartupTask(
    id: 'admob',
    execute: _initializeAdMob,
    traceName: TraceName.startupTaskAdMob,
  ),
];

// ============================================================================
// Task Implementations
// ============================================================================

/// Initialize Firebase and configure emulators in debug mode.
Future<List<Override>> _initializeEmulators(StartupReader read) async {
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
  return const [];
}

/// Initialize SharedPreferences
Future<List<Override>> _initializeSharedPreferences(StartupReader read) async {
  try {
    final prefs = await SharedPreferences.getInstance();
    return [sharedPreferencesProvider.overrideWithValue(prefs)];
  } catch (e, stack) {
    AppLogger.fatal(
      'SharedPreferences initialization failed: $e',
      stackTrace: stack,
    );
    rethrow; // Critical task should fail fast
  }
}

/// Initialize Drift database and warm up service
Future<List<Override>> _initializeDrift(StartupReader read) async {
  try {
    // Resolving the provider initializes DB and warms it up
    await AppDatabase.initialize();
    final db = AppDatabase.instance;
    return [appDatabaseProvider.overrideWithValue(db)];
  } catch (e, stack) {
    AppLogger.fatal(
      'Drift database initialization failed: $e',
      stackTrace: stack,
    );
    rethrow; // Critical task should fail fast
  }
}

/// Initialize Remote Config (fetch and activate).
Future<List<Override>> _initializeRemoteConfig(StartupReader read) async {
  try {
    final service = read(remoteConfigServiceProvider);
    await service.initialize();
  } catch (e, stack) {
    AppLogger.fatal(
      'Remote Config initialization failed: $e',
      stackTrace: stack,
    );
  }
  return const [];
}

/// Initialize auth startup manager (background auth state sync).
Future<List<Override>> _initializeAuth(StartupReader read) async {
  try {
    final manager = read(authStartupManagerProvider);
    manager.start();
  } catch (e, stack) {
    AppLogger.fatal(
      'Auth startup initialization failed: $e',
      stackTrace: stack,
    );
  }
  return const [];
}

/// Initialize analytics service.
Future<List<Override>> _initializeAnalytics(StartupReader read) async {
  try {
    final service = read(analyticsServiceProvider);
    await service.initialize();

    // User properties will be set automatically when auth state changes
    // via the analyticsUserTrackingProvider listener in the running app
  } catch (e, stack) {
    AppLogger.fatal('Analytics initialization failed: $e', stackTrace: stack);
  }
  return const [];
}

/// Migrate legacy SharedPreferences reactions to Drift database if needed.
Future<List<Override>> _migrateReactionsToDrift(StartupReader read) async {
  try {
    final service = read(jokeReactionsMigrationServiceProvider);
    await service.migrateIfNeeded();
  } catch (e, stack) {
    AppLogger.fatal('Reactions migration task failed: $e', stackTrace: stack);
  }
  return const [];
}

/// Initialize notification service.
Future<List<Override>> _initializeNotifications(StartupReader read) async {
  try {
    final notificationService = read(notificationServiceProvider);
    await notificationService.initialize();
  } catch (e, stack) {
    AppLogger.fatal(
      'Notification service initialization failed: $e',
      stackTrace: stack,
    );
  }
  return const [];
}

/// Initialize AdMob with Families-compliant settings.
Future<List<Override>> _initializeAdMob(StartupReader read) async {
  try {
    final admob = read(adMobServiceProvider);
    await admob.initialize();
  } catch (e, stack) {
    AppLogger.fatal('AdMob initialization failed: $e', stackTrace: stack);
  }
  return const [];
}

/// Sync feed jokes to local database.
Future<List<Override>> _syncFeedJokes(StartupReader read) async {
  try {
    final repository = read(jokeRepositoryProvider);
    final interactionsRepository = read(jokeInteractionsRepositoryProvider);

    JokeListPageCursor? cursor;
    int feedIndex = 0;

    while (true) {
      final page = await repository.readFeedJokes(cursor: cursor);

      if (page.jokes != null && page.jokes!.isNotEmpty) {
        final jokes = page.jokes!
            .map((joke) => (joke: joke, feedIndex: feedIndex++))
            .toList();

        await interactionsRepository.syncFeedJokes(jokes: jokes);
      }
      AppLogger.info(
        'STARTUP_TASKS: SYNC_FEED_JOKES: Synced feed joke: ${page.jokes?.length} jokes, feedIndex: $feedIndex',
      );

      if (!page.hasMore ||
          page.cursor == null ||
          page.cursor?.docId == cursor?.docId) {
        AppLogger.info(
          'STARTUP_TASKS: SYNC_FEED_JOKES: No more feed jokes to sync: hasMore: ${page.hasMore}, prev cursor: ${cursor?.docId}, new cursor: ${page.cursor?.docId}',
        );
        break;
      }

      cursor = page.cursor;
    }
  } catch (e, stack) {
    AppLogger.fatal(
      'STARTUP_TASKS: SYNC_FEED_JOKES: Feed jokes sync task failed: $e',
      stackTrace: stack,
    );
  }
  return const [];
}
