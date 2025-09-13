import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

/// Coordinates eligibility checks and attempts an in-app review prompt
class ReviewPromptCoordinator {
  ReviewPromptCoordinator({
    required RemoteConfigValues Function() getRemoteValues,
    required AppUsageService appUsageService,
    required AppReviewService appReviewService,
    required ReviewPromptStateStore stateStore,
  }) : _getRemoteValues = getRemoteValues,
       _usage = appUsageService,
       _review = appReviewService,
       _store = stateStore;

  final RemoteConfigValues Function() _getRemoteValues;
  final AppUsageService _usage;
  final AppReviewService _review;
  final ReviewPromptStateStore _store;

  Future<void> maybePromptForReview({
    required ReviewRequestSource source,
  }) async {
    try {
      debugPrint('REVIEW_COORDINATOR maybePromptForReview');

      // Early out if previously requested
      if (await _store.hasRequested()) {
        debugPrint('REVIEW_COORDINATOR maybePromptForReview already requested');
        return;
      }

      // Read thresholds (synchronous, default-safe)
      final rv = _getRemoteValues();
      final int minDays = rv.getInt(RemoteParam.reviewMinDaysUsed);
      final int minSaved = rv.getInt(RemoteParam.reviewMinSavedJokes);
      final int minShared = rv.getInt(RemoteParam.reviewMinSharedJokes);

      // Read usage (fast SharedPreferences reads)
      final days = await _usage.getNumDaysUsed();
      final saved = await _usage.getNumSavedJokes();
      final shared = await _usage.getNumSharedJokes();

      final eligible =
          days >= minDays && saved >= minSaved && shared >= minShared;
      if (!eligible) return;

      debugPrint('REVIEW_COORDINATOR maybePromptForReview requesting review');
      // Respect the requirement to mark only when native is attempted
      final response = await _review.requestReview(source: source);
      if (response.nativeAttempted) {
        await _store.markRequested();
      }
    } catch (e) {
      debugPrint('REVIEW_COORDINATOR maybePromptForReview error: $e');
    }
  }
}

final reviewPromptCoordinatorProvider = Provider<ReviewPromptCoordinator>((
  ref,
) {
  final usage = ref.watch(appUsageServiceProvider);
  final review = ref.watch(appReviewServiceProvider);
  final store = ref.watch(reviewPromptStateStoreProvider);
  return ReviewPromptCoordinator(
    getRemoteValues: () => ref.read(remoteConfigValuesProvider),
    appUsageService: usage,
    appReviewService: review,
    stateStore: store,
  );
});
