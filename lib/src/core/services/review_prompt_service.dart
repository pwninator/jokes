import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

part 'review_prompt_service.g.dart';

@Riverpod(keepAlive: true)
ReviewPromptCoordinator reviewPromptCoordinator(Ref ref) {
  final remoteConfigValues = ref.read(remoteConfigValuesProvider);
  final appReviewService = ref.read(appReviewServiceProvider);
  final stateStore = ref.read(reviewPromptStateStoreProvider);
  final isDailySubscribed = ref.read(isSubscribedProvider);
  final isAdmin = ref.read(isAdminProvider);
  return ReviewPromptCoordinator(
    getRemoteValues: () => remoteConfigValues,
    appReviewService: appReviewService,
    stateStore: stateStore,
    getIsDailySubscribed: () => isDailySubscribed,
    getIsAdmin: () => isAdmin,
  );
}

/// Coordinates eligibility checks and attempts an in-app review prompt
class ReviewPromptCoordinator {
  ReviewPromptCoordinator({
    required RemoteConfigValues Function() getRemoteValues,
    required AppReviewService appReviewService,
    required ReviewPromptStateStore stateStore,
    required bool Function() getIsDailySubscribed,
    required bool Function() getIsAdmin,
  }) : _getRemoteValues = getRemoteValues,
       _reviewService = appReviewService,
       _store = stateStore,
       _getIsDailySubscribed = getIsDailySubscribed,
       _getIsAdmin = getIsAdmin;

  final RemoteConfigValues Function() _getRemoteValues;
  final AppReviewService _reviewService;
  final ReviewPromptStateStore _store;
  final bool Function() _getIsDailySubscribed;
  final bool Function() _getIsAdmin;

  Future<void> maybePromptForReview({
    required int numDaysUsed,
    required int numSavedJokes,
    required int numSharedJokes,
    required int numJokesViewed,
    required ReviewRequestSource source,
    required BuildContext context,
  }) async {
    try {
      AppLogger.debug('REVIEW_COORDINATOR maybePromptForReview');

      final isAdmin = _getIsAdmin();
      if (isAdmin) {
        AppLogger.debug(
          'REVIEW_COORDINATOR maybePromptForReview skipped for admin user',
        );
        return;
      }

      // Early out if previously requested
      if (_store.hasRequested()) {
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

      final subscriptionRequirementPassed = requireDailySub
          ? _getIsDailySubscribed()
          : true;

      final eligible =
          numDaysUsed >= minDays &&
          numSavedJokes >= minSaved &&
          numSharedJokes >= minShared &&
          numJokesViewed >= minViewed &&
          subscriptionRequirementPassed;
      if (!eligible) return;

      AppLogger.debug(
        'REVIEW_COORDINATOR maybePromptForReview requesting review',
      );
      // The review service is responsible for marking attempts
      if (context.mounted) {
        await _reviewService.requestReview(source: source, context: context);
      }
    } catch (e) {
      AppLogger.warn('REVIEW_COORDINATOR maybePromptForReview error: $e');
    }
  }
}
