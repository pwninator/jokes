import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

part 'analytics_providers.g.dart';

@Riverpod(keepAlive: true)
FirebaseAnalytics firebaseAnalytics(Ref ref) {
  return FirebaseAnalytics.instance;
}

/// Provider for AnalyticsService
@Riverpod(keepAlive: true)
AnalyticsService analyticsService(Ref ref) {
  final firebaseAnalytics = ref.watch(firebaseAnalyticsProvider);
  final crashService = ref.watch(crashReportingServiceProvider);
  return FirebaseAnalyticsService(
    analytics: firebaseAnalytics,
    crashReportingService: crashService,
  );
}

/// Provider that initializes analytics and sets up user tracking
/// This provider automatically manages analytics initialization and user property updates
final analyticsInitializationProvider = FutureProvider<void>((ref) async {
  final analyticsService = ref.watch(analyticsServiceProvider);
  final authState = ref.watch(authStateProvider);

  // Initialize analytics service
  await analyticsService.initialize();

  // Set user properties when auth state is available
  authState.whenData((user) async {
    await analyticsService.setUserProperties(user);
  });
});

/// Provider that watches auth state changes and updates analytics user properties
/// This ensures analytics always has the latest user information
final analyticsUserTrackingProvider = Provider<void>((ref) {
  final analyticsService = ref.watch(analyticsServiceProvider);

  // Update user properties whenever auth state changes
  ref.listen<AsyncValue<dynamic>>(authStateProvider, (previous, current) {
    current.whenData((user) async {
      await analyticsService.setUserProperties(user);
    });
  });
});
