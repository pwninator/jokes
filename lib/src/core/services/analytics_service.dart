import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/utils/device_utils.dart';

/// Abstract interface for analytics service
/// This allows for easy mocking in tests
abstract class AnalyticsService {
  /// Initialize analytics and set user properties
  Future<void> initialize();

  /// Set user properties for analytics
  Future<void> setUserProperties(AppUser? user);

  /// Log when user views a joke setup
  Future<void> logJokeSetupViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
  });

  /// Log when user views a joke punchline
  Future<void> logJokePunchlineViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
  });

  /// Log when a joke is fully viewed (setup and punchline each viewed ≥ 2s sequentially)
  Future<void> logJokeViewed(
    String jokeId, {
    required int totalJokesViewed,
    required String navigationMethod,
    required String jokeContext,
  });

  /// Log when user navigates through jokes
  Future<void> logJokeNavigation(
    String jokeId,
    int jokeScrollDepth, {
    required String method,
    required String jokeContext,
  });

  /// Log when a joke is saved
  Future<void> logJokeSaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  });

  /// Log when a joke is unsaved
  Future<void> logJokeUnsaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  });

  /// Log successful joke share events
  Future<void> logJokeShareSuccess(
    String jokeId, {
    required String jokeContext,
    String? shareMethod,
    String? shareDestination,
    required int totalJokesShared,
  });

  /// Share funnel: user initiated sharing
  Future<void> logJokeShareInitiated(
    String jokeId, {
    required String jokeContext,
    required String shareMethod,
  });

  /// Share funnel: user canceled/dismissed share sheet (failure, not error)
  Future<void> logJokeShareCanceled(
    String jokeId, {
    required String jokeContext,
    required String shareMethod,
    String? shareDestination,
  });

  /// Share funnel: error occurred during sharing
  Future<void> logErrorJokeShare(
    String jokeId, {
    required String jokeContext,
    required String shareMethod,
    required String errorMessage,
    String? errorContext,
    String? exceptionType,
  });

  /// Subscription: toggled on in settings
  Future<void> logSubscriptionOnSettings();

  /// Subscription: accepted prompt and permission granted
  Future<void> logSubscriptionOnPrompt();

  /// Subscription: toggled off in settings
  Future<void> logSubscriptionOffSettings();

  /// Subscription: time changed in settings
  Future<void> logSubscriptionTimeChanged({required int subscriptionHour});

  /// Subscription: chose "Maybe later" in prompt
  Future<void> logSubscriptionDeclinedMaybeLater();

  /// Subscription: denied permissions from settings flow
  Future<void> logSubscriptionDeclinedPermissionsInSettings();

  /// Subscription: denied permissions from prompt flow
  Future<void> logSubscriptionDeclinedPermissionsInPrompt();

  /// Log when subscription prompt is shown
  Future<void> logSubscriptionPromptShown();

  /// Subscription prompt show/dismiss errors
  Future<void> logErrorSubscriptionPrompt({
    required String errorMessage,
    String? phase,
  });

  /// Subscription permission errors from prompt/settings flows
  Future<void> logErrorSubscriptionPermission({
    required String source,
    required String errorMessage,
  });

  /// Log when user taps on a notification to open the app
  Future<void> logNotificationTapped({String? jokeId, String? notificationId});

  /// Notification handling errors
  Future<void> logErrorNotificationHandling({
    String? notificationId,
    String? phase,
    required String errorMessage,
  });

  /// Remote Config errors
  Future<void> logErrorRemoteConfig({
    required String errorMessage,
    String? phase,
  });

  /// Log tab navigation events
  Future<void> logTabChanged(
    AppTab previousTab,
    AppTab newTab, {
    required String method,
  });

  /// Route/navigation errors
  Future<void> logErrorRouteNavigation({
    String? previousRoute,
    String? newRoute,
    String? method,
    required String errorMessage,
  });

  /// Log errors that occur during analytics
  Future<void> logAnalyticsError(String errorMessage, String context);

  /// Save reaction errors
  Future<void> logErrorJokeSave({
    required String jokeId,
    required String action,
    required String errorMessage,
  });

  /// Image-related errors
  Future<void> logErrorImagePrecache({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  });

  Future<void> logErrorImageLoad({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  });

  Future<void> logErrorJokeImagesMissing({
    required String jokeId,
    required String missingParts,
  });

  /// Data/content loading errors
  Future<void> logErrorJokesLoad({
    required String source,
    required String errorMessage,
  });

  Future<void> logErrorJokeFetch({
    required String jokeId,
    required String errorMessage,
  });

  /// App usage: unique day incremented
  Future<void> logAppUsageDayIncremented({required int numDaysUsed});

  /// Log joke search completion
  Future<void> logJokeSearch({
    required int queryLength,
    required String scope,
    required int resultsCount,
  });

  /// Log when user taps Similar to perform a prefilled search
  Future<void> logJokeSearchSimilar({
    required int queryLength,
    required String jokeContext,
  });

  /// Log when a user submits app feedback (no parameters)
  Future<void> logFeedbackSubmitted();

  // Auth
  Future<void> logErrorAuthSignIn({
    required String source,
    required String errorMessage,
  });

  // Settings / subscriptions
  Future<void> logErrorSubscriptionToggle({
    required String source,
    required String errorMessage,
  });

  Future<void> logErrorSubscriptionTimeUpdate({
    required String source,
    required String errorMessage,
  });

  // Feedback
  Future<void> logErrorFeedbackSubmit({required String errorMessage});

  // App review
  Future<void> logAppReviewAttempt({required String source});

  Future<void> logErrorAppReviewAvailability({
    required String source,
    required String errorMessage,
  });

  Future<void> logErrorAppReviewRequest({
    required String source,
    required String errorMessage,
  });
}

/// Firebase Analytics implementation of the analytics service
class FirebaseAnalyticsService implements AnalyticsService {
  final FirebaseAnalytics _analytics;
  final CrashReportingService _crashReportingService;
  AppUser? _currentUser;

  FirebaseAnalyticsService({
    FirebaseAnalytics? analytics,
    CrashReportingService? crashReportingService,
  }) : _analytics = analytics ?? FirebaseAnalytics.instance,
       _crashReportingService =
           crashReportingService ?? NoopCrashReportingService();

  /// Check if fake analytics should be used (debug mode AND not physical device)
  Future<bool> _shouldUseFakeAnalytics() async {
    if (kDebugMode) {
      try {
        final isPhysicalDevice = await DeviceUtils.isPhysicalDevice;
        return !isPhysicalDevice;
      } catch (e) {
        debugPrint('ANALYTICS WARN: Device check failed - $e');
        return true;
      }
    }
    return false;
  }

  @override
  Future<void> initialize() async {
    try {
      if (await _shouldUseFakeAnalytics()) {
        debugPrint(
          'ANALYTICS: Initializing in debug mode on non-physical device (events will not be sent)',
        );
        return;
      }

      // Set default user properties
      await _analytics.setDefaultEventParameters({
        AnalyticsParameters.userType: AnalyticsUserType.anonymous,
      });

      debugPrint('ANALYTICS: Firebase Analytics initialized');
    } catch (e) {
      debugPrint('ANALYTICS ERROR: Failed to initialize - $e');
    }
  }

  @override
  Future<void> setUserProperties(AppUser? user) async {
    _currentUser = user;

    try {
      final userType = _getUserType(user);

      if (await _shouldUseFakeAnalytics()) {
        debugPrint(
          'ANALYTICS (DEBUG): Setting user properties - userType: $userType',
        );
        return;
      }

      if (user?.id != null) {
        await _analytics.setUserId(id: user!.id);
      }
      await _analytics.setUserProperty(
        name: AnalyticsParameters.userType,
        value: userType,
      );

      debugPrint('ANALYTICS: User properties set - type: $userType');
    } catch (e) {
      debugPrint('ANALYTICS ERROR: Failed to set user properties - $e');
    }
  }

  @override
  Future<void> logJokeSetupViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSetupViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokePunchlineViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokePunchlineViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeViewed(
    String jokeId, {
    required int totalJokesViewed,
    required String navigationMethod,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokeViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.totalJokesViewed: totalJokesViewed,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeNavigation(
    String jokeId,
    int jokeScrollDepth, {
    required String method,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokeNavigated, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeScrollDepth: jokeScrollDepth,
      AnalyticsParameters.navigationMethod: method,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeSaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSaved, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.totalJokesSaved: totalJokesSaved,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeUnsaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  }) async {
    await _logEvent(AnalyticsEvent.jokeUnsaved, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.totalJokesSaved: totalJokesSaved,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeShareSuccess(
    String jokeId, {
    required String jokeContext,
    String? shareMethod,
    String? shareDestination,
    required int totalJokesShared,
  }) async {
    await _logEvent(AnalyticsEvent.jokeShareSuccess, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
      AnalyticsParameters.totalJokesShared: totalJokesShared,
      if (shareMethod != null) AnalyticsParameters.shareMethod: shareMethod,
      if (shareDestination != null)
        AnalyticsParameters.shareDestination: shareDestination,
    });
  }

  @override
  Future<void> logJokeShareInitiated(
    String jokeId, {
    required String jokeContext,
    required String shareMethod,
  }) async {
    await _logEvent(AnalyticsEvent.jokeShareInitiated, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.shareMethod: shareMethod,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeShareCanceled(
    String jokeId, {
    required String jokeContext,
    required String shareMethod,
    String? shareDestination,
  }) async {
    await _logEvent(AnalyticsEvent.jokeShareCanceled, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.shareMethod: shareMethod,
      AnalyticsParameters.userType: _getUserType(_currentUser),
      if (shareDestination != null)
        AnalyticsParameters.shareDestination: shareDestination,
    });
  }

  @override
  Future<void> logErrorJokeShare(
    String jokeId, {
    required String jokeContext,
    required String shareMethod,
    required String errorMessage,
    String? errorContext,
    String? exceptionType,
  }) async {
    await _logEvent(AnalyticsEvent.errorJokeShare, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.shareMethod: shareMethod,
      AnalyticsParameters.errorMessage: errorMessage,
      if (errorContext != null) AnalyticsParameters.errorContext: errorContext,
      if (exceptionType != null)
        AnalyticsParameters.exceptionType: exceptionType,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logSubscriptionOnSettings() async {
    await _logEvent(AnalyticsEvent.subscriptionOnSettings, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.permissionGranted: true,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionOnPrompt() async {
    await _logEvent(AnalyticsEvent.subscriptionOnPrompt, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.popup.value,
      AnalyticsParameters.permissionGranted: true,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionOffSettings() async {
    await _logEvent(AnalyticsEvent.subscriptionOffSettings, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionTimeChanged({
    required int subscriptionHour,
  }) async {
    await _logEvent(AnalyticsEvent.subscriptionTimeChanged, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.permissionGranted: true,
      AnalyticsParameters.subscriptionHour: subscriptionHour,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionDeclinedMaybeLater() async {
    await _logEvent(AnalyticsEvent.subscriptionDeclinedMaybeLater, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.popup.value,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionDeclinedPermissionsInSettings() async {
    await _logEvent(AnalyticsEvent.subscriptionDeclinedPermissions, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.permissionGranted: false,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionDeclinedPermissionsInPrompt() async {
    await _logEvent(AnalyticsEvent.subscriptionDeclinedPermissions, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.popup.value,
      AnalyticsParameters.permissionGranted: false,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionPromptShown() async {
    await _logEvent(AnalyticsEvent.subscriptionPromptShown, {
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logErrorSubscriptionPrompt({
    required String errorMessage,
    String? phase,
  }) async {
    await _logEvent(AnalyticsEvent.errorSubscriptionPrompt, {
      AnalyticsParameters.errorMessage: errorMessage,
      if (phase != null) AnalyticsParameters.phase: phase,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorSubscriptionPermission({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorSubscriptionPermission, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logNotificationTapped({
    String? jokeId,
    String? notificationId,
  }) async {
    await _logEvent(AnalyticsEvent.notificationTapped, {
      if (jokeId != null) AnalyticsParameters.jokeId: jokeId,
      if (notificationId != null)
        AnalyticsParameters.notificationId: notificationId,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logErrorNotificationHandling({
    String? notificationId,
    String? phase,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorNotificationHandling, {
      if (notificationId != null)
        AnalyticsParameters.notificationId: notificationId,
      if (phase != null) AnalyticsParameters.phase: phase,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorRemoteConfig({
    required String errorMessage,
    String? phase,
  }) async {
    await _logEvent(AnalyticsEvent.errorRemoteConfig, {
      if (phase != null) AnalyticsParameters.phase: phase,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logTabChanged(
    AppTab previousTab,
    AppTab newTab, {
    required String method,
  }) async {
    await _logEvent(AnalyticsEvent.tabChanged, {
      AnalyticsParameters.previousTab: previousTab.value,
      AnalyticsParameters.newTab: newTab.value,
      AnalyticsParameters.navigationMethod: method,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logErrorRouteNavigation({
    String? previousRoute,
    String? newRoute,
    String? method,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorRouteNavigation, {
      if (previousRoute != null) AnalyticsParameters.previousTab: previousRoute,
      if (newRoute != null) AnalyticsParameters.newTab: newRoute,
      if (method != null) AnalyticsParameters.navigationMethod: method,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logAnalyticsError(String errorMessage, String context) async {
    await _logEvent(AnalyticsEvent.analyticsError, {
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.errorContext: context,
    }, isError: true);
  }

  @override
  Future<void> logErrorJokeSave({
    required String jokeId,
    required String action,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorJokeSave, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.action: action,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorImagePrecache({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorImagePrecache, {
      if (jokeId != null) AnalyticsParameters.jokeId: jokeId,
      if (imageType != null) AnalyticsParameters.imageType: imageType,
      if (imageUrlHash != null) AnalyticsParameters.imageUrlHash: imageUrlHash,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorImageLoad({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorImageLoad, {
      if (jokeId != null) AnalyticsParameters.jokeId: jokeId,
      if (imageType != null) AnalyticsParameters.imageType: imageType,
      if (imageUrlHash != null) AnalyticsParameters.imageUrlHash: imageUrlHash,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorJokeImagesMissing({
    required String jokeId,
    required String missingParts,
  }) async {
    await _logEvent(AnalyticsEvent.errorJokeImagesMissing, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.errorContext: missingParts,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorJokesLoad({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorJokesLoad, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorJokeFetch({
    required String jokeId,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorJokeFetch, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logAppUsageDayIncremented({required int numDaysUsed}) async {
    await _logEvent(AnalyticsEvent.appUsageDayIncremented, {
      AnalyticsParameters.numDaysUsed: numDaysUsed,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeSearch({
    required int queryLength,
    required String scope,
    required int resultsCount,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSearch, {
      'query_length': queryLength,
      'scope': scope,
      'results_count': resultsCount,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeSearchSimilar({
    required int queryLength,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSearchSimilar, {
      'query_length': queryLength,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logFeedbackSubmitted() async {
    // Per requirements, log event with no parameters
    await _logEvent(AnalyticsEvent.feedbackSubmitted, {});
  }

  // Auth
  @override
  Future<void> logErrorAuthSignIn({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorAuthSignIn, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  // Settings / subscriptions
  @override
  Future<void> logErrorSubscriptionToggle({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorSubscriptionToggle, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorSubscriptionTimeUpdate({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorSubscriptionTimeUpdate, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  // Feedback
  @override
  Future<void> logErrorFeedbackSubmit({required String errorMessage}) async {
    await _logEvent(AnalyticsEvent.errorFeedbackSubmit, {
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  // App review
  @override
  Future<void> logAppReviewAttempt({required String source}) async {
    await _logEvent(AnalyticsEvent.appReviewAttempt, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
    // Intentionally no Crashlytics for non-error attempt events
  }

  @override
  Future<void> logErrorAppReviewAvailability({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorAppReviewAvailability, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  @override
  Future<void> logErrorAppReviewRequest({
    required String source,
    required String errorMessage,
  }) async {
    await _logEvent(AnalyticsEvent.errorAppReviewRequest, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    }, isError: true);
  }

  /// Internal method to log events with consistent error handling
  Future<void> _logEvent(
    AnalyticsEvent event,
    Map<String, dynamic> parameters, {
    bool isError = false,
  }) async {
    try {
      // Convert parameters to Map<String, Object> and filter out null values
      // Also convert non-string/non-num values to strings for Firebase Analytics
      final analyticsParameters = <String, Object>{};
      for (final entry in parameters.entries) {
        if (entry.value != null) {
          final value = entry.value;
          if (value is String || value is num) {
            analyticsParameters[entry.key] = value;
          } else {
            // Convert other types (like bool) to string
            analyticsParameters[entry.key] = value.toString();
          }
        }
      }

      // Prepare Crashlytics keys if needed
      Future<void> recordNonFatal() async {
        final String? errorMessage =
            parameters[AnalyticsParameters.errorMessage]?.toString();
        final crashKeys = <String, Object>{
          ...analyticsParameters,
          'analytics_event': event.eventName,
        };
        await _crashReportingService.recordNonFatal(
          Exception('${event.eventName}: ${errorMessage ?? 'n/a'}'),
          keys: crashKeys,
        );
      }

      // Record Crashlytics for non-error events.
      if (isError) {
        // Fake Crashlytics is used in debug mode by provider, so record even in debug mode.
        await recordNonFatal();
      }

      // Handle debug/admin short-circuits but still record Crashlytics for errors
      if (await _shouldUseFakeAnalytics()) {
        debugPrint(
          'ANALYTICS SKIPPED (DEBUG): ${event.eventName} - $analyticsParameters',
        );
        return;
      }

      if (_getUserType(_currentUser) == AnalyticsUserType.admin) {
        debugPrint(
          'ANALYTICS SKIPPED (ADMIN): ${event.eventName} - $analyticsParameters',
        );
        return;
      }

      await _analytics.logEvent(
        name: event.eventName,
        parameters: analyticsParameters,
      );

      debugPrint('ANALYTICS: ${event.eventName} logged: $analyticsParameters');
    } catch (e) {
      debugPrint('ANALYTICS ERROR: Failed to log ${event.eventName} - $e');
      // Don't recursively log analytics errors to avoid infinite loops
      if (event != AnalyticsEvent.analyticsError) {
        await logAnalyticsError(e.toString(), event.eventName);
      }
    }
  }

  /// Get user type string for analytics
  String _getUserType(AppUser? user) {
    if (user == null) return AnalyticsUserType.anonymous;
    if (user.isAdmin) return AnalyticsUserType.admin;
    if (user.isAnonymous) return AnalyticsUserType.anonymous;
    return AnalyticsUserType.authenticated;
  }
}
