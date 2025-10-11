import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

part 'analytics_providers.g.dart';

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
