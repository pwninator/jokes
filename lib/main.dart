import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/app.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/utils/device_utils.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase (required before any UI that uses auth)
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  // Set up FCM background message handler
  FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

  // Initialize notification service
  final notificationService = NotificationService();
  await notificationService.initialize();

  final useEmulatorInDebugMode = true;
  // ignore: dead_code
  if (kDebugMode && useEmulatorInDebugMode) {
    bool isPhysicalDevice = await DeviceUtils.isPhysicalDevice;
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

  if (kReleaseMode) {
    FlutterError.onError = (FlutterErrorDetails details) async {
      // Forward Flutter framework errors to Crashlytics in release builds only
      final container = ProviderContainer();
      final crashService = container.read(crashReportingServiceProvider);
      await crashService.recordFlutterError(details);
    };

    PlatformDispatcher.instance.onError = (error, stack) {
      // Uncaught async errors
      final container = ProviderContainer();
      final crashService = container.read(crashReportingServiceProvider);
      crashService.recordFatal(error, stack);
      return true;
    };
  }

  runApp(const ProviderScope(child: App()));
}
