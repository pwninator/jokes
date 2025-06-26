import 'dart:convert';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;

  /// Initialize the notification service
  Future<void> initialize() async {
    if (_isInitialized) return;

    await _initializeLocalNotifications();
    await _initializeFCM();

    _isInitialized = true;
  }

  /// Initialize local notifications
  Future<void> _initializeLocalNotifications() async {
    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
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

  /// Initialize Firebase Cloud Messaging
  Future<void> _initializeFCM() async {
    // Request permission for iOS
    await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    // Get FCM token for debugging
    final token = await FirebaseMessaging.instance.getToken();
    debugPrint('FCM Token: $token');

    // Handle foreground messages
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // Handle notification taps when app is in background/terminated
    FirebaseMessaging.onMessageOpenedApp.listen(_handleMessageOpenedApp);
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

  /// Show local notification
  Future<void> _showJokeNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'daily_jokes',
      'Daily Jokes',
      channelDescription: 'Daily joke notifications',
      importance: Importance.high,
      priority: Priority.high,
      showWhen: true,
      icon: '@mipmap/ic_launcher',
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
