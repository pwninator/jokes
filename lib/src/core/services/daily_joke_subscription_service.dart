import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Abstract interface for daily joke subscription service
abstract class DailyJokeSubscriptionService {
  /// Check if user is subscribed to daily jokes
  Future<bool> isSubscribed();

  /// Subscribe to daily joke notifications
  Future<bool> subscribe();

  /// Unsubscribe from daily joke notifications
  Future<bool> unsubscribe();

  /// Toggle subscription status
  Future<bool> toggleSubscription();

  /// Test function to manually trigger a daily joke notification
  Future<bool> testDailyJoke();
}

/// Concrete implementation of the daily joke subscription service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  static const String _subscriptionKey = 'daily_jokes_subscribed';

  @override
  Future<bool> isSubscribed() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_subscriptionKey) ?? false;
  }

  @override
  Future<bool> subscribe() async {
    try {
      // Get FCM token
      final token = await FirebaseMessaging.instance.getToken();
      if (token == null) {
        debugPrint('Failed to get FCM token');
        return false;
      }

      // Call Cloud Function to subscribe to topic
      final functions = FirebaseFunctions.instance;
      final callable = functions.httpsCallable('subscribeToDailyJokes');

      await callable.call({'token': token});

      // Store subscription status locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_subscriptionKey, true);

      debugPrint('Successfully subscribed to daily jokes');
      return true;
    } catch (e) {
      debugPrint('Failed to subscribe to daily jokes: $e');
      return false;
    }
  }

  @override
  Future<bool> unsubscribe() async {
    try {
      // Get FCM token
      final token = await FirebaseMessaging.instance.getToken();
      if (token == null) {
        debugPrint('Failed to get FCM token');
        return false;
      }

      // Call Cloud Function to unsubscribe from topic
      final functions = FirebaseFunctions.instance;
      final callable = functions.httpsCallable('unsubscribeFromDailyJokes');

      await callable.call({'token': token});

      // Store subscription status locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_subscriptionKey, false);

      debugPrint('Successfully unsubscribed from daily jokes');
      return true;
    } catch (e) {
      debugPrint('Failed to unsubscribe from daily jokes: $e');
      return false;
    }
  }

  @override
  Future<bool> toggleSubscription() async {
    final isCurrentlySubscribed = await isSubscribed();

    if (isCurrentlySubscribed) {
      return await unsubscribe();
    } else {
      return await subscribe();
    }
  }

  @override
  Future<bool> testDailyJoke() async {
    try {
      final functions = FirebaseFunctions.instance;
      final callable = functions.httpsCallable('sendDailyJokeManual');

      final result = await callable.call();
      debugPrint('Test notification result: ${result.data}');

      return true;
    } catch (e) {
      debugPrint('Failed to send test notification: $e');
      return false;
    }
  }
}

/// Riverpod provider for the daily joke subscription service
final dailyJokeSubscriptionServiceProvider =
    Provider<DailyJokeSubscriptionService>((ref) {
      return DailyJokeSubscriptionServiceImpl();
    });
