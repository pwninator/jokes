import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/settings/application/brightness_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

part 'app_usage_service.g.dart';

@Riverpod(keepAlive: true)
AppUsageService appUsageService(Ref ref) {
  final settingsService = ref.read(settingsServiceProvider);
  final analyticsService = ref.read(analyticsServiceProvider);
  final jokeCloudFn = ref.read(jokeCloudFunctionServiceProvider);
  final categoryInteractionsService = ref.read(
    categoryInteractionsRepositoryProvider,
  );
  return AppUsageService(
    ref: ref,
    settingsService: settingsService,
    analyticsService: analyticsService,
    jokeCloudFn: jokeCloudFn,
    categoryInteractionsService: categoryInteractionsService,
    isDebugMode: kDebugMode,
  );
}

/// Service responsible for tracking local app usage metrics via SharedPreferences
class AppUsageService {
  AppUsageService({
    required Ref ref,
    required SettingsService settingsService,
    required AnalyticsService analyticsService,
    required JokeCloudFunctionService jokeCloudFn,
    required CategoryInteractionsRepository categoryInteractionsService,
    bool? isDebugMode,
  }) : _settings = settingsService,
       _analyticsService = analyticsService,
       _ref = ref,
       _jokeCloudFn = jokeCloudFn,
       _categoryInteractions = categoryInteractionsService,
       _isDebugMode = isDebugMode;

  final Ref _ref;
  final SettingsService _settings;
  final AnalyticsService _analyticsService;
  final JokeCloudFunctionService _jokeCloudFn;
  final CategoryInteractionsRepository _categoryInteractions;
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
    final String? oldFirstUsed = _settings.getString(_firstUsedDateKey);
    final String? oldLastUsed = _settings.getString(_lastUsedDateKey);
    final int oldNumDaysUsed = _settings.getInt(_numDaysUsedKey) ?? 0;

    // Compute new values
    final bool shouldSetFirstUsed =
        (oldFirstUsed == null || oldFirstUsed.isEmpty);
    final bool shouldIncrementDays =
        (oldLastUsed == null || oldLastUsed != today);
    final int newNumDaysUsed = oldNumDaysUsed + (shouldIncrementDays ? 1 : 0);
    final String newLastUsed = today;

    // Persist changes
    await _settings.setString(_lastUsedDateKey, newLastUsed);
    if (shouldSetFirstUsed) {
      await _settings.setString(_firstUsedDateKey, today);
    }
    if (shouldIncrementDays) {
      await _settings.setInt(_numDaysUsedKey, newNumDaysUsed);
      // Notify listeners that usage changed
      _notifyUsageChanged();

      // Fire-and-forget analytics + backend usage snapshot
      try {
        final brightness = _ref.read(brightnessProvider);
        _analyticsService.logAppUsageDays(
          numDaysUsed: newNumDaysUsed,
          brightness: brightness,
        );
      } catch (e) {
        AppLogger.warn('APP_USAGE analytics error: $e');
      }

      // Do not await remote sync to keep UI responsive
      _pushUsageSnapshot();
    }

    // Single debug print summarizing modifications
    final List<String> changes = [];
    changes.add('first_used_date: ${oldFirstUsed ?? '(null)'} -> $today');
    changes.add('last_used_date: ${oldLastUsed ?? '(null)'} -> $newLastUsed');
    changes.add('num_days_used: $oldNumDaysUsed -> $newNumDaysUsed');
    AppLogger.debug('APP_USAGE logAppUsage: { ${changes.join(', ')} }');
  }

  /// Increment the number of jokes viewed counter.
  ///
  /// The caller should ensure business rules are satisfied
  /// (e.g., both setup and punchline images viewed for at least 2 seconds each).
  Future<void> logJokeViewed() async {
    final int oldCount = _settings.getInt(_numJokesViewedKey) ?? 0;
    final int newCount = oldCount + 1;
    await _settings.setInt(_numJokesViewedKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    AppLogger.debug(
      'APP_USAGE logJokeViewed: { num_jokes_viewed: $oldCount -> $newCount }',
    );
  }

  /// Increment the number of saved jokes counter (on save).
  Future<void> incrementSavedJokesCount() async {
    final int oldCount = _settings.getInt(_numSavedJokesKey) ?? 0;
    final int newCount = oldCount + 1;
    await _settings.setInt(_numSavedJokesKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    AppLogger.debug(
      'APP_USAGE incrementSavedJokesCount: { num_saved_jokes: $oldCount -> $newCount }',
    );
  }

  /// Decrement the number of saved jokes counter (on unsave). Floors at 0.
  Future<void> decrementSavedJokesCount() async {
    final int oldCount = _settings.getInt(_numSavedJokesKey) ?? 0;
    final int newCount = (oldCount > 0) ? oldCount - 1 : 0;
    await _settings.setInt(_numSavedJokesKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    AppLogger.debug(
      'APP_USAGE decrementSavedJokesCount: { num_saved_jokes: $oldCount -> $newCount }',
    );
  }

  /// Increment the number of shared jokes counter (on successful share).
  Future<void> incrementSharedJokesCount() async {
    final int oldCount = _settings.getInt(_numSharedJokesKey) ?? 0;
    final int newCount = oldCount + 1;
    await _settings.setInt(_numSharedJokesKey, newCount);
    _notifyUsageChanged();

    // Fire-and-forget usage snapshot to backend
    _pushUsageSnapshot();
    AppLogger.debug(
      'APP_USAGE incrementSharedJokesCount: { num_shared_jokes: $oldCount -> $newCount }',
    );
  }

  /// Getters to read metrics (useful for UI and tests)
  Future<String?> getFirstUsedDate() async =>
      _settings.getString(_firstUsedDateKey);

  Future<String?> getLastUsedDate() async =>
      _settings.getString(_lastUsedDateKey);

  Future<int> getNumDaysUsed() async => _settings.getInt(_numDaysUsedKey) ?? 0;

  Future<int> getNumJokesViewed() async =>
      _settings.getInt(_numJokesViewedKey) ?? 0;

  Future<int> getNumSavedJokes() async =>
      _settings.getInt(_numSavedJokesKey) ?? 0;

  Future<int> getNumSharedJokes() async =>
      _settings.getInt(_numSharedJokesKey) ?? 0;

  /// Setters to directly override metrics (admin/testing tools)
  Future<void> setFirstUsedDate(String? date) async {
    if (date == null || date.isEmpty) {
      await _settings.remove(_firstUsedDateKey);
    } else {
      await _settings.setString(_firstUsedDateKey, date);
    }
    _notifyUsageChanged();
  }

  Future<void> setLastUsedDate(String? date) async {
    if (date == null || date.isEmpty) {
      await _settings.remove(_lastUsedDateKey);
    } else {
      await _settings.setString(_lastUsedDateKey, date);
    }
    _notifyUsageChanged();
  }

  Future<void> setNumDaysUsed(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _settings.setInt(_numDaysUsedKey, sanitized);
    _notifyUsageChanged();
  }

  Future<void> setNumJokesViewed(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _settings.setInt(_numJokesViewedKey, sanitized);
    _notifyUsageChanged();
  }

  Future<void> setNumSavedJokes(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _settings.setInt(_numSavedJokesKey, sanitized);
    _notifyUsageChanged();
  }

  Future<void> setNumSharedJokes(int value) async {
    final int sanitized = value < 0 ? 0 : value;
    await _settings.setInt(_numSharedJokesKey, sanitized);
    _notifyUsageChanged();
  }

  /// Record that a category has been viewed.
  /// Fire-and-forget: performs DB write and logs analytics without blocking caller.
  Future<void> logCategoryViewed(String categoryId) async {
    // Use microtask to avoid creating a pending Timer in widget tests
    scheduleMicrotask(() async {
      try {
        _analyticsService.logJokeCategoryViewed(categoryId: categoryId);
        await _categoryInteractions.setViewed(categoryId);
        AppLogger.debug(
          'APP_USAGE logCategoryViewed: { category_id: $categoryId }',
        );
      } catch (e) {
        AppLogger.warn('APP_USAGE logCategoryViewed error: $e');
      }
    });
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
      final notifier = _ref.read(appUsageEventsProvider.notifier);
      notifier.state++;
    } catch (_) {}
  }

  Future<void> _pushUsageSnapshot() async {
    try {
      // Skip backend sync in debug mode or for admin users (mirrors analytics behavior)
      final bool isAdmin = _ref.read(isAdminProvider);
      if ((_isDebugMode ?? kDebugMode) || isAdmin) {
        AppLogger.debug(
          'APP_USAGE SKIPPED (${isAdmin ? 'ADMIN' : 'DEBUG'}): trackUsage snapshot not sent',
        );
        return;
      }

      final futures = <Future<void>>[];
      final int numDaysUsed = await getNumDaysUsed();
      final int numSaved = await getNumSavedJokes();
      final int numViewed = await getNumJokesViewed();
      final int numShared = await getNumSharedJokes();
      final bool requestedReview = _ref
          .read(reviewPromptStateStoreProvider)
          .hasRequested();
      futures.add(
        _jokeCloudFn
            .trackUsage(
              numDaysUsed: numDaysUsed,
              numSaved: numSaved,
              numViewed: numViewed,
              numShared: numShared,
              requestedReview: requestedReview,
            )
            .catchError(
              (e, _) => AppLogger.warn('APP_USAGE trackUsage error: $e'),
            ),
      );
      await Future.wait(futures);
    } catch (e) {
      AppLogger.warn('APP_USAGE pushUsageSnapshot error: $e');
    }
  }
}
