import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockCrashReportingService extends Mock implements CrashReportingService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FirebaseAnalyticsService analyticsService;
  late MockFirebaseAnalytics mockFirebaseAnalytics;
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
      forceRealAnalytics: true,
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
      analyticsService = FirebaseAnalyticsService(
        analytics: mockFirebaseAnalytics,
        crashReportingService: mockCrashService,
        forceRealAnalytics: false,
      );
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
          homepage: 'daily',
        ),
        () => analyticsService.logHomepage(true),
        () => analyticsService.logHomepage(false),
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

  group('logAppUsageDays', () {
    test(
      'logs usage day increment without return event on first day',
      () async {
        analyticsService.logAppUsageDays(
          numDaysUsed: 1,
          brightness: Brightness.dark,
          homepage: 'daily',
        );

        await Future.delayed(Duration.zero);

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'app_usage_day_incremented',
            parameters: any(
              named: 'parameters',
              that: predicate<Map<String, Object>>(
                (params) =>
                    params[AnalyticsParameters.numDaysUsed] == 1 &&
                    params[AnalyticsParameters.appTheme] == 'dark',
                'contains day count and theme',
              ),
            ),
          ),
        ).called(1);

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: 'app_return_days_incremented',
            parameters: any(named: 'parameters'),
          ),
        );
      },
    );

    test(
      'logs usage and return events when numDaysUsed greater than one',
      () async {
        analyticsService.logAppUsageDays(
          numDaysUsed: 3,
          brightness: Brightness.light,
          homepage: 'daily',
        );

        await Future.delayed(Duration.zero);

        final matcher = predicate<Map<String, Object>>(
          (params) =>
              params[AnalyticsParameters.numDaysUsed] == 3 &&
              params[AnalyticsParameters.appTheme] == 'light',
          'contains day count and theme',
        );

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'app_usage_day_incremented',
            parameters: any(named: 'parameters', that: matcher),
          ),
        ).called(1);

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'app_return_days_incremented',
            parameters: any(named: 'parameters', that: matcher),
          ),
        ).called(1);
      },
    );
  });

  group('logJokeSetupViewed', () {
    test('logs joke setup viewed without suffix', () async {
      analyticsService.logJokeSetupViewed(
        'j123',
        navigationMethod: 'swipe',
        jokeContext: 'daily',
        jokeViewerMode: JokeViewerMode.reveal,
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j123' &&
            params[AnalyticsParameters.navigationMethod] == 'swipe' &&
            params[AnalyticsParameters.jokeContext] == 'daily' &&
            params[AnalyticsParameters.jokeViewerMode] == 'reveal',
        'includes all joke setup viewed parameters',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_setup_viewed',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });

    test('logs joke setup viewed with suffix appended to context', () async {
      analyticsService.logJokeSetupViewed(
        'j456',
        navigationMethod: 'tap',
        jokeContext: 'saved',
        jokeContextSuffix: 'category',
        jokeViewerMode: JokeViewerMode.bothAdaptive,
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j456' &&
            params[AnalyticsParameters.navigationMethod] == 'tap' &&
            params[AnalyticsParameters.jokeContext] == 'saved:category' &&
            params[AnalyticsParameters.jokeViewerMode] == 'bothAdaptive',
        'includes all joke setup viewed parameters with suffixed context',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_setup_viewed',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });
  });

  group('logJokePunchlineViewed', () {
    test('logs joke punchline viewed without suffix', () async {
      analyticsService.logJokePunchlineViewed(
        'j123',
        navigationMethod: 'swipe',
        jokeContext: 'daily',
        jokeViewerMode: JokeViewerMode.reveal,
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j123' &&
            params[AnalyticsParameters.navigationMethod] == 'swipe' &&
            params[AnalyticsParameters.jokeContext] == 'daily' &&
            params[AnalyticsParameters.jokeViewerMode] == 'reveal',
        'includes all joke punchline viewed parameters',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_punchline_viewed',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });

    test(
      'logs joke punchline viewed with suffix appended to context',
      () async {
        analyticsService.logJokePunchlineViewed(
          'j456',
          navigationMethod: 'tap',
          jokeContext: 'saved',
          jokeContextSuffix: 'category',
          jokeViewerMode: JokeViewerMode.bothAdaptive,
        );

        await Future.delayed(Duration.zero);

        final matcher = predicate<Map<String, Object>>(
          (params) =>
              params[AnalyticsParameters.jokeId] == 'j456' &&
              params[AnalyticsParameters.navigationMethod] == 'tap' &&
              params[AnalyticsParameters.jokeContext] == 'saved:category' &&
              params[AnalyticsParameters.jokeViewerMode] == 'bothAdaptive',
          'includes all joke punchline viewed parameters with suffixed context',
        );

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'joke_punchline_viewed',
            parameters: any(named: 'parameters', that: matcher),
          ),
        ).called(1);
      },
    );
  });

  group('logJokeViewed', () {
    test(
      'logs standard event only when total jokes viewed below threshold',
      () async {
        analyticsService.logJokeViewed(
          'j123',
          totalJokesViewed: 5,
          navigationMethod: 'swipe',
          jokeContext: 'daily',
          jokeViewerMode: JokeViewerMode.reveal,
        );

        await Future.delayed(Duration.zero);

        final matcher = predicate<Map<String, Object>>(
          (params) =>
              params[AnalyticsParameters.jokeId] == 'j123' &&
              params[AnalyticsParameters.totalJokesViewed] == 5 &&
              params[AnalyticsParameters.navigationMethod] == 'swipe' &&
              params[AnalyticsParameters.jokeContext] == 'daily' &&
              params[AnalyticsParameters.jokeViewerMode] == 'reveal' &&
              params[AnalyticsParameters.jokeViewedCount] == 1,
          'includes joke metadata and counts',
        );

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'joke_viewed',
            parameters: any(named: 'parameters', that: matcher),
          ),
        ).called(1);

        verifyNever(
          () => mockFirebaseAnalytics.logEvent(
            name: 'joke_viewed_high',
            parameters: any(named: 'parameters'),
          ),
        );
      },
    );

    test('logs high event when total jokes viewed is ten or more', () async {
      analyticsService.logJokeViewed(
        'j999',
        totalJokesViewed: 12,
        navigationMethod: 'tap',
        jokeContext: 'saved',
        jokeViewerMode: JokeViewerMode.bothAdaptive,
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j999' &&
            params[AnalyticsParameters.totalJokesViewed] == 12 &&
            params[AnalyticsParameters.navigationMethod] == 'tap' &&
            params[AnalyticsParameters.jokeContext] == 'saved' &&
            params[AnalyticsParameters.jokeViewerMode] == 'bothAdaptive' &&
            params[AnalyticsParameters.jokeViewedCount] == 1,
        'includes joke metadata and counts',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_viewed',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_viewed_high',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });

    test('logs joke viewed with suffix appended to context', () async {
      analyticsService.logJokeViewed(
        'j789',
        totalJokesViewed: 5,
        navigationMethod: 'swipe',
        jokeContext: 'feed',
        jokeContextSuffix: 'search',
        jokeViewerMode: JokeViewerMode.reveal,
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j789' &&
            params[AnalyticsParameters.totalJokesViewed] == 5 &&
            params[AnalyticsParameters.navigationMethod] == 'swipe' &&
            params[AnalyticsParameters.jokeContext] == 'feed:search' &&
            params[AnalyticsParameters.jokeViewerMode] == 'reveal' &&
            params[AnalyticsParameters.jokeViewedCount] == 1,
        'includes all joke viewed parameters with suffixed context',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_viewed',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });
  });

  group('Remote Config Event Name Length', () {
    test('all remote config event names are less than 40 characters', () async {
      // Import the remote config parameters
      final remoteParams = <RemoteParam, String>{
        RemoteParam.feedbackMinJokesViewed: 'feedback_min_jokes_viewed',
        RemoteParam.subscriptionPromptMinJokesViewed:
            'subscription_prompt_min_jokes_viewed',
        RemoteParam.reviewMinDaysUsed: 'review_min_days_used',
        RemoteParam.reviewMinViewedJokes: 'review_min_viewed_jokes',
        RemoteParam.reviewMinSavedJokes: 'review_min_saved_jokes',
        RemoteParam.reviewMinSharedJokes: 'review_min_shared_jokes',
        RemoteParam.reviewRequestFromJokeViewed:
            'review_request_from_joke_viewed',
        RemoteParam.reviewRequireDailySubscription:
            'review_require_daily_subscription',
        RemoteParam.reviewPromptVariant: 'review_prompt_variant',
        RemoteParam.defaultJokeViewerReveal: 'default_joke_viewer_reveal',
        RemoteParam.shareImagesMode: 'share_images_mode',
        RemoteParam.adDisplayMode: 'ad_display_mode',
        RemoteParam.bannerAdPosition: 'banner_ad_position',
        RemoteParam.feedScreenEnabled: 'feed_screen_enabled',
      };

      // Capture event names that are logged
      final capturedEventNames = <String>[];

      when(
        () => mockFirebaseAnalytics.logEvent(
          name: any(named: 'name'),
          parameters: any(named: 'parameters'),
        ),
      ).thenAnswer((invocation) {
        final name = invocation.namedArguments[#name] as String;
        capturedEventNames.add(name);
        return Future.value();
      });

      // Test each remote config function for each parameter
      for (final entry in remoteParams.entries) {
        final paramName = entry.value;

        // Test all four logging functions
        analyticsService.logRemoteConfigUsedLocal(
          paramName: paramName,
          value: 'test_value',
        );
        analyticsService.logRemoteConfigUsedError(
          paramName: paramName,
          value: 'test_value',
        );
        analyticsService.logRemoteConfigUsedDefault(
          paramName: paramName,
          value: 'test_value',
        );
        analyticsService.logRemoteConfigUsedRemote(
          paramName: paramName,
          value: 'test_value',
        );
      }

      // Wait for all async operations to complete
      await Future.delayed(const Duration(milliseconds: 100));

      // Verify all event names are less than 40 characters
      for (final eventName in capturedEventNames) {
        expect(
          eventName.length,
          lessThanOrEqualTo(40),
          reason:
              'Event name "$eventName" is ${eventName.length} characters, '
              'exceeding Firebase Analytics 40-character limit',
        );
      }
    });
  });

  group('logHomepage', () {
    test(
      'logs homepage event with feed value when feedEnabled is true',
      () async {
        analyticsService.logHomepage(true);

        await Future.delayed(Duration.zero);

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'homepage',
            parameters: any(
              named: 'parameters',
              that: predicate<Map<String, Object>>(
                (params) =>
                    params[AnalyticsParameters.homepageName] ==
                    AnalyticsHomepageName.feed,
                'contains feed homepage name',
              ),
            ),
          ),
        ).called(1);
      },
    );

    test(
      'logs homepage event with daily value when feedEnabled is false',
      () async {
        analyticsService.logHomepage(false);

        await Future.delayed(Duration.zero);

        verify(
          () => mockFirebaseAnalytics.logEvent(
            name: 'homepage',
            parameters: any(
              named: 'parameters',
              that: predicate<Map<String, Object>>(
                (params) =>
                    params[AnalyticsParameters.homepageName] ==
                    AnalyticsHomepageName.daily,
                'contains daily homepage name',
              ),
            ),
          ),
        ).called(1);
      },
    );
  });

  group('logJokeNavigation', () {
    test('logs joke navigation without suffix', () async {
      analyticsService.logJokeNavigation(
        'j123',
        5,
        method: 'swipe',
        jokeContext: 'daily',
        jokeViewerMode: JokeViewerMode.reveal,
        brightness: Brightness.light,
        screenOrientation: 'portrait',
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j123' &&
            params[AnalyticsParameters.jokeScrollDepth] == 5 &&
            params[AnalyticsParameters.navigationMethod] == 'swipe' &&
            params[AnalyticsParameters.jokeContext] == 'daily' &&
            params[AnalyticsParameters.jokeViewerMode] == 'reveal' &&
            params[AnalyticsParameters.appTheme] == 'light' &&
            params[AnalyticsParameters.screenOrientation] == 'portrait' &&
            params[AnalyticsParameters.jokeNavigatedCount] == 1,
        'includes all joke navigation parameters',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_navigated',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });

    test('logs joke navigation with suffix appended to context', () async {
      analyticsService.logJokeNavigation(
        'j456',
        10,
        method: 'tap',
        jokeContext: 'saved',
        jokeContextSuffix: 'category',
        jokeViewerMode: JokeViewerMode.bothAdaptive,
        brightness: Brightness.dark,
        screenOrientation: 'landscape',
      );

      await Future.delayed(Duration.zero);

      final matcher = predicate<Map<String, Object>>(
        (params) =>
            params[AnalyticsParameters.jokeId] == 'j456' &&
            params[AnalyticsParameters.jokeScrollDepth] == 10 &&
            params[AnalyticsParameters.navigationMethod] == 'tap' &&
            params[AnalyticsParameters.jokeContext] == 'saved:category' &&
            params[AnalyticsParameters.jokeViewerMode] == 'bothAdaptive' &&
            params[AnalyticsParameters.appTheme] == 'dark' &&
            params[AnalyticsParameters.screenOrientation] == 'landscape' &&
            params[AnalyticsParameters.jokeNavigatedCount] == 1,
        'includes all joke navigation parameters with suffixed context',
      );

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_navigated',
          parameters: any(named: 'parameters', that: matcher),
        ),
      ).called(1);
    });
  });

  group('logJokeEndReached', () {
    test('logs joke end reached with context as event name suffix', () async {
      analyticsService.logJokeEndReached(jokeContext: 'daily');

      await Future.delayed(Duration.zero);

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_end_reached_daily',
          parameters: any(named: 'parameters', that: isEmpty),
        ),
      ).called(1);
    });

    test('logs joke end reached with different contexts', () async {
      analyticsService.logJokeEndReached(jokeContext: 'saved');

      await Future.delayed(Duration.zero);

      verify(
        () => mockFirebaseAnalytics.logEvent(
          name: 'joke_end_reached_saved',
          parameters: any(named: 'parameters', that: isEmpty),
        ),
      ).called(1);
    });
  });
}
