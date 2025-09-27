import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

import 'firebase_mocks.dart';

// Mock classes for analytics services
class MockAnalyticsService extends Mock implements AnalyticsService {}

/// Analytics-specific service mocks for unit tests
class AnalyticsMocks {
  static MockAnalyticsService? _mockAnalyticsService;

  /// Get or create mock analytics service
  static MockAnalyticsService get mockAnalyticsService {
    _mockAnalyticsService ??= MockAnalyticsService();
    _setupAnalyticsServiceDefaults(_mockAnalyticsService!);
    return _mockAnalyticsService!;
  }

  /// Register fallback values for mocktail
  static void registerFallbackValues() {
    registerFallbackValue(JokeViewerMode.reveal);
  }

  /// Reset all analytics mocks (call this in setUp if needed)
  static void reset() {
    _mockAnalyticsService = null;
  }

  /// Get analytics-specific provider overrides
  static List<Override> getAnalyticsProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock Firebase Analytics (required for analytics service)
      firebaseAnalyticsProvider.overrideWithValue(
        FirebaseMocks.mockFirebaseAnalytics,
      ),

      // Mock analytics service
      analyticsServiceProvider.overrideWithValue(mockAnalyticsService),

      // Add any additional overrides
      ...additionalOverrides,
    ];
  }

  static void _setupAnalyticsServiceDefaults(MockAnalyticsService mock) {
    // Setup default behaviors that won't throw
    when(() => mock.initialize()).thenAnswer((_) async {});

    when(() => mock.setUserProperties(any())).thenAnswer((_) async {});

    when(
      () => mock.logJokeSetupViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokePunchlineViewed(
        any(),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeViewed(
        any(),
        totalJokesViewed: any(named: 'totalJokesViewed'),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeNavigation(
        any(),
        any(),
        method: any(named: 'method'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeSaved(
        any(),
        jokeContext: any(named: 'jokeContext'),
        totalJokesSaved: any(named: 'totalJokesSaved'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeUnsaved(
        any(),
        jokeContext: any(named: 'jokeContext'),
        totalJokesSaved: any(named: 'totalJokesSaved'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeShareSuccess(
        any(),
        jokeContext: any(named: 'jokeContext'),
        shareDestination: any(named: 'shareDestination'),
        totalJokesShared: any(named: 'totalJokesShared'),
      ),
    ).thenAnswer((_) async {});

    // Similar search CTA
    when(
      () => mock.logJokeSearchSimilar(
        queryLength: any(named: 'queryLength'),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});

    // Feedback
    when(() => mock.logFeedbackSubmitted()).thenAnswer((_) async {});

    // New error/non-error APIs
    when(
      () => mock.logErrorAuthSignIn(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mock.logErrorSubscriptionToggle(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mock.logErrorSubscriptionTimeUpdate(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
    when(
      () =>
          mock.logErrorFeedbackSubmit(errorMessage: any(named: 'errorMessage')),
    ).thenAnswer((_) async {});
    when(
      () => mock.logAppReviewAttempt(source: any(named: 'source')),
    ).thenAnswer((_) async {});
    when(
      () => mock.logErrorAppReviewAvailability(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mock.logErrorAppReviewRequest(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    // Share funnel
    when(
      () => mock.logJokeShareInitiated(
        any(),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeShareCanceled(
        any(),
        jokeContext: any(named: 'jokeContext'),
        shareDestination: any(named: 'shareDestination'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorJokeShare(
        any(),
        jokeContext: any(named: 'jokeContext'),
        errorMessage: any(named: 'errorMessage'),
        errorContext: any(named: 'errorContext'),
        exceptionType: any(named: 'exceptionType'),
      ),
    ).thenAnswer((_) async {});

    when(() => mock.logSubscriptionOnSettings()).thenAnswer((_) async {});
    when(() => mock.logSubscriptionOnPrompt()).thenAnswer((_) async {});
    when(() => mock.logSubscriptionOffSettings()).thenAnswer((_) async {});
    when(
      () => mock.logSubscriptionTimeChanged(
        subscriptionHour: any(named: 'subscriptionHour'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mock.logSubscriptionDeclinedMaybeLater(),
    ).thenAnswer((_) async {});
    when(
      () => mock.logSubscriptionDeclinedPermissionsInSettings(),
    ).thenAnswer((_) async {});
    when(
      () => mock.logSubscriptionDeclinedPermissionsInPrompt(),
    ).thenAnswer((_) async {});

    when(() => mock.logSubscriptionPromptShown()).thenAnswer((_) async {});

    // Error events
    when(
      () => mock.logErrorSubscriptionPrompt(
        errorMessage: any(named: 'errorMessage'),
        phase: any(named: 'phase'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorSubscriptionPermission(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logNotificationTapped(
        jokeId: any(named: 'jokeId'),
        notificationId: any(named: 'notificationId'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorNotificationHandling(
        notificationId: any(named: 'notificationId'),
        phase: any(named: 'phase'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logTabChanged(any(), any(), method: any(named: 'method')),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorRouteNavigation(
        previousRoute: any(named: 'previousRoute'),
        newRoute: any(named: 'newRoute'),
        method: any(named: 'method'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(() => mock.logAnalyticsError(any(), any())).thenAnswer((_) async {});

    when(
      () => mock.logErrorJokeSave(
        jokeId: any(named: 'jokeId'),
        action: any(named: 'action'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorImagePrecache(
        jokeId: any(named: 'jokeId'),
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorImageLoad(
        jokeId: any(named: 'jokeId'),
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorJokeImagesMissing(
        jokeId: any(named: 'jokeId'),
        missingParts: any(named: 'missingParts'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorJokesLoad(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logErrorJokeFetch(
        jokeId: any(named: 'jokeId'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    // App usage
    when(
      () => mock.logAppUsageDayIncremented(
        numDaysUsed: any(named: 'numDaysUsed'),
      ),
    ).thenAnswer((_) async {});

    // Settings: joke viewer changed
    when(
      () => mock.logJokeViewerSettingChanged(mode: any(named: 'mode')),
    ).thenAnswer((_) async {});
  }
}

/// Fake classes for registerFallbackValue (required by mocktail)
class FakeAppUser extends Fake implements AppUser {}

/// Helper to register fallback values for mocktail
void registerAnalyticsFallbackValues() {
  registerFallbackValue(FakeAppUser());
  registerFallbackValue(JokeReactionType.save);
  registerFallbackValue(JokeViewerMode.reveal);
  // No subscription-specific enum fallbacks needed after API changes
  registerFallbackValue(AppTab.dailyJokes);
}
