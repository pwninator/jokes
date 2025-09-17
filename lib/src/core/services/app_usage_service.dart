import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

/// Provider for AppUsageService using the shared preferences instance provider
final appUsageServiceProvider = Provider<AppUsageService>((ref) {
  final sharedPreferences = ref.watch(sharedPreferencesInstanceProvider);
  final analyticsService = ref.watch(analyticsServiceProvider);
  final jokeCloudFn = ref.watch(jokeCloudFunctionServiceProvider);
  return AppUsageService(
    prefs: sharedPreferences,
    analyticsService: analyticsService,
    ref: ref,
    jokeCloudFn: jokeCloudFn,
    isDebugMode: kDebugMode,
  );
});

/// Service responsible for tracking local app usage metrics via SharedPreferences
class AppUsageService {
  AppUsageService({
    required SharedPreferences prefs,
    AnalyticsService? analyticsService,
    Ref? ref,
    JokeCloudFunctionService? jokeCloudFn,
    bool? isDebugMode,
  }) : _prefs = prefs,
       _analyticsService = analyticsService,
       _ref = ref,
       _jokeCloudFn = jokeCloudFn ?? JokeCloudFunctionService(),
       _isDebugMode = isDebugMode;

  final SharedPreferences _prefs;
  final AnalyticsService? _analyticsService;
  final Ref? _ref;
  final JokeCloudFunctionService _jokeCloudFn;
  final bool? _isDebugMode;

  // Preference keys
  static const String _firstUsedDateKey = 'first_used_date';
  static const String _lastUsedDateKey = 'last_used_date';
  static const String _numDaysUsedKey = 'num_days_used';
  static const String _numJokesViewedKey = 'num_jokes_viewed';
  static const String _numSavedJokesKey = 'num_saved_jokes';
  static const String _numSharedJokesKey = 'num_shared_jokes';

  /// Log app usage for the current launch.
  ///
  /// - Sets `first_used_date` if it does not exist
  /// - Updates `last_used_date` to today on every call
  /// - Increments `num_days_used` if the last used date is not today
  Future<void> logAppUsage() async {
    final String today = _formatTodayDate();

    // Capture current values
    final String? oldFirstUsed = _prefs.getString(_firstUsedDateKey);
    final String? oldLastUsed = _prefs.getString(_lastUsedDateKey);
    final int oldNumDaysUsed = _prefs.getInt(_numDaysUsedKey) ?? 0;

    // Compute new values
    final bool shouldSetFirstUsed =
        (oldFirstUsed == null || oldFirstUsed.isEmpty);
    final bool shouldIncrementDays =
        (oldLastUsed == null || oldLastUsed != today);
    final int newNumDaysUsed = oldNumDaysUsed + (shouldIncrementDays ? 1 : 0);
    final String newLastUsed = today;

    // Persist changes
    await _prefs.setString(_lastUsedDateKey, newLastUsed);
    if (shouldSetFirstUsed) {
      await _prefs.setString(_firstUsedDateKey, today);
    }
    if (shouldIncrementDays) {
      await _prefs.setInt(_numDaysUsedKey, newNumDaysUsed);
      // Notify listeners that usage changed
      _notifyUsageChanged();

      // Fire-and-forget analytics + backend usage snapshot
      final service = _analyticsService;
      if (service != null) {
        try {
          service.logAppUsageDayIncremented(numDaysUsed: newNumDaysUsed);
        } catch (e) {
          debugPrint('APP_USAGE analytics error: $e');
        }
      }
      // Do not await remote sync to keep UI responsive
      _pushUsageSnapshot();
    }

    // Single debug print summarizing modifications
    final List<String> changes = [];
    changes.add('first_used_date: ${oldFirstUsed ?? '(null)'} -> $today');
    changes.add('last_used_date: ${oldLastUsed ?? '(null)'} -> $newLastUsed');
    changes.add('num_days_used: $oldNumDaysUsed -> $newNumDaysUsed');
    debugPrint('APP_USAGE logAppUsage: { ${changes.join(', ')} }');
  }

  /// Increment the number of jokes viewed counter.
  ///
  /// The caller should ensure business rules are satisfied
  /// (e.g., both setup and punchline images viewed for at least 2 seconds each).
  Future<void> logJokeViewed() async {
    final int oldCount = _prefs.getInt(_numJokesViewedKey) ?? 0;
    final int newCount = oldCount + 1;
    await _prefs.setInt(_numJokesViewedKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    debugPrint(
      'APP_USAGE logJokeViewed: { num_jokes_viewed: $oldCount -> $newCount }',
    );
  }

  /// Increment the number of saved jokes counter (on save).
  Future<void> incrementSavedJokesCount() async {
    final int oldCount = _prefs.getInt(_numSavedJokesKey) ?? 0;
    final int newCount = oldCount + 1;
    await _prefs.setInt(_numSavedJokesKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    debugPrint(
      'APP_USAGE incrementSavedJokesCount: { num_saved_jokes: $oldCount -> $newCount }',
    );
  }

  /// Decrement the number of saved jokes counter (on unsave). Floors at 0.
  Future<void> decrementSavedJokesCount() async {
    final int oldCount = _prefs.getInt(_numSavedJokesKey) ?? 0;
    final int newCount = (oldCount > 0) ? oldCount - 1 : 0;
    await _prefs.setInt(_numSavedJokesKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    debugPrint(
      'APP_USAGE decrementSavedJokesCount: { num_saved_jokes: $oldCount -> $newCount }',
    );
  }

  /// Increment the number of shared jokes counter (on successful share).
  Future<void> incrementSharedJokesCount() async {
    final int oldCount = _prefs.getInt(_numSharedJokesKey) ?? 0;
    final int newCount = oldCount + 1;
    await _prefs.setInt(_numSharedJokesKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    debugPrint(
      'APP_USAGE incrementSharedJokesCount: { num_shared_jokes: $oldCount -> $newCount }',
    );
  }

  /// Getters to read metrics (useful for UI and tests)
  Future<String?> getFirstUsedDate() async =>
      _prefs.getString(_firstUsedDateKey);

  Future<String?> getLastUsedDate() async => _prefs.getString(_lastUsedDateKey);

  Future<int> getNumDaysUsed() async => _prefs.getInt(_numDaysUsedKey) ?? 0;

  Future<int> getNumJokesViewed() async =>
      _prefs.getInt(_numJokesViewedKey) ?? 0;

  Future<int> getNumSavedJokes() async => _prefs.getInt(_numSavedJokesKey) ?? 0;

  Future<int> getNumSharedJokes() async =>
      _prefs.getInt(_numSharedJokesKey) ?? 0;

  /// Setters to directly override metrics (admin/testing tools)
  Future<void> setFirstUsedDate(String? date) async {
    if (date == null || date.isEmpty) {
      await _prefs.remove(_firstUsedDateKey);
    } else {
      await _prefs.setString(_firstUsedDateKey, date);
    }
    _notifyUsageChanged();
  }

  Future<void> setLastUsedDate(String? date) async {
    if (date == null || date.isEmpty) {
      await _prefs.remove(_lastUsedDateKey);
    } else {
      await _prefs.setString(_lastUsedDateKey, date);
    }
    _notifyUsageChanged();
  }

  Future<void> setNumDaysUsed(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _prefs.setInt(_numDaysUsedKey, sanitized);
    _notifyUsageChanged();
  }

  Future<void> setNumJokesViewed(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _prefs.setInt(_numJokesViewedKey, sanitized);
    _notifyUsageChanged();
  }

  Future<void> setNumSavedJokes(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _prefs.setInt(_numSavedJokesKey, sanitized);
    _notifyUsageChanged();
  }

  Future<void> setNumSharedJokes(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _prefs.setInt(_numSharedJokesKey, sanitized);
    _notifyUsageChanged();
  }

  // Returns today's date as yyyy-MM-dd in local time
  String _formatTodayDate() {
    final DateTime now = DateTime.now();
    final String year = now.year.toString();
    final String month = now.month.toString().padLeft(2, '0');
    final String day = now.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  void _notifyUsageChanged() {
    try {
      final notifier = _ref?.read(appUsageEventsProvider.notifier);
      if (notifier != null) notifier.state++;
    } catch (_) {}
  }

  Future<void> _pushUsageSnapshot() async {
    try {
      // Skip backend sync in debug mode or for admin users (mirrors analytics behavior)
      final bool isAdmin = _ref?.read(isAdminProvider) ?? false;
      if ((_isDebugMode ?? kDebugMode) || isAdmin) {
        debugPrint(
          'APP_USAGE SKIPPED (${isAdmin ? 'ADMIN' : 'DEBUG'}): trackUsage snapshot not sent',
        );
        return;
      }

      final futures = <Future<void>>[];
      final int numDaysUsed = await getNumDaysUsed();
      final int numSaved = await getNumSavedJokes();
      final int numViewed = await getNumJokesViewed();
      final int numShared = await getNumSharedJokes();
      final bool requestedReview =
          await _ref?.read(reviewPromptStateStoreProvider).hasRequested() ??
          false;
      futures.add(
        _jokeCloudFn
            .trackUsage(
              numDaysUsed: numDaysUsed,
              numSaved: numSaved,
              numViewed: numViewed,
              numShared: numShared,
              requestedReview: requestedReview,
            )
            .catchError((e, _) => debugPrint('APP_USAGE trackUsage error: $e')),
      );
      await Future.wait(futures);
    } catch (e) {
      debugPrint('APP_USAGE pushUsageSnapshot error: $e');
    }
  }
}
