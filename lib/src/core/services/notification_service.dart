import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/app.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/common_widgets/main_navigation_widget.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/auth/presentation/auth_wrapper.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  bool _isInitialized = false;

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

    _syncSubscriptions().catchError((e) {
      debugPrint('Background subscription sync failed: $e');
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

  /// Sync subscription state with FCM server (background)
  Future<void> _syncSubscriptions() async {
    try {
      final subscriptionService = DailyJokeSubscriptionServiceImpl();
      await subscriptionService.ensureSubscriptionSync();
      debugPrint('Subscription sync completed in background');
    } catch (e) {
      debugPrint('Failed to sync subscriptions in background: $e');
      // Non-critical error, app continues normally
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

    // Navigate to jokes screen and scroll to top
    _navigateToJokesScreen();
  }

  /// Navigate to jokes screen and reset to first joke
  void _navigateToJokesScreen() {
    try {
      final navigatorContext = App.navigatorKey.currentContext;
      if (navigatorContext == null) {
        debugPrint('Navigator context not available');
        return;
      }

      // Try to access the MainNavigationWidget state
      final mainNavState = MainNavigationWidget.navigationKey.currentState;
      if (mainNavState != null) {
        // We can access the navigation widget, navigate to jokes tab and reset
        mainNavState.navigateToJokesAndReset();
        debugPrint('Navigated to jokes screen via MainNavigationWidget');
      } else {
        // MainNavigationWidget not available, do a full navigation reset
        Navigator.of(navigatorContext).pushAndRemoveUntil(
          MaterialPageRoute(builder: (context) => const AuthWrapper()),
          (route) => false,
        );
        debugPrint('Navigated to jokes screen via full navigation reset');
      }
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

  /// Cache image for faster loading using CachedJokeImage logic
  Future<void> _cacheImage(String imageUrl) async {
    try {
      final imageService = ImageService();
      await CachedJokeImage.precacheJokeImage(imageUrl, imageService);
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
