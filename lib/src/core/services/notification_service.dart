import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  bool _isInitialized = false;
  AnalyticsService? _analyticsService;

  // Global navigation key for notifications
  static final GlobalKey<NavigatorState> navigatorKey =
      GlobalKey<NavigatorState>();

  /// Set the analytics service (called after provider container is available)
  void setAnalyticsService(AnalyticsService analyticsService) {
    _analyticsService = analyticsService;

    // Now that analytics is ready, check for initial message from terminated state
    _checkInitialMessage();
  }

  /// Initialize notification service (non-blocking)
  /// Now ultra-fast since everything is background/on-demand
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

    _initializeFCMListeners().catchError((e) {
      debugPrint('Background FCM initialization failed: $e');
    });
  }

  /// Request FCM permissions when user subscribes (blocking - user needs to respond)
  Future<bool> requestNotificationPermissions() async {
    try {
      final settings = await FirebaseMessaging.instance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      final granted =
          settings.authorizationStatus == AuthorizationStatus.authorized;
      debugPrint('FCM permissions requested - granted: $granted');
      return granted;
    } catch (e) {
      debugPrint('Failed to request FCM permissions: $e');
      return false;
    }
  }

  /// Check if app was launched from notification (terminated state)
  Future<void> _checkInitialMessage() async {
    try {
      final initialMessage = await FirebaseMessaging.instance
          .getInitialMessage();
      if (initialMessage != null) {
        debugPrint(
          'App launched from notification: ${initialMessage.messageId}',
        );
        await _handleMessageOpenedApp(initialMessage);
      }
    } catch (e) {
      debugPrint('Failed to check initial message: $e');
    }
  }

  /// Initialize FCM listeners and token (background)
  Future<void> _initializeFCMListeners() async {
    try {
      // Get FCM token for debugging
      final token = await FirebaseMessaging.instance.getToken();
      debugPrint('FCM Token: $token');

      // Handle foreground messages
      FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

      // Handle notification taps when app is in background/terminated
      FirebaseMessaging.onMessageOpenedApp.listen(_handleMessageOpenedApp);

      debugPrint('FCM listeners initialized');
    } catch (e) {
      debugPrint('Failed to initialize FCM listeners: $e');
    }
  }

  /// Handle foreground FCM messages
  Future<void> _handleForegroundMessage(RemoteMessage message) async {
    debugPrint('Received foreground FCM message: ${message.messageId}');
    await _processJokeNotification(message);
  }

  /// Handle FCM message when app is opened from notification
  Future<void> _handleMessageOpenedApp(RemoteMessage message) async {
    debugPrint('App opened from FCM notification: ${message.messageId}');

    // Track analytics for notification tap
    if (_analyticsService != null) {
      final jokeId = message.data['joke_id'];
      await _analyticsService!.logNotificationTapped(
        jokeId: jokeId,
        notificationId: message.messageId,
      );
    }

    // Navigate to jokes screen and scroll to top
    _navigateToJokesScreen();
  }

  /// Navigate to jokes screen and reset to first joke
  void _navigateToJokesScreen() {
    try {
      // Use a delayed call to ensure the app is fully initialized
      Future.delayed(const Duration(milliseconds: 100), () {
        final context = navigatorKey.currentContext;
        if (context != null && context.mounted) {
          // Use GoRouter to navigate to jokes screen
          GoRouter.of(context).go('/jokes');
          debugPrint('Navigated to jokes screen via GoRouter');
        } else {
          debugPrint(
            'Navigator context not available for notification navigation',
          );
        }
      });
    } catch (e) {
      debugPrint('Failed to navigate to jokes screen: $e');
    }
  }

  /// Process joke notification - pre-cache images for faster app loading
  /// FCM handles displaying the notification with images automatically
  Future<void> _processJokeNotification(RemoteMessage message) async {
    try {
      final jokeData = message.data;
      final jokeId = jokeData['joke_id'];

      debugPrint('Processing joke notification for joke: $jokeId');

      // Pre-cache images in parallel so they load instantly when user opens the app
      final List<Future<void>> cachingFutures = [];

      if (jokeData.containsKey('setup_image_url')) {
        cachingFutures.add(_cacheImage(jokeData['setup_image_url']));
      }
      if (jokeData.containsKey('punchline_image_url')) {
        cachingFutures.add(_cacheImage(jokeData['punchline_image_url']));
      }

      if (cachingFutures.isNotEmpty) {
        await Future.wait(cachingFutures);
      }

      debugPrint('Images pre-cached for joke: $jokeId');
    } catch (e) {
      debugPrint('Error processing joke notification: $e');
      // FCM will still show the notification even if image caching fails
    }
  }

  /// Cache image for faster loading
  Future<void> _cacheImage(String imageUrl) async {
    try {
      final imageService = ImageService();
      await imageService.precacheJokeImage(imageUrl);
    } catch (e) {
      debugPrint('Failed to cache image $imageUrl: $e');
    }
  }

  /// Get FCM token for server-side targeting (if needed)
  Future<String?> getFCMToken() async {
    return await FirebaseMessaging.instance.getToken();
  }
}

/// Background message handler - must be top-level function
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  debugPrint('Handling background FCM message: ${message.messageId}');

  // Initialize Firebase if not already done
  await Firebase.initializeApp();

  // Process the joke notification
  final notificationService = NotificationService();
  await notificationService._processJokeNotification(message);
}
