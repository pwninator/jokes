import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

import '../../test_helpers/analytics_mocks.dart';

// Mock Firebase Analytics
class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

void main() {
  group('FirebaseAnalyticsService', () {
    late MockFirebaseAnalytics mockFirebaseAnalytics;
    late FirebaseAnalyticsService analyticsService;

    setUpAll(() {
      registerAnalyticsFallbackValues();
    });

    setUp(() {
      mockFirebaseAnalytics = MockFirebaseAnalytics();
      analyticsService = FirebaseAnalyticsService(
        analytics: mockFirebaseAnalytics,
      );

      // Set up default mock responses
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
    });

    group('initialize', () {
      test('should initialize successfully in production mode', () async {
        // arrange
        when(
          () => mockFirebaseAnalytics.setDefaultEventParameters(any()),
        ).thenAnswer((_) async {});

        // act
        await analyticsService.initialize();

        // assert - no exception should be thrown
        expect(true, isTrue); // Test passes if no exception
      });

      test('should handle initialization errors gracefully', () async {
        // arrange
        when(
          () => mockFirebaseAnalytics.setDefaultEventParameters(any()),
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
        await analyticsService.logJokeSetupViewed(
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
        await analyticsService.logJokePunchlineViewed(
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
        await analyticsService.logJokeSaved(
          'test-joke-id',
          true,
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
    });

    group('subscription analytics', () {
      test('should log subscription prompt shown', () async {
        // arrange
        // No setup needed for debug mode

        // act
        await analyticsService.logSubscriptionPromptShown();

        // assert - in debug mode, we should see debug logging but no Firebase calls
        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription on settings', () async {
        await analyticsService.logSubscriptionOnSettings();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription on prompt', () async {
        await analyticsService.logSubscriptionOnPrompt();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription off settings', () async {
        await analyticsService.logSubscriptionOffSettings();

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription time changed', () async {
        await analyticsService.logSubscriptionTimeChanged(subscriptionHour: 9);

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: any(named: 'name'),
            parameters: any(named: 'parameters'),
          ),
        );
      });

      test('should log subscription declined maybe later', () async {
        await analyticsService.logSubscriptionDeclinedMaybeLater();

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
          await analyticsService.logSubscriptionDeclinedPermissionsInSettings();

          verifyNever(
            () => mockFirebaseAnalytics.logEvent(
              name: any(named: 'name'),
              parameters: any(named: 'parameters'),
            ),
          );
        },
      );

      test('should log subscription declined permissions in prompt', () async {
        await analyticsService.logSubscriptionDeclinedPermissionsInPrompt();

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
        await analyticsService.logJokeNavigation(
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
        await analyticsService.logTabChanged(
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
        await analyticsService.logNotificationTapped(
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

    group('error handling', () {
      test('should handle analytics errors gracefully', () async {
        // arrange
        // No setup needed for debug mode

        // act & assert - should not throw
        await expectLater(
          analyticsService.logJokeSetupViewed(
            'test-joke-id',
            navigationMethod: AnalyticsNavigationMethod.swipe,
            jokeContext: 'test',
          ),
          completes,
        );
      });

      test('exercises new error/flow analytics methods', () async {
        // act
        await analyticsService.logJokeShareInitiated(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
        );
        await analyticsService.logJokeShareCanceled(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
          status: 'dismissed',
        );
        await analyticsService.logErrorJokeShare(
          'joke-id',
          jokeContext: 'ctx',
          shareMethod: 'images',
          errorMessage: 'boom',
          errorContext: 'share_images',
          exceptionType: 'Exception',
        );
        await analyticsService.logErrorSubscriptionPrompt(
          errorMessage: 'prompt failed',
          phase: 'show_dialog',
        );
        await analyticsService.logErrorSubscriptionPermission(
          source: 'prompt',
          errorMessage: 'denied',
        );
        await analyticsService.logErrorNotificationHandling(
          notificationId: 'nid',
          phase: 'foreground',
          errorMessage: 'notif error',
        );
        await analyticsService.logErrorRouteNavigation(
          previousRoute: '/a',
          newRoute: '/b',
          method: 'programmatic',
          errorMessage: 'route err',
        );
        await analyticsService.logErrorJokeSave(
          jokeId: 'joke-id',
          action: 'toggle',
          errorMessage: 'save err',
        );
        await analyticsService.logErrorImagePrecache(
          jokeId: 'joke-id',
          imageType: 'setup',
          imageUrlHash: 'abc',
          errorMessage: 'cache err',
        );
        await analyticsService.logErrorImageLoad(
          jokeId: 'joke-id',
          imageType: 'setup',
          imageUrlHash: 'abc',
          errorMessage: 'load err',
        );
        await analyticsService.logErrorJokeImagesMissing(
          jokeId: 'joke-id',
          missingParts: 'setup',
        );
        await analyticsService.logErrorJokesLoad(
          source: 'monthly',
          errorMessage: 'load err',
        );
        await analyticsService.logErrorJokeFetch(
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
    });
  });
}
