import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';

/// Abstract interface for daily joke subscription service
abstract class DailyJokeSubscriptionService {
  /// Check if user is subscribed to daily jokes
  Future<bool> isSubscribed();

  /// Get the user's preferred notification hour (0-23) in local time
  /// Returns -1 if not set or not subscribed
  Future<int> getSubscriptionHour();

  /// Check if user has ever made a subscription choice (true/false)
  /// Returns false if they've never been asked or made a choice
  Future<bool> hasUserMadeSubscriptionChoice();

  /// Ensure subscription is synced with FCM server (call on app startup)
  Future<bool> ensureSubscriptionSync();

  /// Complete subscription flow with notification permission handling
  /// Returns true if subscription was successful, false if failed or permission denied
  Future<bool> subscribeWithNotificationPermission({int? hour});

  /// Unsubscribe from daily jokes (no permission required)
  /// Returns true if unsubscription was successful
  Future<bool> unsubscribe();
}

/// Concrete implementation of the daily joke subscription service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  DailyJokeSubscriptionServiceImpl({
    required SharedPreferences sharedPreferences,
    NotificationService? notificationService,
  }) : _sharedPreferences = sharedPreferences,
       _notificationService = notificationService ?? NotificationService();

  final SharedPreferences _sharedPreferences;
  final NotificationService _notificationService;

  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _subscriptionHourKey = 'daily_jokes_subscribed_hour';
  static const String _topicPrefix = 'tester_jokes';
  static const int defaultHour = 9; // 9 AM default

  // Cache expensive reads for performance
  bool? _cachedSubscriptionState;
  int? _cachedSubscriptionHour;

  @override
  Future<bool> isSubscribed() async {
    // Use cache if available for performance
    if (_cachedSubscriptionState != null) {
      return _cachedSubscriptionState!;
    }
    _cachedSubscriptionState =
        _sharedPreferences.getBool(_subscriptionKey) ?? false;
    return _cachedSubscriptionState!;
  }

  @override
  Future<int> getSubscriptionHour() async {
    // Use cache if available for performance
    if (_cachedSubscriptionHour == null) {
      int hour = _sharedPreferences.getInt(_subscriptionHourKey) ?? -1;
      if (hour < 0 || hour > 23) {
        // Migrate existing subscribers to default hour
        hour = defaultHour;

        // _setSubscriptionHour sets _cachedSubscriptionHour if successful
        await _setSubscriptionHour(hour);
      }

      _cachedSubscriptionHour ??= hour;
    }

    return _cachedSubscriptionHour!;
  }

  @override
  Future<bool> hasUserMadeSubscriptionChoice() async {
    return _sharedPreferences.containsKey(_subscriptionKey);
  }

  /// Convert local hour to UTC-12 hour and determine topic suffix
  String _calculateTopicName(int localHour) {
    if (localHour < 0 || localHour > 23) {
      throw ArgumentError('Invalid hour: $localHour. Must be 0-23.');
    }

    // Get current timezone offset from UTC in hours
    final now = DateTime.now();
    final localOffset = now.timeZoneOffset;

    // Handle timezone detection failure - fallback to PST (UTC-8)
    double offsetHours;
    try {
      offsetHours = localOffset.inMinutes / 60.0;
    } catch (e) {
      debugPrint('Failed to get timezone offset, defaulting to PST: $e');
      offsetHours = -8.0; // PST
    }

    // Create local time and UTC-12 time for the same moment
    final localTime = DateTime(now.year, now.month, now.day, localHour);
    final utcTime = localTime.subtract(
      Duration(minutes: (offsetHours * 60).round()),
    );
    final utcMinus12Time = utcTime.subtract(const Duration(hours: 12));

    final utcMinus12Hour = utcMinus12Time.hour;

    // Determine suffix based on day relationship
    String suffix = utcMinus12Time.day < localTime.day ? 'n' : 'c';

    return '${_topicPrefix}_${utcMinus12Hour.toString().padLeft(2, '0')}$suffix';
  }

  /// Get all possible topic names (for unsubscribing)
  List<String> _getAllPossibleTopics() {
    final topics = <String>[_topicPrefix]; // Legacy topic

    // Add all hour/suffix combinations
    for (int hour = 0; hour < 24; hour++) {
      final hourStr = hour.toString().padLeft(2, '0');
      topics.add('${_topicPrefix}_${hourStr}c');
      topics.add('${_topicPrefix}_${hourStr}n');
    }

    return topics;
  }

  /// Ensure subscription is synced with FCM server
  /// Call this on app startup or after preference changes to handle sync
  @override
  Future<bool> ensureSubscriptionSync() async {
    try {
      String? topicToSubscribe;
      final isLocallySubscribed = await isSubscribed();

      if (isLocallySubscribed) {
        final hour = await getSubscriptionHour();
        topicToSubscribe = _calculateTopicName(hour);
      }

      // Unsubscribe from all topics except the one we want to subscribe to
      final allTopics = _getAllPossibleTopics();
      for (final topic in allTopics) {
        if (topicToSubscribe != null && topic == topicToSubscribe) {
          await FirebaseMessaging.instance.subscribeToTopic(topic);
          debugPrint('Subscribed to $topic');
        } else {
          await FirebaseMessaging.instance.unsubscribeFromTopic(topic);
          debugPrint('Unsubscribed from $topic');
        }
      }

      return true;
    } catch (e) {
      debugPrint('Failed to sync subscription state: $e');
      return false;
    }
  }

  /// Complete subscription flow with notification permission handling
  /// Returns true if subscription was successful, false if failed or permission denied
  @override
  Future<bool> subscribeWithNotificationPermission({int? hour}) async {
    try {
      // First, save the subscription preferences
      final prefSaved = await _setSubscriptionPreference(true);
      if (!prefSaved) {
        debugPrint('Failed to save subscription preferences');
        return false;
      }

      // Then set the hour if given. If not, do nothing, and ensureSubscriptionSync
      // will set to the default hour later.
      if (hour != null && (hour >= 0 && hour <= 23)) {
        final hourSaved = await _setSubscriptionHour(hour);
        if (!hourSaved) {
          debugPrint('Failed to save subscription hour');
          return false;
        }
      }

      // Request notification permission
      final permissionGranted =
          await _notificationService.requestNotificationPermissions();

      if (permissionGranted) {
        // Permission granted, sync with FCM
        debugPrint(
          'Successfully subscribed with notification permission at hour ${hour ?? "EXISTING"}',
        );
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
        debugPrint('Failed to save unsubscription preferences');
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
      await _sharedPreferences.setBool(_subscriptionKey, subscribed);
      _cachedSubscriptionState = subscribed;
      return true;
    } catch (e) {
      debugPrint('Failed to save subscription preference: $e');
      return false;
    }
  }

  // Save subscription hour locally and update cache
  Future<bool> _setSubscriptionHour(int hour) async {
    try {
      await _sharedPreferences.setInt(_subscriptionHourKey, hour);

      _cachedSubscriptionHour = hour;
      return true;
    } catch (e) {
      debugPrint('Failed to save subscription hour: $e');
      return false;
    }
  }
}

/// Riverpod provider for the daily joke subscription service
final dailyJokeSubscriptionServiceProvider =
    Provider<DailyJokeSubscriptionService>((ref) {
      final sharedPreferences = ref.watch(sharedPreferencesInstanceProvider);
      return DailyJokeSubscriptionServiceImpl(
        sharedPreferences: sharedPreferences,
      );
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
