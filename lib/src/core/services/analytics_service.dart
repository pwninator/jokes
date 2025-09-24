import 'dart:async';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/utils/device_utils.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Abstract interface for analytics service
/// This allows for easy mocking in tests
abstract class AnalyticsService {
  /// Initialize analytics and set user properties
  Future<void> initialize();

  /// Set user properties for analytics
  Future<void> setUserProperties(AppUser? user);

  /// Log when user views a joke setup
  void logJokeSetupViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  });

  /// Log when user views a joke punchline
  void logJokePunchlineViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  });

  /// Log when a joke is fully viewed (setup and punchline each viewed ≥ 2s sequentially)
  void logJokeViewed(
    String jokeId, {
    required int totalJokesViewed,
    required String navigationMethod,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  });

  /// Log when user navigates through jokes
  void logJokeNavigation(
    String jokeId,
    int jokeScrollDepth, {
    required String method,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  });

  /// Log when a joke is saved
  void logJokeSaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  });

  /// Log when a joke is unsaved
  void logJokeUnsaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  });

  /// Log successful joke share events
  void logJokeShareSuccess(
    String jokeId, {
    required String jokeContext,
    String? shareDestination,
    required int totalJokesShared,
  });

  /// Share funnel: user initiated sharing
  void logJokeShareInitiated(String jokeId, {required String jokeContext});

  /// Share funnel: user canceled/dismissed share sheet (failure, not error)
  void logJokeShareCanceled(
    String jokeId, {
    required String jokeContext,
    String? shareDestination,
  });

  /// Share funnel: error occurred during sharing
  void logErrorJokeShare(
    String jokeId, {
    required String jokeContext,
    required String errorMessage,
    String? errorContext,
    String? exceptionType,
  });

  /// Subscription: toggled on in settings
  void logSubscriptionOnSettings();

  /// Subscription: accepted prompt and permission granted
  void logSubscriptionOnPrompt();

  /// Subscription: toggled off in settings
  void logSubscriptionOffSettings();

  /// Subscription: time changed in settings
  void logSubscriptionTimeChanged({required int subscriptionHour});

  /// Subscription: chose "Maybe later" in prompt
  void logSubscriptionDeclinedMaybeLater();

  /// Subscription: denied permissions from settings flow
  void logSubscriptionDeclinedPermissionsInSettings();

  /// Subscription: denied permissions from prompt flow
  void logSubscriptionDeclinedPermissionsInPrompt();

  /// Log when subscription prompt is shown
  void logSubscriptionPromptShown();

  /// Subscription prompt show/dismiss errors
  void logErrorSubscriptionPrompt({
    required String errorMessage,
    String? phase,
  });

  /// Subscription permission errors from prompt/settings flows
  void logErrorSubscriptionPermission({
    required String source,
    required String errorMessage,
  });

  /// Log when user taps on a notification to open the app
  void logNotificationTapped({String? jokeId, String? notificationId});

  /// Notification handling errors
  void logErrorNotificationHandling({
    String? notificationId,
    String? phase,
    required String errorMessage,
  });

  /// Remote Config errors
  void logErrorRemoteConfig({required String errorMessage, String? phase});

  /// Log tab navigation events
  void logTabChanged(
    AppTab previousTab,
    AppTab newTab, {
    required String method,
  });

  /// Route/navigation errors
  void logErrorRouteNavigation({
    String? previousRoute,
    String? newRoute,
    String? method,
    required String errorMessage,
  });

  /// Log errors that occur during analytics
  void logAnalyticsError(String errorMessage, String context);

  /// Save reaction errors
  void logErrorJokeSave({
    required String jokeId,
    required String action,
    required String errorMessage,
  });

  /// Image-related errors
  void logErrorImagePrecache({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  });

  void logErrorImageLoad({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  });

  void logErrorJokeImagesMissing({
    required String jokeId,
    required String missingParts,
  });

  /// Data/content loading errors
  void logErrorJokesLoad({
    required String source,
    required String errorMessage,
  });

  void logErrorJokeFetch({
    required String jokeId,
    required String errorMessage,
  });

  /// App usage: unique day incremented
  void logAppUsageDayIncremented({required int numDaysUsed});

  /// Log joke search completion
  void logJokeSearch({
    required int queryLength,
    required String scope,
    required int resultsCount,
  });

  /// Log when user taps Similar to perform a prefilled search
  void logJokeSearchSimilar({
    required int queryLength,
    required String jokeContext,
  });

  /// Log when a user submits app feedback (no parameters)
  void logFeedbackSubmitted();

  /// Log when the feedback dialog is shown
  void logFeedbackDialogShown();

  // Auth
  void logErrorAuthSignIn({
    required String source,
    required String errorMessage,
  });

  // Settings / subscriptions
  void logErrorSubscriptionToggle({
    required String source,
    required String errorMessage,
  });

  void logErrorSubscriptionTimeUpdate({
    required String source,
    required String errorMessage,
  });

  // Feedback
  void logErrorFeedbackSubmit({required String errorMessage});

  // App review
  void logAppReviewAttempt({required String source});

  void logErrorAppReviewAvailability({
    required String source,
    required String errorMessage,
  });

  void logErrorAppReviewRequest({
    required String source,
    required String errorMessage,
  });

  /// Settings: joke viewer setting changed
  void logJokeViewerSettingChanged({required String mode});
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
        AppLogger.warn('ANALYTICS WARN: Device check failed - $e');
        return true;
      }
    }
    return false;
  }

  @override
  Future<void> initialize() async {
    try {
      if (await _shouldUseFakeAnalytics()) {
        AppLogger.debug(
          'ANALYTICS: Initializing in debug mode on non-physical device (events will not be sent)',
        );
        return;
      }

      // Set default user properties
      await _analytics.setDefaultEventParameters({
        AnalyticsParameters.userType: AnalyticsUserType.anonymous,
      });

      AppLogger.debug('ANALYTICS: Firebase Analytics initialized');
    } catch (e) {
      AppLogger.warn('ANALYTICS ERROR: Failed to initialize - $e');
    }
  }

  @override
  Future<void> setUserProperties(AppUser? user) async {
    _currentUser = user;

    try {
      final userType = _getUserType(user);

      if (await _shouldUseFakeAnalytics()) {
        AppLogger.debug(
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

      AppLogger.debug('ANALYTICS: User properties set - type: $userType');
    } catch (e) {
      AppLogger.warn('ANALYTICS ERROR: Failed to set user properties - $e');
    }
  }

  @override
  void logJokeSetupViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  }) {
    _logEvent(AnalyticsEvent.jokeSetupViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.jokeViewerMode: jokeViewerMode.name,
    });
  }

  @override
  void logJokePunchlineViewed(
    String jokeId, {
    required String navigationMethod,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  }) {
    _logEvent(AnalyticsEvent.jokePunchlineViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.jokeViewerMode: jokeViewerMode.name,
    });
  }

  @override
  void logJokeViewed(
    String jokeId, {
    required int totalJokesViewed,
    required String navigationMethod,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  }) {
    _logEvent(AnalyticsEvent.jokeViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.totalJokesViewed: totalJokesViewed,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.jokeViewerMode: jokeViewerMode.name,
      AnalyticsParameters.jokeViewedCount: 1,
    });
  }

  @override
  void logJokeNavigation(
    String jokeId,
    int jokeScrollDepth, {
    required String method,
    required String jokeContext,
    required JokeViewerMode jokeViewerMode,
  }) {
    _logEvent(AnalyticsEvent.jokeNavigated, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeScrollDepth: jokeScrollDepth,
      AnalyticsParameters.navigationMethod: method,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.jokeViewerMode: jokeViewerMode.name,
      AnalyticsParameters.jokeNavigatedCount: 1,
    });
  }

  @override
  void logJokeSaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  }) {
    _logEvent(AnalyticsEvent.jokeSaved, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.totalJokesSaved: totalJokesSaved,
      AnalyticsParameters.jokeSavedCount: 1,
    });
  }

  @override
  void logJokeUnsaved(
    String jokeId, {
    required String jokeContext,
    required int totalJokesSaved,
  }) {
    _logEvent(AnalyticsEvent.jokeUnsaved, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.totalJokesSaved: totalJokesSaved,
      AnalyticsParameters.jokeSavedCount: -1,
    });
  }

  @override
  void logJokeShareSuccess(
    String jokeId, {
    required String jokeContext,
    String? shareDestination,
    required int totalJokesShared,
  }) {
    _logEvent(AnalyticsEvent.jokeShareSuccess, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.totalJokesShared: totalJokesShared,
      AnalyticsParameters.shareSuccessCount: 1,
      if (shareDestination != null)
        AnalyticsParameters.shareDestination: shareDestination,
    });
  }

  @override
  void logJokeShareInitiated(String jokeId, {required String jokeContext}) {
    _logEvent(AnalyticsEvent.jokeShareInitiated, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.shareInitiatedCount: 1,
    });
  }

  @override
  void logJokeShareCanceled(
    String jokeId, {
    required String jokeContext,
    String? shareDestination,
  }) {
    _logEvent(AnalyticsEvent.jokeShareCanceled, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.shareCanceledCount: 1,
      if (shareDestination != null)
        AnalyticsParameters.shareDestination: shareDestination,
    });
  }

  @override
  void logErrorJokeShare(
    String jokeId, {
    required String jokeContext,
    required String errorMessage,
    String? errorContext,
    String? exceptionType,
  }) {
    _logEvent(AnalyticsEvent.errorJokeShare, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.shareErrorCount: 1,
      if (errorContext != null) AnalyticsParameters.errorContext: errorContext,
      if (exceptionType != null)
        AnalyticsParameters.exceptionType: exceptionType,
    }, isError: true);
  }

  @override
  void logSubscriptionOnSettings() {
    _logEvent(AnalyticsEvent.subscriptionOnSettings, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.permissionGranted: true,
      AnalyticsParameters.subscriptionOnCount: 1,
    });
  }

  @override
  void logSubscriptionOnPrompt() {
    _logEvent(AnalyticsEvent.subscriptionOnPrompt, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.popup.value,
      AnalyticsParameters.permissionGranted: true,
      AnalyticsParameters.subscriptionPromptAcceptedCount: 1,
      AnalyticsParameters.subscriptionOnCount: 1,
    });
  }

  @override
  void logSubscriptionOffSettings() {
    _logEvent(AnalyticsEvent.subscriptionOffSettings, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.subscriptionOnCount: -1,
    });
  }

  @override
  void logSubscriptionTimeChanged({required int subscriptionHour}) {
    _logEvent(AnalyticsEvent.subscriptionTimeChanged, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.permissionGranted: true,
      AnalyticsParameters.subscriptionHour: subscriptionHour,
    });
  }

  @override
  void logSubscriptionDeclinedMaybeLater() {
    _logEvent(AnalyticsEvent.subscriptionDeclinedMaybeLater, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.popup.value,
      AnalyticsParameters.subscriptionPromptDeclinedCount: 1,
    });
  }

  @override
  void logSubscriptionDeclinedPermissionsInSettings() {
    _logEvent(AnalyticsEvent.subscriptionDeclinedPermissions, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.settings.value,
      AnalyticsParameters.permissionGranted: false,
    });
  }

  @override
  void logSubscriptionDeclinedPermissionsInPrompt() {
    _logEvent(AnalyticsEvent.subscriptionDeclinedPermissions, {
      AnalyticsParameters.subscriptionSource: SubscriptionSource.popup.value,
      AnalyticsParameters.permissionGranted: false,
      AnalyticsParameters.subscriptionPromptDeclinedCount: 1,
    });
  }

  @override
  void logSubscriptionPromptShown() {
    _logEvent(AnalyticsEvent.subscriptionPromptShown, {
      AnalyticsParameters.subscriptionPromptShownCount: 1,
    });
  }

  @override
  void logErrorSubscriptionPrompt({
    required String errorMessage,
    String? phase,
  }) {
    _logEvent(AnalyticsEvent.errorSubscriptionPrompt, {
      AnalyticsParameters.errorMessage: errorMessage,
      if (phase != null) AnalyticsParameters.phase: phase,
      AnalyticsParameters.subscriptionPromptErrorCount: 1,
    }, isError: true);
  }

  @override
  void logErrorSubscriptionPermission({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorSubscriptionPermission, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logNotificationTapped({String? jokeId, String? notificationId}) {
    _logEvent(AnalyticsEvent.notificationTapped, {
      if (jokeId != null) AnalyticsParameters.jokeId: jokeId,
      if (notificationId != null)
        AnalyticsParameters.notificationId: notificationId,
    });
  }

  @override
  void logErrorNotificationHandling({
    String? notificationId,
    String? phase,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorNotificationHandling, {
      if (notificationId != null)
        AnalyticsParameters.notificationId: notificationId,
      if (phase != null) AnalyticsParameters.phase: phase,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorRemoteConfig({required String errorMessage, String? phase}) {
    _logEvent(AnalyticsEvent.errorRemoteConfig, {
      if (phase != null) AnalyticsParameters.phase: phase,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logTabChanged(
    AppTab previousTab,
    AppTab newTab, {
    required String method,
  }) {
    _logEvent(AnalyticsEvent.tabChanged, {
      AnalyticsParameters.previousTab: previousTab.value,
      AnalyticsParameters.newTab: newTab.value,
      AnalyticsParameters.navigationMethod: method,
    });
  }

  @override
  void logErrorRouteNavigation({
    String? previousRoute,
    String? newRoute,
    String? method,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorRouteNavigation, {
      if (previousRoute != null) AnalyticsParameters.previousTab: previousRoute,
      if (newRoute != null) AnalyticsParameters.newTab: newRoute,
      if (method != null) AnalyticsParameters.navigationMethod: method,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logAnalyticsError(String errorMessage, String context) {
    _logEvent(AnalyticsEvent.analyticsError, {
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.errorContext: context,
    }, isError: true);
  }

  @override
  void logErrorJokeSave({
    required String jokeId,
    required String action,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorJokeSave, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.action: action,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorImagePrecache({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorImagePrecache, {
      if (jokeId != null) AnalyticsParameters.jokeId: jokeId,
      if (imageType != null) AnalyticsParameters.imageType: imageType,
      if (imageUrlHash != null) AnalyticsParameters.imageUrlHash: imageUrlHash,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorImageLoad({
    String? jokeId,
    String? imageType,
    String? imageUrlHash,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorImageLoad, {
      if (jokeId != null) AnalyticsParameters.jokeId: jokeId,
      if (imageType != null) AnalyticsParameters.imageType: imageType,
      if (imageUrlHash != null) AnalyticsParameters.imageUrlHash: imageUrlHash,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorJokeImagesMissing({
    required String jokeId,
    required String missingParts,
  }) {
    _logEvent(AnalyticsEvent.errorJokeImagesMissing, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.errorContext: missingParts,
    }, isError: true);
  }

  @override
  void logErrorJokesLoad({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorJokesLoad, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorJokeFetch({
    required String jokeId,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorJokeFetch, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logAppUsageDayIncremented({required int numDaysUsed}) {
    _logEvent(AnalyticsEvent.appUsageDayIncremented, {
      AnalyticsParameters.numDaysUsed: numDaysUsed,
    });
  }

  @override
  void logJokeSearch({
    required int queryLength,
    required String scope,
    required int resultsCount,
  }) {
    _logEvent(AnalyticsEvent.jokeSearch, {
      'query_length': queryLength,
      'scope': scope,
      'results_count': resultsCount,
    });
  }

  @override
  void logJokeSearchSimilar({
    required int queryLength,
    required String jokeContext,
  }) {
    _logEvent(AnalyticsEvent.jokeSearchSimilar, {
      'query_length': queryLength,
      AnalyticsParameters.jokeContext: jokeContext,
    });
  }

  @override
  void logJokeViewerSettingChanged({required String mode}) {
    _logEvent(AnalyticsEvent.jokeViewerSettingChanged, {'mode': mode});
  }

  @override
  void logFeedbackSubmitted() {
    // Per requirements, log event with no parameters
    _logEvent(AnalyticsEvent.feedbackSubmitted, {});
  }

  @override
  void logFeedbackDialogShown() {
    _logEvent(AnalyticsEvent.feedbackDialogShown, {});
  }

  // Auth
  @override
  void logErrorAuthSignIn({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorAuthSignIn, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  // Settings / subscriptions
  @override
  void logErrorSubscriptionToggle({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorSubscriptionToggle, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorSubscriptionTimeUpdate({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorSubscriptionTimeUpdate, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  // Feedback
  @override
  void logErrorFeedbackSubmit({required String errorMessage}) {
    _logEvent(AnalyticsEvent.errorFeedbackSubmit, {
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  // App review
  @override
  void logAppReviewAttempt({required String source}) {
    _logEvent(AnalyticsEvent.appReviewAttempt, {
      AnalyticsParameters.source: source,
    });
    // Intentionally no Crashlytics for non-error attempt events
  }

  @override
  void logErrorAppReviewAvailability({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorAppReviewAvailability, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  @override
  void logErrorAppReviewRequest({
    required String source,
    required String errorMessage,
  }) {
    _logEvent(AnalyticsEvent.errorAppReviewRequest, {
      AnalyticsParameters.source: source,
      AnalyticsParameters.errorMessage: errorMessage,
    }, isError: true);
  }

  /// Internal method to log events with consistent error handling
  void _logEvent(
    AnalyticsEvent event,
    Map<String, dynamic> parameters, {
    bool isError = false,
  }) {
    // Fire-and-forget: execute analytics work in a microtask
    scheduleMicrotask(() async {
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

        if (isError) {
          await recordNonFatal();
        }

        // Handle debug/admin short-circuits but still record Crashlytics for errors
        if (await _shouldUseFakeAnalytics()) {
          AppLogger.debug(
            'ANALYTICS SKIPPED (DEBUG): ${event.eventName} - $analyticsParameters',
          );
          return;
        }

        if (_getUserType(_currentUser) == AnalyticsUserType.admin) {
          AppLogger.debug(
            'ANALYTICS SKIPPED (ADMIN): ${event.eventName} - $analyticsParameters',
          );
          return;
        }

        await _analytics.logEvent(
          name: event.eventName,
          parameters: analyticsParameters,
        );

        AppLogger.debug(
          'ANALYTICS: ${event.eventName} logged: $analyticsParameters',
        );
      } catch (e) {
        AppLogger.warn(
          'ANALYTICS ERROR: Failed to log ${event.eventName} - $e',
        );
        // Don't recursively log analytics errors to avoid infinite loops
        if (event != AnalyticsEvent.analyticsError) {
          logAnalyticsError(e.toString(), event.eventName);
        }
      }
    });
  }

  /// Get user type string for analytics
  String _getUserType(AppUser? user) {
    if (user == null) return AnalyticsUserType.anonymous;
    if (user.isAdmin) return AnalyticsUserType.admin;
    if (user.isAnonymous) return AnalyticsUserType.anonymous;
    return AnalyticsUserType.authenticated;
  }
}
