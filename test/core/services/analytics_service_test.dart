import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockCrashReportingService extends Mock implements CrashReportingService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late MockFirebaseAnalytics mockFirebaseAnalytics;
  late FirebaseAnalyticsService analyticsService;
  late MockCrashReportingService mockCrashService;

  setUpAll(() {
    registerFallbackValue(StackTrace.current);
  });

  setUp(() {
    mockFirebaseAnalytics = MockFirebaseAnalytics();
    mockCrashService = MockCrashReportingService();
    analyticsService = FirebaseAnalyticsService(
      analytics: mockFirebaseAnalytics,
      crashReportingService: mockCrashService,
    );

    // Default mock responses
    when(
      () => mockFirebaseAnalytics.setDefaultEventParameters(any()),
    ).thenAnswer((_) async {});
    when(
      () => mockFirebaseAnalytics.setUserId(id: any(named: 'id')),
    ).thenAnswer((_) async {});
    when(
      () => mockFirebaseAnalytics.setUserProperty(
        name: any(named: 'name'),
        value: any(named: 'value'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mockFirebaseAnalytics.logEvent(
        name: any(named: 'name'),
        parameters: any(named: 'parameters'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mockCrashService.recordNonFatal(
        any(),
        stackTrace: any(named: 'stackTrace'),
        keys: any(named: 'keys'),
      ),
    ).thenAnswer((_) async {});
  });

  group('FirebaseAnalyticsService (in debug environment)', () {
    test('does not send events to Firebase', () async {
      // A list of all logging methods to test
      final allLogFunctions = [
        () => analyticsService.logJokeSetupViewed(
          'j1',
          navigationMethod: 'swipe',
          jokeContext: 'daily',
          jokeViewerMode: JokeViewerMode.reveal,
        ),
        () => analyticsService.logJokePunchlineViewed(
          'j2',
          navigationMethod: 'tap',
          jokeContext: 'saved',
          jokeViewerMode: JokeViewerMode.reveal,
        ),
        () => analyticsService.logSubscriptionOnSettings(),
        () => analyticsService.logErrorJokeShare(
          'j1',
          jokeContext: 'ctx',
          errorMessage: 'err',
        ),
        () => analyticsService.logAppUsageDays(
          numDaysUsed: 3,
          brightness: Brightness.light,
        ),
      ];

      for (final logFunction in allLogFunctions) {
        logFunction();
      }

      await Future.delayed(Duration.zero); // Allow microtasks to complete

      verifyNever(
        () => mockFirebaseAnalytics.logEvent(
          name: any(named: 'name'),
          parameters: any(named: 'parameters'),
        ),
      );
    });

    test(
      'logs error events to Crashlytics without app_theme parameter',
      () async {
        analyticsService.logErrorJokesLoad(source: 'src', errorMessage: 'err');
        await Future.delayed(Duration.zero); // Allow microtasks to complete

        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            stackTrace: any(named: 'stackTrace'),
            keys: any(
              named: 'keys',
              that: allOf(
                containsPair('analytics_event', 'error_jokes_load'),
                predicate<Map<String, Object>>(
                  (m) => !m.containsKey('app_theme'),
                  'does not include app_theme',
                ),
              ),
            ),
          ),
        ).called(1);
      },
    );

    test('initialization completes without error', () async {
      await expectLater(analyticsService.initialize(), completes);
    });

    test('setUserProperties completes without error', () async {
      const user = AppUser(
        id: 'user1',
        email: 'user@test.com',
        isAnonymous: false,
        role: UserRole.user,
      );
      await expectLater(analyticsService.setUserProperties(user), completes);
      await expectLater(analyticsService.setUserProperties(null), completes);
    });
  });
}
