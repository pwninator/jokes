import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Abstract interface for daily joke subscription service
abstract class DailyJokeSubscriptionService {
  /// Check if user is subscribed to daily jokes
  Future<bool> isSubscribed();

  /// Ensure subscription is synced with FCM server (call on app startup)
  Future<bool> ensureSubscriptionSync();

  /// Save subscription preference immediately (for UI responsiveness)
  Future<bool> setSubscriptionPreference(bool subscribed);


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

  /// Ensure subscription is synced with FCM server
  /// Call this on app startup or after preference changes to handle sync
  @override
  Future<bool> ensureSubscriptionSync() async {
    final isLocallySubscribed = await isSubscribed();

    try {
      if (isLocallySubscribed) {
        // Subscribe to ensure server-side subscription is active
        await FirebaseMessaging.instance.subscribeToTopic(_topicName);
        debugPrint('Ensured subscription to $_topicName');
      } else {
        // Unsubscribe to ensure server-side subscription is inactive
        await FirebaseMessaging.instance.unsubscribeFromTopic(_topicName);
        debugPrint('Ensured unsubscription from $_topicName');
      }
      return true;
    } catch (e) {
      debugPrint('Failed to sync subscription state: $e');
      // Keep local state as-is, but log the issue
      return false;
    }
  }

  /// Save subscription preference locally
  Future<bool> _saveSubscriptionPreference(bool subscribed) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_subscriptionKey, subscribed);
      return true;
    } catch (e) {
      debugPrint('Failed to save subscription preference: $e');
      return false;
    }
  }

  /// Save subscription preference immediately (for UI responsiveness)
  /// Call ensureSubscriptionSync afterward to handle FCM operations
  @override
  Future<bool> setSubscriptionPreference(bool subscribed) async {
    return await _saveSubscriptionPreference(subscribed);
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
