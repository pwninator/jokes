import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

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
    // Trigger background sync on startup (subscribe only; do not unsubscribe others)
    _syncInBackground(unsubscribeOthers: false);
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
      AppLogger.warn('Failed to save subscription preference: $e');
    }
  }

  /// SETTER: Set subscription hour (fast - only updates SharedPreferences + notifies)
  Future<void> setHour(int hour) async {
    if (hour < 0 || hour > 23) {
      AppLogger.warn('Invalid hour: $hour. Must be 0-23.');
      return;
    }

    try {
      await _sharedPreferences.setInt(_subscriptionHourKey, hour);
      state = state.copyWith(hour: hour);
      _syncInBackground(); // Trigger background sync
    } catch (e) {
      AppLogger.warn('Failed to save subscription hour: $e');
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
      final permissionGranted = await notificationService
          .requestNotificationPermissions();

      if (permissionGranted) {
        await setSubscribed(true);
        return true;
      } else {
        // Permission denied, don't subscribe
        await setSubscribed(false);
        return false;
      }
    } catch (e) {
      AppLogger.warn('Error in subscription flow: $e');
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
  void _syncInBackground({bool unsubscribeOthers = true}) {
    // Don't await - let it run in background
    _syncService
        .ensureSubscriptionSync(unsubscribeOthers: unsubscribeOthers)
        .catchError((e) {
          AppLogger.warn('Background sync failed: $e');
          return false;
        });
  }
}

/// Abstract interface for FCM sync operations (kept for separation of concerns)
abstract class DailyJokeSubscriptionService {
  /// Ensure subscription is synced with FCM server (background operation)
  /// If [unsubscribeOthers] is true, unsubscribe from all other possible topics.
  /// On app startup this should be false to avoid mass-unsubscribe.
  Future<bool> ensureSubscriptionSync({bool unsubscribeOthers = true});
}

/// Concrete implementation of FCM sync service
class DailyJokeSubscriptionServiceImpl implements DailyJokeSubscriptionService {
  DailyJokeSubscriptionServiceImpl({
    required SharedPreferences sharedPreferences,
    required FirebaseMessaging firebaseMessaging,
  }) : _sharedPreferences = sharedPreferences,
       _firebaseMessaging = firebaseMessaging;

  final SharedPreferences _sharedPreferences;
  final FirebaseMessaging _firebaseMessaging;

  static const String _subscriptionKey = 'daily_jokes_subscribed';
  static const String _subscriptionHourKey = 'daily_jokes_subscribed_hour';
  static const String _topicPrefix = JokeConstants.defaultJokeScheduleId;
  static const int defaultHour = 9; // 9 AM default

  // Debouncing + Latest-Wins + Mutex implementation
  Timer? _debounceTimer;
  Completer<bool>? _currentCompleter;
  int _currentOperationId = 0;
  static const Duration _debounceDelay = Duration(milliseconds: 500);

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
      AppLogger.warn('Failed to get timezone offset, defaulting to PST: $e');
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
  /// Uses debouncing + latest-wins + mutex to handle rapid changes efficiently
  @override
  Future<bool> ensureSubscriptionSync({bool unsubscribeOthers = true}) async {
    // 1. DEBOUNCING: Cancel any pending timer and complete previous operation
    _debounceTimer?.cancel();

    // Complete the previous completer with false (cancelled) if it exists
    if (_currentCompleter != null && !_currentCompleter!.isCompleted) {
      _currentCompleter!.complete(false);
    }

    // 2. LATEST-WINS: Increment operation ID (invalidates previous operations)
    final operationId = ++_currentOperationId;
    AppLogger.debug('Starting subscription sync operation $operationId');

    // 3. MUTEX: The operation ID acts as our mutex - only current operation proceeds
    final completer = Completer<bool>();
    _currentCompleter = completer;

    _debounceTimer = Timer(_debounceDelay, () async {
      AppLogger.debug(
        'Executing debounced subscription sync operation $operationId',
      );
      final result = await _performSync(operationId, unsubscribeOthers);

      // Only complete if this completer is still current and not already completed
      if (_currentCompleter == completer && !completer.isCompleted) {
        completer.complete(result);
      }
    });

    return completer.future;
  }

  /// Perform the actual sync operation with cancellation checks
  Future<bool> _performSync(int operationId, bool unsubscribeOthers) async {
    try {
      // Check if we're still the current operation
      if (_currentOperationId != operationId) {
        AppLogger.debug('Sync operation $operationId cancelled before start');
        return false;
      }

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

      // Check again after reading state
      if (_currentOperationId != operationId) {
        AppLogger.debug('Sync operation $operationId cancelled during setup');
        return false;
      }

      if (topicToSubscribe != null) {
        await _firebaseMessaging.subscribeToTopic(topicToSubscribe);
        AppLogger.debug('Subscribed to $topicToSubscribe');
      }

      // Check after subscribe operation
      if (_currentOperationId != operationId) {
        AppLogger.debug(
          'Sync operation $operationId cancelled after subscribe',
        );
        return false;
      }

      // Optionally unsubscribe from other topics (e.g., when settings change)
      if (unsubscribeOthers) {
        // Get all topics and process them with cancellation checks
        final allTopics = _getAllPossibleTopics();
        for (final topic in allTopics) {
          // Check before each unsubscribe operation
          if (_currentOperationId != operationId) {
            AppLogger.debug(
              'Sync operation $operationId cancelled during unsubscribe loop',
            );
            return false;
          }

          if (topicToSubscribe == null || topic != topicToSubscribe) {
            await _firebaseMessaging.unsubscribeFromTopic(topic);
            AppLogger.debug('Unsubscribed from $topic');
          }
        }
      }

      AppLogger.debug('Sync operation $operationId completed successfully');
      return true;
    } catch (e) {
      AppLogger.warn('Sync operation $operationId failed: $e');
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
        firebaseMessaging: FirebaseMessaging.instance,
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

  const SubscriptionPromptState({
    this.isSubscribed = false,
    this.hasUserMadeChoice = false,
    this.shouldShowPrompt = false,
  });

  SubscriptionPromptState copyWith({
    bool? isSubscribed,
    bool? hasUserMadeChoice,
    bool? shouldShowPrompt,
  }) {
    return SubscriptionPromptState(
      isSubscribed: isSubscribed ?? this.isSubscribed,
      hasUserMadeChoice: hasUserMadeChoice ?? this.hasUserMadeChoice,
      shouldShowPrompt: shouldShowPrompt ?? this.shouldShowPrompt,
    );
  }

  /// Early exit: should we skip all prompt logic?
  /// Skip if user has already made a choice (subscribed or declined)
  bool get shouldSkipPromptLogic => hasUserMadeChoice;
}

/// High-performance subscription prompt state manager
class SubscriptionPromptNotifier
    extends StateNotifier<SubscriptionPromptState> {
  SubscriptionPromptNotifier(
    this._subscriptionNotifier, {
    required this.remoteConfigValues,
  }) : super(const SubscriptionPromptState()) {
    _initializeState();
  }

  final SubscriptionNotifier _subscriptionNotifier;
  final RemoteConfigValues remoteConfigValues;

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
      AppLogger.warn('Failed to initialize subscription prompt state: $e');
    }
  }

  /// Consider showing the prompt immediately based on jokes-viewed threshold
  void considerPromptAfterJokeViewed(int jokesViewedCount) {
    // Always check the current subscription state from the underlying notifier
    // to ensure we have the latest information (e.g., if user subscribed from settings)
    final currentSubscriptionState = _subscriptionNotifier.state;
    final hasUserMadeChoice = _subscriptionNotifier.hasUserMadeChoice();

    // Update our state to reflect the current subscription state
    state = state.copyWith(
      isSubscribed: currentSubscriptionState.isSubscribed,
      hasUserMadeChoice: hasUserMadeChoice,
    );

    // Skip if user has already made a choice or prompt already pending/shown
    if (state.shouldSkipPromptLogic || state.shouldShowPrompt) {
      return;
    }

    final int threshold = remoteConfigValues.getInt(
      RemoteParam.subscriptionPromptMinJokesViewed,
    );
    if (jokesViewedCount >= threshold) {
      state = state.copyWith(shouldShowPrompt: true);
    }
  }

  /// Handle subscription (user clicked "Subscribe")
  Future<bool> subscribeUser() async {
    final success = await _subscriptionNotifier.subscribeWithPermission();
    if (success) {
      state = state.copyWith(
        isSubscribed: true,
        hasUserMadeChoice: true,
        shouldShowPrompt: false,
      );
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
    state = state.copyWith(shouldShowPrompt: false);
  }
}

/// Provider for subscription prompt state management
final subscriptionPromptProvider =
    StateNotifierProvider<SubscriptionPromptNotifier, SubscriptionPromptState>((
      ref,
    ) {
      final subscriptionNotifier = ref.watch(subscriptionProvider.notifier);
      final rcValues = ref.watch(remoteConfigValuesProvider);
      return SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: rcValues,
      );
    });
