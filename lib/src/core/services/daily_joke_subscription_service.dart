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

  /// Ensure subscription is synced with FCM server (call on app startup)
  Future<bool> ensureSubscriptionSync();
}

/// Concrete implementation of the daily joke subscription service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _topicName = 'daily-jokes';

  @override
  Future<bool> isSubscribed() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_subscriptionKey) ?? false;
  }

  /// Ensure subscription is active on FCM server
  /// Call this on app startup to handle stale subscription cleanup
  @override
  Future<bool> ensureSubscriptionSync() async {
    final isLocallySubscribed = await isSubscribed();
    
    if (isLocallySubscribed) {
      try {
        // Re-subscribe to ensure server-side subscription is active
        await FirebaseMessaging.instance.subscribeToTopic(_topicName);
        debugPrint('Re-confirmed subscription to $_topicName on startup');
        return true;
      } catch (e) {
        debugPrint('Failed to re-confirm subscription: $e');
        // Keep local state as-is, but log the issue
        return false;
      }
    }
    
    return true; // Not subscribed, nothing to sync
  }

  @override
  Future<bool> subscribe() async {
    try {
      // Subscribe directly to FCM topic
      await FirebaseMessaging.instance.subscribeToTopic(_topicName);

      // Store subscription status locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_subscriptionKey, true);

      debugPrint('Successfully subscribed to daily jokes topic: $_topicName');
      return true;
    } catch (e) {
      debugPrint('Failed to subscribe to daily jokes: $e');
      return false;
    }
  }

  @override
  Future<bool> unsubscribe() async {
    try {
      // Unsubscribe directly from FCM topic
      await FirebaseMessaging.instance.unsubscribeFromTopic(_topicName);

      // Store subscription status locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_subscriptionKey, false);

      debugPrint('Successfully unsubscribed from daily jokes topic: $_topicName');
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

/// Simple state provider for subscription status with manual refresh
final subscriptionStatusProvider = StateProvider<AsyncValue<bool>>((ref) {
  return const AsyncValue.loading();
});

/// Provider to refresh subscription status
final subscriptionRefreshProvider = Provider<Future<void>>((ref) async {
  final subscriptionService = ref.watch(dailyJokeSubscriptionServiceProvider);
  final statusNotifier = ref.read(subscriptionStatusProvider.notifier);
  
  try {
    final isSubscribed = await subscriptionService.isSubscribed();
    statusNotifier.state = AsyncValue.data(isSubscribed);
  } catch (error, stackTrace) {
    statusNotifier.state = AsyncValue.error(error, stackTrace);
  }
});
