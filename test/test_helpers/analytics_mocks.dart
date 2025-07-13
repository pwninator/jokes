import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

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
        hasImages: any(named: 'hasImages'),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokePunchlineViewed(
        any(),
        hasImages: any(named: 'hasImages'),
        navigationMethod: any(named: 'navigationMethod'),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeNavigation(
        any(),
        any(),
        method: any(named: 'method'),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logJokeReaction(
        any(),
        any(),
        any(),
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logSubscriptionEvent(
        any(),
        any(),
        permissionGranted: any(named: 'permissionGranted'),
        subscriptionHour: any(named: 'subscriptionHour'),
      ),
    ).thenAnswer((_) async {});

    when(() => mock.logSubscriptionPromptShown()).thenAnswer((_) async {});

    when(
      () => mock.logNotificationTapped(
        jokeId: any(named: 'jokeId'),
        notificationId: any(named: 'notificationId'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mock.logTabChanged(any(), any(), method: any(named: 'method')),
    ).thenAnswer((_) async {});

    when(() => mock.logAnalyticsError(any(), any())).thenAnswer((_) async {});
  }
}

/// Fake classes for registerFallbackValue (required by mocktail)
class FakeAppUser extends Fake implements AppUser {}

/// Helper to register fallback values for mocktail
void registerAnalyticsFallbackValues() {
  registerFallbackValue(FakeAppUser());
  registerFallbackValue(JokeReactionType.save);
  registerFallbackValue(SubscriptionEventType.subscribed);
  registerFallbackValue(SubscriptionSource.popup);
  registerFallbackValue(AppTab.dailyJokes);
}
