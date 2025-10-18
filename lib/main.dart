import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_performance/firebase_performance.dart';
import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/firebase_options.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/startup/startup_orchestrator.dart';
import 'package:snickerdoodle/src/startup/startup_tasks.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  // Set up FCM background message handler before runApp
  // (This must be done here, not in a startup task)
  FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

  if (kReleaseMode) {
    FlutterError.onError = (FlutterErrorDetails details) {
      try {
        FirebaseCrashlytics.instance.recordFlutterError(details);
      } catch (e) {
        debugPrint('Failed to report Flutter error: $e');
      }
    };

    PlatformDispatcher.instance.onError = (error, stack) {
      try {
        FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      } catch (e) {
        debugPrint('Failed to report fatal error: $e');
      }
      return true;
    };
  }

  // Provide Firebase instances up-front so performance tracing is available
  // from the very beginning of startup orchestration.
  runApp(
    ProviderScope(
      overrides: [
        firebaseFirestoreProvider.overrideWithValue(FirebaseFirestore.instance),
        firebaseFunctionsProvider.overrideWithValue(FirebaseFunctions.instance),
        firebaseAuthProvider.overrideWithValue(FirebaseAuth.instance),
        firebaseAnalyticsProvider.overrideWithValue(FirebaseAnalytics.instance),
        firebasePerformanceProvider.overrideWithValue(
          FirebasePerformance.instance,
        ),
        firebaseRemoteConfigProvider.overrideWithValue(
          FirebaseRemoteConfig.instance,
        ),
        firebaseMessagingProvider.overrideWithValue(FirebaseMessaging.instance),
        firebaseCrashlyticsProvider.overrideWithValue(
          FirebaseCrashlytics.instance,
        ),
      ],
      child: StartupOrchestrator(
        criticalTasks: criticalBlockingTasks,
        bestEffortTasks: bestEffortBlockingTasks,
        backgroundTasks: backgroundTasks,
      ),
    ),
  );
}
