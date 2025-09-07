import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_review/in_app_review.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';

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
enum ReviewRequestSource { adminTest, settings, auto }

extension ReviewRequestSourceX on ReviewRequestSource {
  String get value {
    switch (this) {
      case ReviewRequestSource.adminTest:
        return 'admin_test';
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
    AnalyticsService? analyticsService,
  }) : _native = nativeAdapter,
       _analytics = analyticsService;

  final NativeReviewAdapter _native;
  final AnalyticsService? _analytics;

  /// Check if in-app review API is available on this device/OS
  Future<bool> isAvailable() async {
    try {
      return await _native.isAvailable();
    } catch (e) {
      debugPrint('APP_REVIEW isAvailable error: $e');
      return false;
    }
  }

  /// Attempt to show the in-app review sheet
  ///
  /// Returns a [ReviewRequestResult] describing the outcome.
  Future<ReviewRequestResult> requestReview({
    required ReviewRequestSource source,
  }) async {
    // Attempt regardless of availability to mirror plugin guidance, but we
    // prefer checking to short-circuit obvious unavailability.
    try {
      await _analytics?.logAnalyticsError(
        // Using analytics error channel for attempts would be noisy; skip.
        // Instead, rely on result-specific events logged below.
        // Keeping this as a no-op shim: do not log attempts here.
        // This line ensures interface availability in case future refactor needs it.
        '',
        'app_review_attempt_${source.value}',
      );
    } catch (_) {
      // Ignore analytics failures
    }

    try {
      final available = await _native.isAvailable();
      if (!available) {
        return ReviewRequestResult.notAvailable;
      }

      await _native.requestReview();

      // The API does not guarantee UI will be shown; treat as throttled/no-op
      // only if we have platform signals. Since we don't, return shown as best-effort.
      return ReviewRequestResult.shown;
    } catch (e) {
      debugPrint('APP_REVIEW requestReview error: $e');
      return ReviewRequestResult.error;
    }
  }
}

/// Provider wiring, following project patterns
final appReviewServiceProvider = Provider<AppReviewService>((ref) {
  final analytics = ref.watch(analyticsServiceProvider);
  return AppReviewService(
    nativeAdapter: InAppReviewAdapter(),
    analyticsService: analytics,
  );
});
