import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';

/// Abstract interface for daily joke subscription service
abstract class DailyJokeSubscriptionService {
  /// Check if user is subscribed to daily jokes
  Future<bool> isSubscribed();

  /// Check if user has ever made a subscription choice (true/false)
  /// Returns false if they've never been asked or made a choice
  Future<bool> hasUserMadeSubscriptionChoice();

  /// Ensure subscription is synced with FCM server (call on app startup)
  Future<bool> ensureSubscriptionSync();

  /// Complete subscription flow with notification permission handling
  /// Returns true if subscription was successful, false if failed or permission denied
  Future<bool> subscribeWithNotificationPermission();

  /// Unsubscribe from daily jokes (no permission required)
  /// Returns true if unsubscription was successful
  Future<bool> unsubscribe();
}

/// Concrete implementation of the daily joke subscription service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _topicName = 'daily-jokes';

  // Cache expensive SharedPreferences reads for performance
  bool? _cachedSubscriptionState;

  @override
  Future<bool> isSubscribed() async {
    // Use cache if available for performance
    if (_cachedSubscriptionState != null) {
      return _cachedSubscriptionState!;
    }
    final prefs = await SharedPreferences.getInstance();
    _cachedSubscriptionState = prefs.getBool(_subscriptionKey) ?? false;
    return _cachedSubscriptionState!;
  }

  @override
  Future<bool> hasUserMadeSubscriptionChoice() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey(_subscriptionKey);
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

  /// Complete subscription flow with notification permission handling
  /// Returns true if subscription was successful, false if failed or permission denied
  @override
  Future<bool> subscribeWithNotificationPermission() async {
    try {
      // First, save the subscription preference
      final prefSaved = await _setSubscriptionPreference(true);
      if (!prefSaved) {
        debugPrint('Failed to save subscription preference');
        return false;
      }

      // Request notification permission
      final notificationService = NotificationService();
      final permissionGranted =
          await notificationService.requestNotificationPermissions();

      if (permissionGranted) {
        // Permission granted, sync with FCM
        debugPrint('Successfully subscribed with notification permission');
        return true;
      } else {
        // Permission denied, rollback subscription
        debugPrint('Notification permission denied, rolling back subscription');
        await _setSubscriptionPreference(false);
        return false;
      }
    } catch (e) {
      debugPrint('Error in subscription flow: $e');
      // Rollback on any error
      await _setSubscriptionPreference(false);
      return false;
    } finally {
      // Ensure subscription is synced after any operation
      await ensureSubscriptionSync();
    }
  }

  /// Unsubscribe from daily jokes (no permission required)
  /// Returns true if unsubscription was successful
  @override
  Future<bool> unsubscribe() async {
    try {
      final prefSaved = await _setSubscriptionPreference(false);
      if (prefSaved) {
        debugPrint('Successfully unsubscribed');
        return true;
      } else {
        debugPrint('Failed to save unsubscription preference');
        return false;
      }
    } catch (e) {
      debugPrint('Error unsubscribing: $e');
      return false;
    } finally {
      // Ensure subscription is synced after any operation
      await ensureSubscriptionSync();
    }
  }

  // Save subscription preference locally and update cache
  Future<bool> _setSubscriptionPreference(bool subscribed) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_subscriptionKey, subscribed);
      _cachedSubscriptionState = subscribed;
      return true;
    } catch (e) {
      debugPrint('Failed to save subscription preference: $e');
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

/// State class for subscription prompt management
class SubscriptionPromptState {
  final bool isSubscribed;
  final bool hasUserMadeChoice;
  final bool shouldShowPrompt;
  final bool isTimerActive;

  const SubscriptionPromptState({
    this.isSubscribed = false,
    this.hasUserMadeChoice = false,
    this.shouldShowPrompt = false,
    this.isTimerActive = false,
  });

  SubscriptionPromptState copyWith({
    bool? isSubscribed,
    bool? hasUserMadeChoice,
    bool? shouldShowPrompt,
    bool? isTimerActive,
  }) {
    return SubscriptionPromptState(
      isSubscribed: isSubscribed ?? this.isSubscribed,
      hasUserMadeChoice: hasUserMadeChoice ?? this.hasUserMadeChoice,
      shouldShowPrompt: shouldShowPrompt ?? this.shouldShowPrompt,
      isTimerActive: isTimerActive ?? this.isTimerActive,
    );
  }

  /// Early exit: should we skip all prompt logic?
  /// Skip if user has already made a choice (subscribed or declined)
  bool get shouldSkipPromptLogic => hasUserMadeChoice;
}

/// High-performance subscription prompt state manager
class SubscriptionPromptNotifier
    extends StateNotifier<SubscriptionPromptState> {
  SubscriptionPromptNotifier(this._subscriptionService)
    : super(const SubscriptionPromptState()) {
    _initializeState();
  }

  final DailyJokeSubscriptionService _subscriptionService;
  Timer? _promptTimer;

  /// Initialize state by checking cached preferences (called once)
  Future<void> _initializeState() async {
    try {
      final isSubscribed = await _subscriptionService.isSubscribed();
      final hasUserMadeChoice =
          await _subscriptionService.hasUserMadeSubscriptionChoice();

      state = state.copyWith(
        isSubscribed: isSubscribed,
        hasUserMadeChoice: hasUserMadeChoice,
      );
    } catch (e) {
      debugPrint('Failed to initialize subscription prompt state: $e');
    }
  }

  /// Start 5-second timer for subscription prompt (only if needed)
  void startPromptTimer() {
    // Early exit: don't start timer if already prompted or subscribed
    if (state.shouldSkipPromptLogic || state.isTimerActive) {
      return;
    }

    // Cancel any existing timer
    _promptTimer?.cancel();

    state = state.copyWith(isTimerActive: true);

    _promptTimer = Timer(const Duration(seconds: 4), () {
      // Double-check state hasn't changed during timer
      if (!state.shouldSkipPromptLogic && mounted) {
        state = state.copyWith(shouldShowPrompt: true, isTimerActive: false);
      }
    });
  }

  /// Cancel prompt timer
  void cancelPromptTimer() {
    _promptTimer?.cancel();
    state = state.copyWith(isTimerActive: false);
  }

  /// Handle subscription (user clicked "Subscribe")
  Future<bool> subscribeUser() async {
    final success =
        await _subscriptionService.subscribeWithNotificationPermission();
    if (success) {
      state = state.copyWith(
        isSubscribed: true,
        hasUserMadeChoice: true,
        shouldShowPrompt: false,
        isTimerActive: false,
      );
      _promptTimer?.cancel();
    }
    return success;
  }

  /// Mark that prompt was actually shown to user
  Future<void> markPromptShown() async {
    // Use unsubscribe to ensure popup never shows again (sets preference to false)
    await _subscriptionService.unsubscribe();

    state = state.copyWith(hasUserMadeChoice: true);
  }

  /// Dismiss prompt (user clicked "Maybe later")
  Future<void> dismissPrompt() async {
    await markPromptShown();
    state = state.copyWith(shouldShowPrompt: false, isTimerActive: false);
    _promptTimer?.cancel();
  }

  @override
  void dispose() {
    _promptTimer?.cancel();
    super.dispose();
  }
}

/// Provider for subscription prompt state management
final subscriptionPromptProvider = StateNotifierProvider<
  SubscriptionPromptNotifier,
  SubscriptionPromptState
>((ref) {
  final subscriptionService = ref.watch(dailyJokeSubscriptionServiceProvider);
  return SubscriptionPromptNotifier(subscriptionService);
});
