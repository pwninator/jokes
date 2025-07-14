import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

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
    required bool hasImages,
    required String navigationMethod,
    required String jokeContext,
  });

  /// Log when user views a joke punchline
  Future<void> logJokePunchlineViewed(
    String jokeId, {
    required bool hasImages,
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

  /// Log joke save events (when user saves/unsaves a joke)
  Future<void> logJokeSaved(
    String jokeId,
    bool isAdded, {
    required String jokeContext,
  });

  /// Log joke share events (when user shares a joke)
  Future<void> logJokeShared(
    String jokeId, {
    required String jokeContext,
    String? shareMethod,
    bool? shareSuccess,
  });

  /// Log subscription-related events
  Future<void> logSubscriptionEvent(
    SubscriptionEventType eventType,
    SubscriptionSource source, {
    bool? permissionGranted,
    int? subscriptionHour,
  });

  /// Log when subscription prompt is shown
  Future<void> logSubscriptionPromptShown();

  /// Log when user taps on a notification to open the app
  Future<void> logNotificationTapped({String? jokeId, String? notificationId});

  /// Log tab navigation events
  Future<void> logTabChanged(
    AppTab previousTab,
    AppTab newTab, {
    required String method,
  });

  /// Log errors that occur during analytics
  Future<void> logAnalyticsError(String errorMessage, String context);
}

/// Firebase Analytics implementation of the analytics service
class FirebaseAnalyticsService implements AnalyticsService {
  static const bool _useFakeAnalytics = kDebugMode;

  final FirebaseAnalytics _analytics;
  AppUser? _currentUser;

  FirebaseAnalyticsService({FirebaseAnalytics? analytics})
    : _analytics = analytics ?? FirebaseAnalytics.instance;

  @override
  Future<void> initialize() async {
    try {
      if (_useFakeAnalytics) {
        debugPrint(
          'ANALYTICS: Initializing in debug mode (events will not be sent)',
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

      if (_useFakeAnalytics) {
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
    required bool hasImages,
    required String navigationMethod,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSetupViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeHasImages: hasImages,
      AnalyticsParameters.navigationMethod: navigationMethod,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokePunchlineViewed(
    String jokeId, {
    required bool hasImages,
    required String navigationMethod,
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokePunchlineViewed, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeHasImages: hasImages,
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
    String jokeId,
    bool isAdded, {
    required String jokeContext,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSaved, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.reactionAdded: isAdded,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeShared(
    String jokeId, {
    required String jokeContext,
    String? shareMethod,
    bool? shareSuccess,
  }) async {
    await _logEvent(AnalyticsEvent.jokeShared, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.jokeContext: jokeContext,
      AnalyticsParameters.userType: _getUserType(_currentUser),
      if (shareMethod != null) AnalyticsParameters.shareMethod: shareMethod,
      if (shareSuccess != null) AnalyticsParameters.shareSuccess: shareSuccess,
    });
  }

  @override
  Future<void> logSubscriptionEvent(
    SubscriptionEventType eventType,
    SubscriptionSource source, {
    bool? permissionGranted,
    int? subscriptionHour,
  }) async {
    await _logEvent(AnalyticsEvent.subscriptionSettingsToggled, {
      AnalyticsParameters.subscriptionEventType: eventType.value,
      AnalyticsParameters.subscriptionSource: source.value,
      if (permissionGranted != null)
        AnalyticsParameters.permissionGranted: permissionGranted,
      if (subscriptionHour != null)
        AnalyticsParameters.subscriptionHour: subscriptionHour,
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
  Future<void> logAnalyticsError(String errorMessage, String context) async {
    await _logEvent(AnalyticsEvent.analyticsError, {
      AnalyticsParameters.errorMessage: errorMessage,
      AnalyticsParameters.errorContext: context,
    });
  }

  /// Internal method to log events with consistent error handling
  Future<void> _logEvent(
    AnalyticsEvent event,
    Map<String, dynamic> parameters,
  ) async {
    try {
      if (_useFakeAnalytics) {
        debugPrint('ANALYTICS (DEBUG): ${event.eventName} - $parameters');
        return;
      }

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

      await _analytics.logEvent(
        name: event.eventName,
        parameters: analyticsParameters,
      );

      debugPrint('ANALYTICS: ${event.eventName} logged');
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
