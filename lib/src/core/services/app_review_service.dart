import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:in_app_review/in_app_review.dart';
import 'package:snickerdoodle/src/common_widgets/app_review_prompt_dialog.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

enum _DialogDecision { accept, dismiss, feedback }

/// Outcome of attempting to request an in-app review
enum ReviewRequestResult {
  /// The native in-app review sheet was shown to the user
  shown,

  /// The API was unavailable on this device/OS
  notAvailable,

  /// The user dismissed the dialog
  dismissed,

  /// An error occurred while attempting to request a review
  error,
}

/// Source of the review request for analytics/telemetry
enum ReviewRequestSource { adminTest, jokeViewed, jokeSaved, jokeShared }

extension ReviewRequestSourceX on ReviewRequestSource {
  String get value {
    switch (this) {
      case ReviewRequestSource.adminTest:
        return 'admin_test';
      case ReviewRequestSource.jokeViewed:
        return 'joke_viewed';
      case ReviewRequestSource.jokeSaved:
        return 'joke_saved';
      case ReviewRequestSource.jokeShared:
        return 'joke_shared';
    }
  }
}

/// Lightweight adapter for the in_app_review plugin to keep it mockable in tests
abstract class NativeReviewAdapter {
  Future<bool> isAvailable();
  Future<void> requestReview();
}

class InAppReviewAdapter implements NativeReviewAdapter {
  InAppReviewAdapter([InAppReview? instance])
    : _inAppReview = instance ?? InAppReview.instance;

  final InAppReview _inAppReview;

  @override
  Future<bool> isAvailable() => _inAppReview.isAvailable();

  @override
  Future<void> requestReview() => _inAppReview.requestReview();
}

/// Service encapsulating in-app review behavior with analytics hooks
class AppReviewService {
  AppReviewService({
    required NativeReviewAdapter nativeAdapter,
    required ReviewPromptStateStore stateStore,
    required ReviewPromptVariant Function() getReviewPromptVariant,
    AnalyticsService? analyticsService,
  }) : _native = nativeAdapter,
       _promptHistoryStore = stateStore,
       _getReviewPromptVariant = getReviewPromptVariant,
       _analytics = analyticsService;

  final NativeReviewAdapter _native;
  final ReviewPromptStateStore _promptHistoryStore;
  final ReviewPromptVariant Function() _getReviewPromptVariant;
  final AnalyticsService? _analytics;

  /// Check if in-app review API is available on this device/OS
  Future<bool> isAvailable() async {
    try {
      return await _native.isAvailable();
    } catch (e) {
      AppLogger.warn('APP_REVIEW isAvailable error: $e');
      // Log analytics/crash for availability check failure
      try {
        _analytics?.logErrorAppReviewAvailability(
          source: 'service',
          errorMessage: 'app_review_is_available_failed',
        );
      } catch (_) {}
      return false;
    }
  }

  /// Attempt to show the in-app review sheet
  ///
  /// Shows a custom dialog first before the native review sheet.
  ///
  /// Returns the outcome of the request. Internally marks the request as
  /// attempted when native API is available (regardless of success/error).
  Future<ReviewRequestResult> requestReview({
    required ReviewRequestSource source,
    required BuildContext context,
    bool force = false,
  }) async {
    try {
      // Check availability first
      final available = await _native.isAvailable();
      if (!available) {
        return ReviewRequestResult.notAvailable;
      }

      if (!context.mounted) {
        return ReviewRequestResult.error;
      }

      // Show custom dialog first
      final variant = _getReviewPromptVariant();
      _analytics?.logAppReviewAttempt(
        source: source.value,
        variant: variant.name,
      );

      // Dialog now can signal three intents via callbacks; wire to pop values
      final userDecision = await showDialog<_DialogDecision>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => AppReviewPromptDialog(
          variant: variant,
          onAccept: () {
            Navigator.of(dialogContext).pop(_DialogDecision.accept);
          },
          onDismiss: () {
            Navigator.of(dialogContext).pop(_DialogDecision.dismiss);
          },
          onFeedback: () {
            Navigator.of(dialogContext).pop(_DialogDecision.feedback);
          },
        ),
      );

      if (userDecision == _DialogDecision.dismiss) {
        // User dismissed dialog
        _analytics?.logAppReviewDeclined(
          source: source.value,
          variant: variant.name,
        );
        return ReviewRequestResult.dismissed;
      }

      if (userDecision == _DialogDecision.feedback) {
        // Navigate to feedback screen using the caller's context (GoRouter)
        try {
          if (context.mounted) {
            // Use context extension to ensure push happens on the correct navigator
            await context.pushNamed(RouteNames.feedback);
          }
        } catch (_) {}
        return ReviewRequestResult.dismissed;
      }

      // User accepted - log and show native review
      _analytics?.logAppReviewAccepted(
        source: source.value,
        variant: variant.name,
      );

      await _native.requestReview();
      // Mark that we attempted to show the native review sheet
      try {
        await _promptHistoryStore.markRequested();
      } catch (_) {}

      // The API does not guarantee UI will be shown; return shown as best-effort.
      return ReviewRequestResult.shown;
    } catch (e) {
      AppLogger.warn('APP_REVIEW requestReview error: $e');
      // Log analytics/crash for request review failure
      try {
        _analytics?.logErrorAppReviewRequest(
          source: source.value,
          errorMessage: 'app_review_request_failed',
        );
      } catch (_) {}
      return ReviewRequestResult.error;
    }
  }
}

/// Provider wiring, following project patterns
final appReviewServiceProvider = Provider<AppReviewService>((ref) {
  final analytics = ref.watch(analyticsServiceProvider);
  final stateStore = ref.watch(reviewPromptStateStoreProvider);
  return AppReviewService(
    nativeAdapter: InAppReviewAdapter(),
    stateStore: stateStore,
    getReviewPromptVariant: () {
      final remoteValues = ref.read(remoteConfigValuesProvider);
      return remoteValues.getEnum<ReviewPromptVariant>(
        RemoteParam.reviewPromptVariant,
      );
    },
    analyticsService: analytics,
  );
});
