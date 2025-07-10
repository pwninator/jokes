import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';

/// State class representing subscription status and hour
class SubscriptionState {
  final bool isSubscribed;
  final int hour;

  const SubscriptionState({required this.isSubscribed, required this.hour});

  SubscriptionState copyWith({bool? isSubscribed, int? hour}) {
    return SubscriptionState(
      isSubscribed: isSubscribed ?? this.isSubscribed,
      hour: hour ?? this.hour,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is SubscriptionState &&
        other.isSubscribed == isSubscribed &&
        other.hour == hour;
  }

  @override
  int get hashCode => isSubscribed.hashCode ^ hour.hashCode;

  @override
  String toString() =>
      'SubscriptionState(isSubscribed: $isSubscribed, hour: $hour)';
}

/// Reactive StateNotifier that manages subscription state.
/// Sets subscription values, notifies on changes, and triggers background sync.
class SubscriptionNotifier extends StateNotifier<SubscriptionState> {
  SubscriptionNotifier(this._sharedPreferences, this._syncService)
    : super(_loadFromPrefs(_sharedPreferences)) {
    // Trigger background sync on startup
    _syncInBackground();
  }

  final SharedPreferences _sharedPreferences;
  final DailyJokeSubscriptionService _syncService;

  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _subscriptionHourKey = 'daily_jokes_subscribed_hour';
  static const int defaultHour = 9; // 9 AM default

  /// Load initial state from SharedPreferences
  static SubscriptionState _loadFromPrefs(SharedPreferences prefs) {
    final isSubscribed = prefs.getBool(_subscriptionKey) ?? false;
    int hour = prefs.getInt(_subscriptionHourKey) ?? -1;

    // Apply default hour logic
    if (hour < 0 || hour > 23) {
      hour = defaultHour;
    }

    return SubscriptionState(isSubscribed: isSubscribed, hour: hour);
  }

  /// SETTER: Set subscription status (fast - only updates SharedPreferences + notifies)
  Future<void> setSubscribed(bool subscribed) async {
    try {
      await _sharedPreferences.setBool(_subscriptionKey, subscribed);
      state = state.copyWith(isSubscribed: subscribed);
      _syncInBackground(); // Trigger background sync
    } catch (e) {
      debugPrint('Failed to save subscription preference: $e');
    }
  }

  /// SETTER: Set subscription hour (fast - only updates SharedPreferences + notifies)
  Future<void> setHour(int hour) async {
    if (hour < 0 || hour > 23) {
      debugPrint('Invalid hour: $hour. Must be 0-23.');
      return;
    }

    try {
      await _sharedPreferences.setInt(_subscriptionHourKey, hour);
      state = state.copyWith(hour: hour);
      _syncInBackground(); // Trigger background sync
    } catch (e) {
      debugPrint('Failed to save subscription hour: $e');
    }
  }

  /// SETTER: Subscribe with permission handling
  Future<bool> subscribeWithPermission({int? hour}) async {
    try {
      // Set hour first if provided
      if (hour != null) {
        await setHour(hour);
      }

      // Request permission
      final notificationService = NotificationService();
      final permissionGranted =
          await notificationService.requestNotificationPermissions();

      if (permissionGranted) {
        await setSubscribed(true);
        return true;
      } else {
        // Permission denied, don't subscribe
        await setSubscribed(false);
        return false;
      }
    } catch (e) {
      debugPrint('Error in subscription flow: $e');
      await setSubscribed(false);
      return false;
    }
  }

  /// SETTER: Unsubscribe (no permission needed)
  Future<void> unsubscribe() async {
    await setSubscribed(false);
  }

  /// Check if user has ever made a subscription choice
  bool hasUserMadeChoice() {
    return _sharedPreferences.containsKey(_subscriptionKey);
  }

  /// SYNCER: Background FCM sync (doesn't block UI)
  void _syncInBackground() {
    // Don't await - let it run in background
    _syncService.ensureSubscriptionSync().catchError((e) {
      debugPrint('Background sync failed: $e');
      return false;
    });
  }
}

/// Abstract interface for FCM sync operations (kept for separation of concerns)
abstract class DailyJokeSubscriptionService {
  /// Ensure subscription is synced with FCM server (background operation)
  Future<bool> ensureSubscriptionSync();
}

/// Concrete implementation of FCM sync service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  DailyJokeSubscriptionServiceImpl({
    required SharedPreferences sharedPreferences,
  }) : _sharedPreferences = sharedPreferences;

  final SharedPreferences _sharedPreferences;

  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _subscriptionHourKey = 'daily_jokes_subscribed_hour';
  static const String _topicPrefix = 'tester_jokes';
  static const int defaultHour = 9; // 9 AM default

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
  @override
  Future<bool> ensureSubscriptionSync() async {
    try {
      String? topicToSubscribe;
      final isLocallySubscribed =
          _sharedPreferences.getBool(_subscriptionKey) ?? false;

      if (isLocallySubscribed) {
        int hour =
            _sharedPreferences.getInt(_subscriptionHourKey) ?? defaultHour;
        if (hour < 0 || hour > 23) {
          hour = defaultHour;
        }
        topicToSubscribe = _calculateTopicName(hour);
      }

      // Get all topics and process them in parallel
      final allTopics = _getAllPossibleTopics();
      final futures = <Future<void>>[];

      for (final topic in allTopics) {
        if (topicToSubscribe != null && topic == topicToSubscribe) {
          futures.add(
            FirebaseMessaging.instance.subscribeToTopic(topic).then((_) {
              debugPrint('Subscribed to $topic');
            }),
          );
        } else {
          futures.add(
            FirebaseMessaging.instance.unsubscribeFromTopic(topic).then((_) {
              debugPrint('Unsubscribed from $topic');
            }),
          );
        }
      }

      // Wait for all operations to complete in parallel
      await Future.wait(futures);
      return true;
    } catch (e) {
      debugPrint('Failed to sync subscription state: $e');
      return false;
    }
  }
}

/// Provider for the FCM sync service
final dailyJokeSubscriptionServiceProvider =
    Provider<DailyJokeSubscriptionService>((ref) {
      final sharedPreferences = ref.watch(sharedPreferencesInstanceProvider);
      return DailyJokeSubscriptionServiceImpl(
        sharedPreferences: sharedPreferences,
      );
    });

/// Main reactive subscription provider (combines Notifier + Setter + Syncer)
final subscriptionProvider =
    StateNotifierProvider<SubscriptionNotifier, SubscriptionState>((ref) {
      final sharedPreferences = ref.watch(sharedPreferencesInstanceProvider);
      final syncService = ref.watch(dailyJokeSubscriptionServiceProvider);
      return SubscriptionNotifier(sharedPreferences, syncService);
    });

/// Convenience providers for specific parts of the state
final isSubscribedProvider = Provider<bool>((ref) {
  return ref.watch(subscriptionProvider).isSubscribed;
});

final subscriptionHourProvider = Provider<int>((ref) {
  return ref.watch(subscriptionProvider).hour;
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
  SubscriptionPromptNotifier(this._subscriptionNotifier)
    : super(const SubscriptionPromptState()) {
    _initializeState();
  }

  final SubscriptionNotifier _subscriptionNotifier;
  Timer? _promptTimer;

  /// Initialize state by checking cached preferences (called once)
  Future<void> _initializeState() async {
    try {
      final subscriptionState = _subscriptionNotifier.state;
      final hasUserMadeChoice = _subscriptionNotifier.hasUserMadeChoice();

      state = state.copyWith(
        isSubscribed: subscriptionState.isSubscribed,
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
    final success = await _subscriptionNotifier.subscribeWithPermission();
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
    await _subscriptionNotifier.unsubscribe();

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
final subscriptionPromptProvider =
    StateNotifierProvider<SubscriptionPromptNotifier, SubscriptionPromptState>((
      ref,
    ) {
      final subscriptionNotifier = ref.watch(subscriptionProvider.notifier);
      return SubscriptionPromptNotifier(subscriptionNotifier);
    });
