import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';

/// Provider for AppUsageService using the shared preferences instance provider
final appUsageServiceProvider = Provider<AppUsageService>((ref) {
  final sharedPreferences = ref.watch(sharedPreferencesInstanceProvider);
  return AppUsageService(prefs: sharedPreferences);
});

/// Service responsible for tracking local app usage metrics via SharedPreferences
class AppUsageService {
  AppUsageService({required SharedPreferences prefs}) : _prefs = prefs;

  final SharedPreferences _prefs;

  // Preference keys
  static const String _firstUsedDateKey = 'first_used_date';
  static const String _lastUsedDateKey = 'last_used_date';
  static const String _numDaysUsedKey = 'num_days_used';
  static const String _numJokesViewedKey = 'num_jokes_viewed';

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
    if (shouldSetFirstUsed) {
      await _prefs.setString(_firstUsedDateKey, today);
    }
    if (shouldIncrementDays) {
      await _prefs.setInt(_numDaysUsedKey, newNumDaysUsed);
    }
    await _prefs.setString(_lastUsedDateKey, newLastUsed);

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
    debugPrint(
      'APP_USAGE logJokeViewed: { num_jokes_viewed: $oldCount -> $newCount }',
    );
  }

  /// Getters to read metrics (useful for UI and tests)
  Future<String?> getFirstUsedDate() async =>
      _prefs.getString(_firstUsedDateKey);

  Future<String?> getLastUsedDate() async => _prefs.getString(_lastUsedDateKey);

  Future<int> getNumDaysUsed() async => _prefs.getInt(_numDaysUsedKey) ?? 0;

  Future<int> getNumJokesViewed() async =>
      _prefs.getInt(_numJokesViewedKey) ?? 0;

  // Returns today's date as yyyy-MM-dd in local time
  String _formatTodayDate() {
    final DateTime now = DateTime.now();
    final String year = now.year.toString();
    final String month = now.month.toString().padLeft(2, '0');
    final String day = now.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }
}
