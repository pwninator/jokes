// Central export file for all test helpers and mocks
// This provides a single import point for tests

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

import 'analytics_mocks.dart';
import 'auth_mocks.dart';
import 'core_mocks.dart';
import 'firebase_mocks.dart';
import 'joke_schedule_mocks.dart';

export 'analytics_mocks.dart';
export 'auth_mocks.dart';
export 'core_mocks.dart';
export 'firebase_mocks.dart';
export 'joke_schedule_mocks.dart';

/// Comprehensive test helpers that combine all mock categories
class TestHelpers {
  /// Get all provider overrides for a complete test environment
  /// This combines auth, core, Firebase, and analytics mocks
  static List<Override> getAllMockOverrides({
    // Auth options
    AppUser? testUser,

    // Additional overrides
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Firebase mocks (includes Firebase Analytics)
      ...FirebaseMocks.getFirebaseProviderOverrides(),

      // Core service mocks
      ...CoreMocks.getCoreProviderOverrides(),

      // Auth mocks
      ...AuthMocks.getAuthProviderOverrides(testUser: testUser),

      // Joke scheduler mocks
      ...JokeScheduleMocks.getJokeScheduleProviderOverrides(),

      // Analytics mocks
      ...AnalyticsMocks.getAnalyticsProviderOverrides(),

      // Additional custom overrides
      ...additionalOverrides,
    ];
  }

  /// Reset all mocks - call this in setUp() for each test
  static void resetAllMocks() {
    AuthMocks.reset();
    CoreMocks.reset();
    FirebaseMocks.reset();
    JokeScheduleMocks.reset();
    AnalyticsMocks.reset();
  }

  /// Create common test users
  static AppUser get anonymousUser => AuthMocks.createAnonymousUser();
  static AppUser get authenticatedUser => AuthMocks.createAuthenticatedUser();
  static AppUser get adminUser => AuthMocks.createAuthenticatedUser(
    role: UserRole.admin,
    email: 'admin@example.com',
    displayName: 'Admin User',
  );
}
