import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:snickerdoodle/firebase_options.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/startup/startup_orchestrator.dart';

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

  // Start the app with the startup orchestrator
  // All initialization (Firebase, SharedPreferences, etc.) is handled by startup tasks
  // This keeps main() fast and allows the loading screen to appear quickly
  runApp(const StartupOrchestrator(initialOverrides: []));
}
