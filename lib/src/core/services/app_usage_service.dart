import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
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
  final jokeInteractionsRepository = ref.read(
    jokeInteractionsRepositoryProvider,
  );
  final reviewPromptCoordinator = ref.read(reviewPromptCoordinatorProvider);
  return AppUsageService(
    ref: ref,
    settingsService: settingsService,
    analyticsService: analyticsService,
    jokeCloudFn: jokeCloudFn,
    categoryInteractionsService: categoryInteractionsService,
    jokeInteractionsRepository: jokeInteractionsRepository,
    reviewPromptCoordinator: reviewPromptCoordinator,
    isDebugMode: kDebugMode,
  );
}

/// Provider for checking if a joke is saved (reactive)
@Riverpod()
Stream<bool> isJokeSaved(Ref ref, String jokeId) {
  final interactions = ref.watch(jokeInteractionsRepositoryProvider);
  return interactions
      .watchJokeInteraction(jokeId)
      .map((ji) => ji?.savedTimestamp != null);
}

/// Provider for checking if a joke is shared (reactive)
@Riverpod()
Stream<bool> isJokeShared(Ref ref, String jokeId) {
  final interactions = ref.watch(jokeInteractionsRepositoryProvider);
  return interactions
      .watchJokeInteraction(jokeId)
      .map((ji) => ji?.sharedTimestamp != null);
}

/// Service responsible for tracking local app usage metrics via SharedPreferences
class AppUsageService {
  AppUsageService({
    required Ref ref,
    required SettingsService settingsService,
    required AnalyticsService analyticsService,
    required JokeCloudFunctionService jokeCloudFn,
    required CategoryInteractionsRepository categoryInteractionsService,
    required JokeInteractionsRepository jokeInteractionsRepository,
    required ReviewPromptCoordinator reviewPromptCoordinator,
    required bool isDebugMode,
  }) : _settings = settingsService,
       _analyticsService = analyticsService,
       _ref = ref,
       _jokeCloudFn = jokeCloudFn,
       _categoryInteractions = categoryInteractionsService,
       _jokeInteractions = jokeInteractionsRepository,
       _reviewPromptCoordinator = reviewPromptCoordinator,
       _isDebugMode = isDebugMode;

  final Ref _ref;
  final SettingsService _settings;
  final AnalyticsService _analyticsService;
  final JokeCloudFunctionService _jokeCloudFn;
  final CategoryInteractionsRepository _categoryInteractions;
  final JokeInteractionsRepository _jokeInteractions;
  final ReviewPromptCoordinator _reviewPromptCoordinator;
  final bool _isDebugMode;

  // Preference keys
  static const String _firstUsedDateKey = 'first_used_date';
  static const String _lastUsedDateKey = 'last_used_date';
  static const String _numDaysUsedKey = 'num_days_used';

  // ==============================
  // APP USAGE TRACKING
  // ==============================

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

  /// Get the first date the app was used (useful for UI and tests)
  Future<String?> getFirstUsedDate() async =>
      _settings.getString(_firstUsedDateKey);

  /// Get the last date the app was used (useful for UI and tests)
  Future<String?> getLastUsedDate() async =>
      _settings.getString(_lastUsedDateKey);

  /// Get the number of days the app has been used (useful for UI and tests)
  Future<int> getNumDaysUsed() async => _settings.getInt(_numDaysUsedKey) ?? 0;

  // ===============================
  // JOKE INTERACTIONS
  // ===============================

  // -------------------------------
  // JOKE VIEWS
  // -------------------------------

  /// Set the joke as viewed.
  ///
  /// The caller should ensure business rules are satisfied
  /// (e.g., both setup and punchline images viewed for at least 2 seconds each).
  Future<void> logJokeViewed(
    String jokeId, {
    required BuildContext context,
  }) async {
    try {
      final interaction = await _jokeInteractions.getJokeInteraction(jokeId);
      final alreadyViewed = interaction?.viewedTimestamp != null;
      if (alreadyViewed) {
        AppLogger.debug(
          'APP_USAGE logJokeViewed skipped (already viewed): { joke_id: $jokeId }',
        );
        return;
      }

      await _jokeInteractions.setViewed(jokeId);
      _notifyUsageChanged();
      _pushUsageSnapshot();
      AppLogger.debug('APP_USAGE logJokeViewed: { joke_id: $jokeId }');

      final subscriptionPromptShown = await _maybeShowSubscriptionPrompt();

      if (!subscriptionPromptShown && context.mounted) {
        await _maybeShowReviewPrompt(
          source: ReviewRequestSource.jokeViewed,
          context: context,
        );
      }
    } catch (e) {
      AppLogger.warn('APP_USAGE logJokeViewed DB error: $e');
    }
  }

  /// Get the number of jokes viewed
  Future<int> getNumJokesViewed() async =>
      await _jokeInteractions.countViewed();

  // -------------------------------
  // JOKE SAVES
  // -------------------------------

  /// Get the number of jokes saved (COUNT from DB)
  Future<int> getNumSavedJokes() async => await _jokeInteractions.countSaved();

  /// Get saved joke IDs ordered by the time they were saved.
  Future<List<String>> getSavedJokeIds() async {
    final rows = await _jokeInteractions.getSavedJokeInteractions();
    return rows.map((row) => row.jokeId).toList(growable: false);
  }

  /// Check if a joke is saved (READ from DB)
  Future<bool> isJokeSaved(String jokeId) async =>
      await _jokeInteractions.isJokeSaved(jokeId);

  /// Toggle a joke save (ADD if not present, REMOVE if present)
  /// Returns true if the joke was saved, false if it was unsaved
  Future<bool> toggleJokeSave(
    String jokeId, {
    required BuildContext context,
  }) async {
    final isSaved = await isJokeSaved(jokeId);
    if (isSaved) {
      await unsaveJoke(jokeId);
      return false;
    } else {
      await saveJoke(
        jokeId,
        context: context, // ignore: use_build_context_synchronously
      );
      return true;
    }
  }

  /// Save a joke (persists to DB)
  Future<void> saveJoke(String jokeId, {required BuildContext context}) async {
    try {
      await _jokeInteractions.setSaved(jokeId);
      _notifyUsageChanged();
      _pushUsageSnapshot();
      AppLogger.debug('APP_USAGE saveJoke: { joke_id: $jokeId }');
      if (context.mounted) {
        await _maybeShowReviewPrompt(
          source: ReviewRequestSource.jokeSaved,
          context: context,
        );
      }
    } catch (e) {
      AppLogger.warn('APP_USAGE saveJoke DB error: $e');
    }
  }

  /// Unsave a joke (persists to DB)
  Future<void> unsaveJoke(String jokeId) async {
    try {
      await _jokeInteractions.setUnsaved(jokeId);
      _notifyUsageChanged();
      _pushUsageSnapshot();
      AppLogger.debug('APP_USAGE unsaveJoke: { joke_id: $jokeId }');
    } catch (e) {
      AppLogger.warn('APP_USAGE unsaveJoke DB error: $e');
    }
  }

  // -------------------------------
  // JOKE SHARES
  // -------------------------------

  /// Share a joke (persists to DB)
  Future<void> shareJoke(String jokeId, {required BuildContext context}) async {
    try {
      await _jokeInteractions.setShared(jokeId);
      _notifyUsageChanged();
      _pushUsageSnapshot();
      AppLogger.debug('APP_USAGE shareJoke: { joke_id: $jokeId }');
      if (context.mounted) {
        await _maybeShowReviewPrompt(
          source: ReviewRequestSource.jokeShared,
          context: context,
        );
      }
    } catch (e) {
      AppLogger.warn('APP_USAGE shareJoke DB error: $e');
    }
  }

  /// Get the number of jokes shared (COUNT from DB)
  Future<int> getNumSharedJokes() async =>
      await _jokeInteractions.countShared();

  // ==============================
  // CATEGORY INTERACTIONS
  // ==============================

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

  // ==============================
  // METRICS SETTERS (Admin/Testing Tools)
  // ==============================

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

  // ==============================
  // PRIVATE HELPER METHODS
  // ==============================

  /// Shows subscription prompt if appropriate based on jokes viewed count.
  /// Returns true if a prompt was shown, false otherwise.
  Future<bool> _maybeShowSubscriptionPrompt() async {
    try {
      final jokesViewedCount = await _jokeInteractions.countViewed();
      final subscriptionPromptNotifier = _ref.read(
        subscriptionPromptProvider.notifier,
      );
      return subscriptionPromptNotifier.maybePromptAfterJokeViewed(
        jokesViewedCount,
      );
    } catch (e) {
      AppLogger.warn('APP_USAGE subscription prompt error: $e');
      return false;
    }
  }

  /// Shows review prompt if appropriate based on the source and context.
  /// Only shows if review prompts are enabled via remote config and context is mounted.
  Future<void> _maybeShowReviewPrompt({
    required ReviewRequestSource source,
    required BuildContext context,
  }) async {
    final numDaysUsed = await getNumDaysUsed();
    final numSavedJokes = await getNumSavedJokes();
    final numSharedJokes = await getNumSharedJokes();
    final numJokesViewed = await getNumJokesViewed();

    if (!context.mounted) {
      return;
    }

    final rv = _ref.read(remoteConfigValuesProvider);
    final reviewFromViewsEnabled = rv.getBool(
      RemoteParam.reviewRequestFromJokeViewed,
    );

    if (reviewFromViewsEnabled) {
      await _reviewPromptCoordinator.maybePromptForReview(
        numDaysUsed: numDaysUsed,
        numSavedJokes: numSavedJokes,
        numSharedJokes: numSharedJokes,
        numJokesViewed: numJokesViewed,
        source: source,
        context: context,
      );
    }
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
      if (_isDebugMode || isAdmin) {
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
