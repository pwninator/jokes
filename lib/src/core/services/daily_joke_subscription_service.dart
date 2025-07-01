import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:async';

/// Abstract interface for daily joke subscription service
abstract class DailyJokeSubscriptionService {
  /// Check if user is subscribed to daily jokes
  Future<bool> isSubscribed();

  /// Ensure subscription is synced with FCM server (call on app startup)
  Future<bool> ensureSubscriptionSync();

  /// Save subscription preference immediately (for UI responsiveness)
  Future<bool> setSubscriptionPreference(bool subscribed);

  /// Check if user has ever been prompted for subscription (cached after first call)
  Future<bool> hasBeenPromptedForSubscription();

  /// Mark that user has been prompted for subscription
  Future<bool> markUserPromptedForSubscription();
}

/// Concrete implementation of the daily joke subscription service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _promptedKey = 'daily_jokes_prompt_shown';
  static const String _topicName = 'daily-jokes';
  
  // Cache expensive SharedPreferences reads for performance
  bool? _cachedPromptedState;
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

  /// Check if user has been prompted (cached for performance)
  @override
  Future<bool> hasBeenPromptedForSubscription() async {
    // Return cached value if available (avoids SharedPreferences read)
    if (_cachedPromptedState != null) {
      return _cachedPromptedState!;
    }

    final prefs = await SharedPreferences.getInstance();
    _cachedPromptedState = prefs.getBool(_promptedKey) ?? false;
    return _cachedPromptedState!;
  }

  /// Mark user as prompted (invalidates cache)
  @override
  Future<bool> markUserPromptedForSubscription() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_promptedKey, true);
      _cachedPromptedState = true; // Update cache
      return true;
    } catch (e) {
      debugPrint('Failed to mark user as prompted: $e');
      return false;
    }
  }

  /// Save subscription preference immediately (for UI responsiveness)
  /// Call ensureSubscriptionSync afterward to handle FCM operations
  @override
  Future<bool> setSubscriptionPreference(bool subscribed) async {
    final success = await _saveSubscriptionPreference(subscribed);
    if (success) {
      _cachedSubscriptionState = subscribed; // Update cache
    }
    return success;
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
  final bool hasBeenPrompted;
  final bool isSubscribed;
  final bool shouldShowPrompt;
  final bool isTimerActive;

  const SubscriptionPromptState({
    this.hasBeenPrompted = false,
    this.isSubscribed = false,
    this.shouldShowPrompt = false,
    this.isTimerActive = false,
  });

  SubscriptionPromptState copyWith({
    bool? hasBeenPrompted,
    bool? isSubscribed,
    bool? shouldShowPrompt,
    bool? isTimerActive,
  }) {
    return SubscriptionPromptState(
      hasBeenPrompted: hasBeenPrompted ?? this.hasBeenPrompted,
      isSubscribed: isSubscribed ?? this.isSubscribed,
      shouldShowPrompt: shouldShowPrompt ?? this.shouldShowPrompt,
      isTimerActive: isTimerActive ?? this.isTimerActive,
    );
  }

  /// Early exit: should we skip all prompt logic?
  bool get shouldSkipPromptLogic => hasBeenPrompted || isSubscribed;
}

/// High-performance subscription prompt state manager
class SubscriptionPromptNotifier extends StateNotifier<SubscriptionPromptState> {
  SubscriptionPromptNotifier(this._subscriptionService) : super(const SubscriptionPromptState()) {
    _initializeState();
  }

  final DailyJokeSubscriptionService _subscriptionService;
  Timer? _promptTimer;

  /// Initialize state by checking cached preferences (called once)
  Future<void> _initializeState() async {
    try {
      final hasBeenPrompted = await _subscriptionService.hasBeenPromptedForSubscription();
      final isSubscribed = await _subscriptionService.isSubscribed();
      
      state = state.copyWith(
        hasBeenPrompted: hasBeenPrompted,
        isSubscribed: isSubscribed,
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

    _promptTimer = Timer(const Duration(seconds: 5), () {
      // Double-check state hasn't changed during timer
      if (!state.shouldSkipPromptLogic && mounted) {
        state = state.copyWith(
          shouldShowPrompt: true,
          isTimerActive: false,
        );
      }
    });
  }

  /// Cancel prompt timer
  void cancelPromptTimer() {
    _promptTimer?.cancel();
    state = state.copyWith(isTimerActive: false);
  }

  /// Mark user as prompted and hide prompt
  Future<void> markUserPrompted() async {
    await _subscriptionService.markUserPromptedForSubscription();
    state = state.copyWith(
      hasBeenPrompted: true,
      shouldShowPrompt: false,
      isTimerActive: false,
    );
    _promptTimer?.cancel();
  }

  /// Handle subscription (user clicked "Subscribe")
  Future<bool> subscribeUser() async {
    final success = await _subscriptionService.setSubscriptionPreference(true);
    if (success) {
      // Sync with FCM in background
      _subscriptionService.ensureSubscriptionSync();
      
      state = state.copyWith(
        isSubscribed: true,
        hasBeenPrompted: true,
        shouldShowPrompt: false,
        isTimerActive: false,
      );
      _promptTimer?.cancel();
    }
    return success;
  }

  /// Dismiss prompt (user clicked "Maybe later")
  Future<void> dismissPrompt() async {
    await markUserPrompted();
  }

  @override
  void dispose() {
    _promptTimer?.cancel();
    super.dispose();
  }
}

/// Provider for subscription prompt state management
final subscriptionPromptProvider = StateNotifierProvider<SubscriptionPromptNotifier, SubscriptionPromptState>((ref) {
  final subscriptionService = ref.watch(dailyJokeSubscriptionServiceProvider);
  return SubscriptionPromptNotifier(subscriptionService);
});
