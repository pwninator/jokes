import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

final crashReportingServiceProvider = Provider<CrashReportingService>((ref) {
  if (kReleaseMode) {
    return FirebaseCrashReportingService();
  }
  return NoopCrashReportingService();
});

/// Initializes crash reporting and syncs user identifier with auth state
final crashReportingInitializationProvider = Provider<void>((ref) {
  final crashService = ref.watch(crashReportingServiceProvider);

  // Listen to auth changes and update crash user identifier
  ref.listen<AsyncValue<dynamic>>(authStateProvider, (prev, next) async {
    next.whenData((user) async {
      await crashService.setUser(user?.id);
    });
  });
});
