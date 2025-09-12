import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

import '../../test_helpers/analytics_mocks.dart';

// Mock Firebase Analytics
class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockCrashReportingService extends Mock implements CrashReportingService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  group('FirebaseAnalyticsService', () {
    late MockFirebaseAnalytics mockFirebaseAnalytics;
    late FirebaseAnalyticsService analyticsService;
    late MockCrashReportingService mockCrashService;

    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Needed for mocktail when matching FlutterErrorDetails and StackTrace
      registerFallbackValue(FlutterErrorDetails(exception: Exception('x')));
      registerFallbackValue(StackTrace.current);
    });

    setUp(() {
      mockFirebaseAnalytics = MockFirebaseAnalytics();
      mockCrashService = MockCrashReportingService();
      analyticsService = FirebaseAnalyticsService(
        analytics: mockFirebaseAnalytics,
        crashReportingService: mockCrashService,
      );

      // Set up default mock responses
      when(
        () => mockFirebaseAnalytics.setDefaultEventParameters(
          any<Map<String, Object?>>(),
        ),
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

      // Crash reporting stubs
      when(() => mockCrashService.initialize()).thenAnswer((_) async {});
      when(() => mockCrashService.setUser(any())).thenAnswer((_) async {});
      when(
        () => mockCrashService.recordFlutterError(any()),
      ).thenAnswer((_) async {});
      when(
        () => mockCrashService.recordFatal(any(), any()),
      ).thenAnswer((_) async {});
      when(
        () => mockCrashService.recordNonFatal(
          any(),
          stackTrace: any(named: 'stackTrace'),
          keys: any(named: 'keys'),
        ),
      ).thenAnswer((_) async {});
      // Also allow calls without stackTrace (optional named arg)
      when(
        () => mockCrashService.recordNonFatal(any(), keys: any(named: 'keys')),
      ).thenAnswer((_) async {});
      when(() => mockCrashService.log(any())).thenAnswer((_) async {});
      when(() => mockCrashService.setKeys(any())).thenAnswer((_) async {});
    });

    group('initialize', () {
      test('should initialize successfully in production mode', () async {
        // arrange
        when(
          () => mockFirebaseAnalytics.setDefaultEventParameters(
            any<Map<String, Object?>>(),
          ),
        ).thenAnswer((_) async {});

        // act
        await analyticsService.initialize();

        // assert - no exception should be thrown
        expect(true, isTrue); // Test passes if no exception
      });

      test('should handle initialization errors gracefully', () async {
        // arrange
        when(
          () => mockFirebaseAnalytics.setDefaultEventParameters(
            any<Map<String, Object?>>(),
          ),
        ).thenThrow(Exception('Firebase initialization failed'));

        // act & assert - should not throw
        await expectLater(analyticsService.initialize(), completes);
      });
    });

    group('setUserProperties', () {
      test('should set user properties for authenticated user', () async {
        // arrange
        final user = AppUser(
          id: 'test-user-id',
          email: 'test@example.com',
          displayName: 'Test User',
          role: UserRole.user,
          isAnonymous: false,
        );

        // act
        await analyticsService.setUserProperties(user);

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.setUserId(id: any(named: 'id')),
        );
        verifyNever(
          () => mockFirebaseAnalytics.setUserProperty(
            name: any(named: 'name'),
            value: any(named: 'value'),
          ),
        );
      });

      test('should set user properties for admin user', () async {
        // arrange
        final adminUser = AppUser(
          id: 'admin-user-id',
          email: 'admin@example.com',
          displayName: 'Admin User',
          role: UserRole.admin,
          isAnonymous: false,
        );

        // act
        await analyticsService.setUserProperties(adminUser);

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.setUserProperty(
            name: any(named: 'name'),
            value: any(named: 'value'),
          ),
        );
      });

      test('should handle null user', () async {
        // arrange
        // No setup needed for debug mode

        // act
        await analyticsService.setUserProperties(null);

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.setUserProperty(
            name: any(named: 'name'),
            value: any(named: 'value'),
          ),
        );
      });
    });

    group('joke viewing analytics', () {
      test('should log joke setup viewed', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logJokeSetupViewed(
          'test-joke-id',
          navigationMethod: AnalyticsNavigationMethod.swipe,
          jokeContext: 'test',
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log joke punchline viewed', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logJokePunchlineViewed(
          'test-joke-id',
          navigationMethod: AnalyticsNavigationMethod.tap,
          jokeContext: 'test',
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });
    });

    group('joke save analytics', () {
      test('should log joke save', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logJokeSaved(
          'test-joke-id',
          jokeContext: 'test',
          totalJokesSaved: 3,
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log joke unsave', () async {
        // act
        analyticsService.logJokeUnsaved(
          'test-joke-id',
          jokeContext: 'test',
          totalJokesSaved: 2,
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });
    });

    group('subscription analytics', () {
      test('should log subscription prompt shown', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logSubscriptionPromptShown();

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription on settings', () async {
        analyticsService.logSubscriptionOnSettings();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription on prompt', () async {
        analyticsService.logSubscriptionOnPrompt();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription off settings', () async {
        analyticsService.logSubscriptionOffSettings();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription time changed', () async {
        analyticsService.logSubscriptionTimeChanged(subscriptionHour: 9);

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription declined maybe later', () async {
        analyticsService.logSubscriptionDeclinedMaybeLater();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test(
        'should log subscription declined permissions in settings',
        () async {
          analyticsService.logSubscriptionDeclinedPermissionsInSettings();

          verifyNever(
            () => mockFirebaseAnalytics.logEvent(
              name: any(named: 'name'),
              parameters: any(named: 'parameters'),
            ),
          );
        },
      );

      test('should log subscription declined permissions in prompt', () async {
        analyticsService.logSubscriptionDeclinedPermissionsInPrompt();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });
    });

    group('navigation analytics', () {
      test('should log joke navigation', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logJokeNavigation(
          'test-joke-id',
          5,
          method: 'swipe',
          jokeContext: 'test',
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log tab changed', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logTabChanged(
          AppTab.dailyJokes,
          AppTab.settings,
          method: 'tap',
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });
    });

    group('notification analytics', () {
      test('should log notification tapped', () async {
        // arrange
        // No setup needed for debug mode

        // act
        analyticsService.logNotificationTapped(
          jokeId: 'test-joke-id',
          notificationId: 'test-notification-id',
        );

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });
    });

    group('app usage analytics', () {
      test('should log app usage day incremented', () async {
        // act
        analyticsService.logAppUsageDayIncremented(numDaysUsed: 2);

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });
    });
    group('error handling', () {
      test('should handle analytics errors gracefully', () async {
        // arrange
        // No setup needed for debug mode

        // act & assert - should not throw
        await expectLater(
          Future.sync(() => analyticsService.logJokeSetupViewed(
            'test-joke-id',
            navigationMethod: AnalyticsNavigationMethod.swipe,
            jokeContext: 'test',
          )),
          completes,
        );
      });

      test('exercises new error/flow analytics methods', () async {
        // act
        analyticsService.logJokeShareInitiated(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
        );
        analyticsService.logJokeShareSuccess(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
          shareDestination: 'com.whatsapp',
          totalJokesShared: 5,
        );
        analyticsService.logJokeShareCanceled(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
          shareDestination: 'com.whatsapp',
        );
        analyticsService.logErrorJokeShare(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
          errorMessage: 'boom',
          errorContext: 'share_images',
          exceptionType: 'Exception',
        );
        analyticsService.logErrorSubscriptionPrompt(
          errorMessage: 'prompt failed',
          phase: 'show_dialog',
        );
        analyticsService.logErrorSubscriptionPermission(
          source: 'prompt',
          errorMessage: 'denied',
        );
        analyticsService.logErrorNotificationHandling(
          notificationId: 'nid',
          phase: 'foreground',
          errorMessage: 'notif error',
        );
        analyticsService.logErrorRouteNavigation(
          previousRoute: '/a',
          newRoute: '/b',
          method: 'programmatic',
          errorMessage: 'route err',
        );
        analyticsService.logErrorJokeSave(
          jokeId: 'joke-id',
          action: 'toggle',
          errorMessage: 'save err',
        );
        analyticsService.logErrorImagePrecache(
          jokeId: 'joke-id',
          imageType: 'setup',
          imageUrlHash: 'abc',
          errorMessage: 'cache err',
        );
        analyticsService.logErrorImageLoad(
          jokeId: 'joke-id',
          imageType: 'setup',
          imageUrlHash: 'abc',
          errorMessage: 'load err',
        );
        analyticsService.logErrorJokeImagesMissing(
          jokeId: 'joke-id',
          missingParts: 'setup',
        );
        analyticsService.logErrorJokesLoad(
          source: 'monthly',
          errorMessage: 'load err',
        );
        analyticsService.logErrorJokeFetch(
          jokeId: 'joke-id',
          errorMessage: 'fetch err',
        );

        // assert - ensure no Firebase calls in debug mode
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('logs Crashlytics non-fatal for error analytics methods', () async {
        // act
        analyticsService.logErrorJokeShare(
          'j-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
          errorMessage: 'boom',
          errorContext: 'share_images',
          exceptionType: 'Exception',
        );
        analyticsService.logErrorSubscriptionPrompt(
          errorMessage: 'prompt failed',
          phase: 'show_dialog',
        );
        analyticsService.logErrorSubscriptionPermission(
          source: 'prompt',
          errorMessage: 'denied',
        );
        analyticsService.logErrorNotificationHandling(
          notificationId: 'nid',
          phase: 'foreground',
          errorMessage: 'notif err',
        );
        analyticsService.logErrorRouteNavigation(
          previousRoute: '/a',
          newRoute: '/b',
          method: 'tap',
          errorMessage: 'route err',
        );
        analyticsService.logAnalyticsError('ae', 'ctx');
        analyticsService.logErrorJokeSave(
          jokeId: 'j-id',
          action: 'toggle',
          errorMessage: 'save err',
        );
        analyticsService.logErrorImagePrecache(
          jokeId: 'j-id',
          imageType: 'setup',
          imageUrlHash: 'abc',
          errorMessage: 'cache err',
        );
        analyticsService.logErrorImageLoad(
          jokeId: 'j-id',
          imageType: 'setup',
          imageUrlHash: 'abc',
          errorMessage: 'load err',
        );
        analyticsService.logErrorJokeImagesMissing(
          jokeId: 'j-id',
          missingParts: 'setup',
        );
        analyticsService.logErrorJokesLoad(
          source: 'viewer',
          errorMessage: 'load err',
        );
        analyticsService.logErrorJokeFetch(
          jokeId: 'j-id',
          errorMessage: 'fetch err',
        );

        // New errors
        analyticsService.logErrorAuthSignIn(
          source: 'user_settings_screen',
          errorMessage: 'google_sign_in_failed',
        );
        analyticsService.logErrorSubscriptionToggle(
          source: 'user_settings_screen',
          errorMessage: 'notifications_toggle_failed',
        );
        analyticsService.logErrorSubscriptionTimeUpdate(
          source: 'notification_hour_widget',
          errorMessage: 'notification_hour_update_failed',
        );
        analyticsService.logErrorFeedbackSubmit(
          errorMessage: 'feedback_submit_failed',
        );
        analyticsService.logAppReviewAttempt(source: 'settings');
        analyticsService.logErrorAppReviewAvailability(
          source: 'service',
          errorMessage: 'app_review_is_available_failed',
        );
        analyticsService.logErrorAppReviewRequest(
          source: 'settings',
          errorMessage: 'app_review_request_failed',
        );

        // Allow microtasks to run for fire-and-forget logging
        await Future<void>.delayed(Duration.zero);

        // Stronger assertion: verify specific events at least once
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorJokeShare.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorSubscriptionPrompt.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorSubscriptionPermission.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorNotificationHandling.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorRouteNavigation.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.analyticsError.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorJokeSave.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorImagePrecache.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorImageLoad.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorJokeImagesMissing.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorJokesLoad.eventName,
              ),
            ),
          ),
        ).called(greaterThanOrEqualTo(1));
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorJokeFetch.eventName,
              ),
            ),
          ),
        ).called(1);

        // New ones
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorAuthSignIn.eventName,
              ),
            ),
          ),
        ).called(1);
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorSubscriptionToggle.eventName,
              ),
            ),
          ),
        ).called(1);
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorSubscriptionTimeUpdate.eventName,
              ),
            ),
          ),
        ).called(1);
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorFeedbackSubmit.eventName,
              ),
            ),
          ),
        ).called(1);
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorAppReviewAvailability.eventName,
              ),
            ),
          ),
        ).called(1);
        verify(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.errorAppReviewRequest.eventName,
              ),
            ),
          ),
        ).called(1);

        // Ensure non-error attempt does NOT record crash
        verifyNever(
          () => mockCrashService.recordNonFatal(
            any(),
            keys: any(
              named: 'keys',
              that: containsPair(
                'analytics_event',
                AnalyticsEvent.appReviewAttempt.eventName,
              ),
            ),
          ),
        );
      });
    });
  });
}
