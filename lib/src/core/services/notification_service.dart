import 'dart:convert';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;
  bool _localNotificationsInitialized = false;

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
    _requestFCMPermissions().catchError((e) {
      debugPrint('Background FCM permission request failed: $e');
    });

    _initializeFCMListeners().catchError((e) {
      debugPrint('Background FCM initialization failed: $e');
    });

    _syncSubscriptions().catchError((e) {
      debugPrint('Background subscription sync failed: $e');
    });
  }

  /// Request FCM permissions (blocking - user needs to respond)
  Future<void> _requestFCMPermissions() async {
    try {
      await FirebaseMessaging.instance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );
      debugPrint('FCM permissions requested');
    } catch (e) {
      debugPrint('Failed to request FCM permissions: $e');
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

  /// Initialize local notifications
  Future<void> _initializeLocalNotifications() async {
    const androidSettings = AndroidInitializationSettings(
      // Default icon to show in notification
      '@drawable/ic_notification',
    );
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _localNotifications.initialize(
      settings,
      onDidReceiveNotificationResponse: _handleNotificationTap,
    );

    // Create notification channel for Android
    const androidChannel = AndroidNotificationChannel(
      'daily_jokes',
      'Daily Jokes',
      description: 'Daily joke notifications',
      importance: Importance.high,
      playSound: true,
    );

    await _localNotifications
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(androidChannel);
  }

  /// Handle foreground FCM messages
  Future<void> _handleForegroundMessage(RemoteMessage message) async {
    debugPrint('Received foreground FCM message: ${message.messageId}');
    await _processJokeNotification(message);
  }

  /// Handle FCM message when app is opened from notification
  Future<void> _handleMessageOpenedApp(RemoteMessage message) async {
    debugPrint('App opened from FCM notification: ${message.messageId}');
    // App is already opening, no additional action needed
  }

  /// Handle local notification tap
  void _handleNotificationTap(NotificationResponse response) {
    debugPrint('Local notification tapped: ${response.payload}');
    // App is already opening, no additional action needed
  }

  /// Process joke notification and show local notification
  Future<void> _processJokeNotification(RemoteMessage message) async {
    try {
      final jokeData = message.data;
      final jokeId = jokeData['jokeId'];
      final setup = jokeData['setup'] ?? 'Daily Joke Available!';

      debugPrint('Processing joke notification for joke: $jokeId');

      // Pre-cache images if URLs are provided
      if (jokeData.containsKey('setupImageUrl')) {
        await _cacheImage(jokeData['setupImageUrl']);
      }
      if (jokeData.containsKey('punchlineImageUrl')) {
        await _cacheImage(jokeData['punchlineImageUrl']);
      }

      // Show local notification
      await _showJokeNotification(
        title: 'Daily Joke',
        body: setup,
        payload: jsonEncode({'jokeId': jokeId}),
      );
    } catch (e) {
      debugPrint('Error processing joke notification: $e');
      // Show fallback notification
      await _showJokeNotification(
        title: 'Daily Joke',
        body: 'Tap to see today\'s joke!',
        payload: jsonEncode({'jokeId': 'fallback'}),
      );
    }
  }

  /// Cache image for faster loading
  Future<void> _cacheImage(String imageUrl) async {
    try {
      await DefaultCacheManager().downloadFile(imageUrl);
      debugPrint('Cached image: $imageUrl');
    } catch (e) {
      debugPrint('Failed to cache image $imageUrl: $e');
    }
  }

  /// Show local notification (with lazy initialization)
  Future<void> _showJokeNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
    // Ensure local notifications are initialized (lazy initialization)
    await _ensureLocalNotificationsInitialized();

    const androidDetails = AndroidNotificationDetails(
      'daily_jokes',
      'Daily Jokes',
      channelDescription: 'Daily joke notifications',
      importance: Importance.high,
      priority: Priority.high,
      showWhen: true,
      icon: '@drawable/ic_notification',
      color: primaryColor,
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _localNotifications.show(
      0, // notification id
      title,
      body,
      details,
      payload: payload,
    );

    debugPrint('Showed local notification: $title - $body');
  }

  /// Ensure local notifications are initialized (lazy/on-demand)
  Future<void> _ensureLocalNotificationsInitialized() async {
    if (_localNotificationsInitialized) return;

    try {
      await _initializeLocalNotifications();
      _localNotificationsInitialized = true;
      debugPrint('Local notifications initialized on-demand');
    } catch (e) {
      debugPrint('Failed to initialize local notifications on-demand: $e');
      rethrow; // Let caller handle the error
    }
  }

  /// Get FCM token for server-side targeting (if needed)
  Future<String?> getFCMToken() async {
    return await FirebaseMessaging.instance.getToken();
  }

  /// Test notification (for admin/development purposes)
  Future<void> showTestNotification() async {
    await _showJokeNotification(
      title: 'Test Notification',
      body: 'This is a test notification from the admin panel!',
      payload: '{"jokeId": "test", "isTest": true}',
    );
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
