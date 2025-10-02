import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

/// Coordinates eligibility checks and attempts an in-app review prompt
class ReviewPromptCoordinator {
  ReviewPromptCoordinator({
    required RemoteConfigValues Function() getRemoteValues,
    required AppUsageService appUsageService,
    required AppReviewService appReviewService,
    required ReviewPromptStateStore stateStore,
    required bool Function() getIsDailySubscribed,
  }) : _getRemoteValues = getRemoteValues,
       _usage = appUsageService,
       _review = appReviewService,
       _store = stateStore,
       _getIsDailySubscribed = getIsDailySubscribed;

  final RemoteConfigValues Function() _getRemoteValues;
  final AppUsageService _usage;
  final AppReviewService _review;
  final ReviewPromptStateStore _store;
  final bool Function() _getIsDailySubscribed;

  Future<void> maybePromptForReview({
    required ReviewRequestSource source,
    required BuildContext context,
  }) async {
    try {
      AppLogger.debug('REVIEW_COORDINATOR maybePromptForReview');

      // Early out if previously requested
      if (await _store.hasRequested()) {
        AppLogger.debug(
          'REVIEW_COORDINATOR maybePromptForReview already requested',
        );
        return;
      }

      // Read thresholds (synchronous, default-safe)
      final rv = _getRemoteValues();
      final int minDays = rv.getInt(RemoteParam.reviewMinDaysUsed);
      final int minSaved = rv.getInt(RemoteParam.reviewMinSavedJokes);
      final int minShared = rv.getInt(RemoteParam.reviewMinSharedJokes);
      final int minViewed = rv.getInt(RemoteParam.reviewMinViewedJokes);
      final bool requireDailySub = rv.getBool(
        RemoteParam.reviewRequireDailySubscription,
      );

      // Read usage (fast SharedPreferences reads)
      final days = await _usage.getNumDaysUsed();
      final saved = await _usage.getNumSavedJokes();
      final shared = await _usage.getNumSharedJokes();
      final viewed = await _usage.getNumJokesViewed();

      final subscriptionRequirementPassed = requireDailySub
          ? _getIsDailySubscribed()
          : true;

      final eligible =
          days >= minDays &&
          saved >= minSaved &&
          shared >= minShared &&
          viewed >= minViewed &&
          subscriptionRequirementPassed;
      if (!eligible) return;

      AppLogger.debug(
        'REVIEW_COORDINATOR maybePromptForReview requesting review',
      );
      // The review service is responsible for marking attempts
      if (context.mounted) {
        await _review.requestReview(source: source, context: context);
      }
    } catch (e) {
      AppLogger.warn('REVIEW_COORDINATOR maybePromptForReview error: $e');
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
    getIsDailySubscribed: () => ref.read(isSubscribedProvider),
  );
});
