import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';

part 'notification_service.g.dart';

@Riverpod(keepAlive: true)
NotificationService notificationService(Ref ref) {
  final firebaseMessaging = ref.watch(firebaseMessagingProvider);
  return NotificationService(firebaseMessaging: firebaseMessaging);
}

class NotificationService {
  NotificationService({required FirebaseMessaging firebaseMessaging})
    : _firebaseMessaging = firebaseMessaging;

  final FirebaseMessaging _firebaseMessaging;

  bool _isInitialized = false;

  // Global navigation key for notifications
  static final GlobalKey<NavigatorState> navigatorKey =
      GlobalKey<NavigatorState>();

  /// Initialize notification service (non-blocking)
  Future<void> initialize() async {
    if (_isInitialized) return;

    // Start background initialization (non-blocking)
    _initializeBackgroundServices();

    _isInitialized = true;
  }

  /// Initialize background services (non-blocking)
  /// These can happen after UI loads without affecting user experience
  void _initializeBackgroundServices() {
    // Run in background without awaiting
    // Note: Permission request only happens when user subscribes
    _initializeFCMListeners().catchError((e, stack) {
      AppLogger.error(
        'Background FCM initialization failed: $e',
        stackTrace: stack,
      );
    });
  }

  /// Request FCM permissions when user subscribes (blocking - user needs to respond)
  Future<bool> requestNotificationPermissions() async {
    try {
      final settings = await _firebaseMessaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      final granted =
          settings.authorizationStatus == AuthorizationStatus.authorized;
      AppLogger.debug('FCM permissions requested - granted: $granted');
      return granted;
    } catch (e, stack) {
      AppLogger.error(
        'Failed to request FCM permissions: $e',
        stackTrace: stack,
      );
      return false;
    }
  }

  /// Initialize FCM listeners and token (background)
  Future<void> _initializeFCMListeners() async {
    try {
      // Get FCM token for debugging
      final token = await _firebaseMessaging.getToken();
      AppLogger.debug('FCM Token: $token');

      // Handle foreground messages
      FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

      AppLogger.debug('FCM listeners initialized');
    } catch (e, stack) {
      AppLogger.error(
        'Failed to initialize FCM listeners: $e',
        stackTrace: stack,
      );
    }
  }

  /// Handle foreground FCM messages
  Future<void> _handleForegroundMessage(RemoteMessage message) async {
    AppLogger.debug('Received foreground FCM message: ${message.messageId}');
    try {
      await _processJokeNotification(message);
    } catch (e, stack) {
      AppLogger.error(
        'Failed to process joke notification: $e',
        stackTrace: stack,
        keys: {'message_id': message.messageId ?? 'unknown'},
      );
    }
  }

  /// Process joke notification - pre-cache images for faster app loading
  /// FCM handles displaying the notification with images automatically
  Future<void> _processJokeNotification(RemoteMessage message) async {
    try {
      final jokeData = message.data;
      final jokeId = jokeData['joke_id'];

      AppLogger.debug('Processing joke notification for joke: $jokeId');

      // Pre-cache images in parallel so they load instantly when user opens the app
      final List<Future<void>> cachingFutures = [];

      if (jokeData.containsKey('setup_image_url')) {
        cachingFutures.add(_cacheImage(jokeData['setup_image_url']));
      }
      if (jokeData.containsKey('punchline_image_url')) {
        cachingFutures.add(_cacheImage(jokeData['punchline_image_url']));
      }

      // Non-blocking: fire-and-forget with timeout and concurrency cap
      // Cap to at most 2 concurrent caching ops here (we only have up to 2 URLs)
      for (final f in cachingFutures) {
        unawaited(_withTimeout(f, const Duration(seconds: 8)));
      }

      AppLogger.debug('Images pre-cached for joke: $jokeId');
    } catch (e, stack) {
      AppLogger.error(
        'Error processing joke notification: $e',
        stackTrace: stack,
        keys: {
          'message_id': message.messageId ?? 'unknown',
          'joke_id': message.data['joke_id'] ?? 'unknown',
        },
      );
    }
  }

  /// Cache image for faster loading
  Future<void> _cacheImage(String imageUrl) async {
    try {
      final imageService = ImageService();
      await imageService.precacheJokeImage(imageUrl);
    } catch (e, stack) {
      AppLogger.error(
        'Failed to cache image $imageUrl: $e',
        stackTrace: stack,
        keys: {'image_url': imageUrl},
      );
    }
  }

  // Helper to wrap a future with a timeout without throwing up-stack
  Future<void> _withTimeout(Future<void> future, Duration timeout) async {
    try {
      await future.timeout(timeout);
    } catch (_) {}
  }

  /// Get FCM token for server-side targeting (if needed)
  Future<String?> getFCMToken() async {
    return await FirebaseMessaging.instance.getToken();
  }
}

/// Background message handler - must be top-level function
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  AppLogger.debug('Handling background FCM message: ${message.messageId}');

  try {
    // Initialize Firebase if not already done
    await Firebase.initializeApp();

    // Process the joke notification
    final notificationService = NotificationService(
      firebaseMessaging: FirebaseMessaging.instance,
    );
    await notificationService._processJokeNotification(message);
  } catch (e, stack) {
    AppLogger.warn('Background message handler failed: $e');
    // Report to Crashlytics directly since we're in a separate isolate
    try {
      final crashReportingService = FirebaseCrashReportingService(
        crashlytics: FirebaseCrashlytics.instance,
      );
      await crashReportingService.recordNonFatal(
        e,
        stackTrace: stack,
        keys: {
          'message_id': message.messageId ?? 'unknown',
          'context': 'background_message_handler',
        },
      );
    } catch (_) {
      // Ignore errors from crash reporting itself
    }
  }
}
