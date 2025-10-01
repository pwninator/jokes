import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/brightness_provider.dart';

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockCrashReportingService extends Mock implements CrashReportingService {}

class MockRef extends Mock implements Ref {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late MockFirebaseAnalytics mockFirebaseAnalytics;
  late FirebaseAnalyticsService analyticsService;
  late MockCrashReportingService mockCrashService;
  late MockRef mockRef;

  setUpAll(() {
    registerFallbackValue(StackTrace.current);
  });

  setUp(() {
    mockFirebaseAnalytics = MockFirebaseAnalytics();
    mockCrashService = MockCrashReportingService();
    mockRef = MockRef();
    analyticsService = FirebaseAnalyticsService(
      mockRef,
      analytics: mockFirebaseAnalytics,
      crashReportingService: mockCrashService,
    );

    when(() => mockRef.read(brightnessProvider)).thenReturn(Brightness.light);

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

    test('logs error events to Crashlytics with app_theme parameter', () async {
      analyticsService.logErrorJokesLoad(source: 'src', errorMessage: 'err');
      await Future.delayed(Duration.zero); // Allow microtasks to complete

      verify(
        () => mockCrashService.recordNonFatal(
          any(),
          keys: any(
            named: 'keys',
            that: allOf(
              containsPair('analytics_event', 'error_jokes_load'),
              containsPair('app_theme', 'light'),
            ),
          ),
        ),
      ).called(1);
    });

    test(
        'logs error events to Crashlytics with app_theme parameter for dark theme',
        () async {
      when(() => mockRef.read(brightnessProvider)).thenReturn(Brightness.dark);

      analyticsService.logErrorJokesLoad(source: 'src', errorMessage: 'err');
      await Future.delayed(Duration.zero); // Allow microtasks to complete

      verify(
        () => mockCrashService.recordNonFatal(
          any(),
          keys: any(
            named: 'keys',
            that: allOf(
              containsPair('analytics_event', 'error_jokes_load'),
              containsPair('app_theme', 'dark'),
            ),
          ),
        ),
      ).called(1);
    });

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
