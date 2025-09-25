import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_review/in_app_review.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Outcome of attempting to request an in-app review
enum ReviewRequestResult {
  /// The native in-app review sheet was shown to the user
  shown,

  /// The API was unavailable on this device/OS
  notAvailable,

  /// The call was accepted but the system did not show UI (rate-limited/no-op)
  throttledOrNoop,

  /// An error occurred while attempting to request a review
  error,
}

/// Source of the review request for analytics/telemetry
enum ReviewRequestSource {
  adminTest,
  jokeViewed,
  jokeSaved,
  jokeShared,
  settings,
  auto
}

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
      case ReviewRequestSource.settings:
        return 'settings';
      case ReviewRequestSource.auto:
        return 'auto';
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
    AnalyticsService? analyticsService,
  }) : _native = nativeAdapter,
       _store = stateStore,
       _analytics = analyticsService;

  final NativeReviewAdapter _native;
  final ReviewPromptStateStore _store;
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
  /// Returns the outcome of the request. Internally marks the request as
  /// attempted when native API is available (regardless of success/error).
  Future<ReviewRequestResult> requestReview({
    required ReviewRequestSource source,
    bool force = false,
  }) async {
    // Attempt regardless of availability to mirror plugin guidance, but we
    // prefer checking to short-circuit obvious unavailability.
    _analytics?.logAppReviewAttempt(source: source.value);

    try {
      final available = await _native.isAvailable();
      if (!available) {
        return ReviewRequestResult.notAvailable;
      }

      await _native.requestReview();
      // Mark that we attempted to show the native review sheet
      try {
        await _store.markRequested();
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
    analyticsService: analytics,
  );
});
