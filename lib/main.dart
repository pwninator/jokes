import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/startup/startup_orchestrator.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Set up FCM background message handler before runApp
  // (This must be done here, not in a startup task)
  FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

  // Set up global error handlers for crash reporting in release mode
  // These handlers are active immediately but gracefully handle pre-Firebase errors
  if (kReleaseMode) {
    FlutterError.onError = (FlutterErrorDetails details) {
      _reportError(
        errorType: 'Flutter error',
        fallbackMessage: details.exceptionAsString(),
        crashlyticsReporter: () =>
            FirebaseCrashlytics.instance.recordFlutterError(details),
      );
    };

    PlatformDispatcher.instance.onError = (error, stack) {
      _reportError(
        errorType: 'Fatal error',
        fallbackMessage: error.toString(),
        crashlyticsReporter: () =>
            FirebaseCrashlytics.instance.recordError(error, stack, fatal: true),
      );
      return true;
    };
  }

  // Start the app with the startup orchestrator
  // All initialization (Firebase, SharedPreferences, etc.) is handled by startup tasks
  // This keeps main() fast and allows the loading screen to appear quickly
  runApp(const StartupOrchestrator(initialOverrides: []));
}

/// Helper function to safely report errors to Crashlytics with fallback logging
void _reportError({
  required String errorType,
  required String fallbackMessage,
  required void Function() crashlyticsReporter,
}) {
  try {
    // Check if Firebase has been initialized by startup tasks
    if (Firebase.apps.isNotEmpty &&
        FirebaseCrashlytics.instance.isCrashlyticsCollectionEnabled) {
      // Fire-and-forget: Crashlytics methods are async but we don't await them
      // This is correct - Crashlytics queues errors internally and uploads later
      crashlyticsReporter();
    } else {
      // Firebase not ready yet, log to console as fallback
      debugPrint('$errorType (pre-Firebase): $fallbackMessage');
    }
  } catch (e) {
    // Crashlytics failed for some reason, ensure we don't crash the error handler
    debugPrint('Failed to report $errorType: $e');
  }
}
