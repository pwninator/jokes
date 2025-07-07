import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

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
    DateTime? jokeCreationDate,
    bool? hasImages,
  });

  /// Log when user views a joke punchline
  Future<void> logJokePunchlineViewed(
    String jokeId, {
    DateTime? jokeCreationDate,
    bool? hasImages,
  });

  /// Log when user navigates through jokes
  Future<void> logJokeNavigation(
    String jokeId,
    int daysBack, {
    required String method,
  });

  /// Log joke reaction events (heart, thumbs up/down, etc.)
  Future<void> logJokeReaction(
    String jokeId,
    JokeReactionType reactionType,
    bool isAdded,
  );

  /// Log subscription-related events
  Future<void> logSubscriptionEvent(
    SubscriptionEventType eventType,
    SubscriptionSource source, {
    bool? hadPreviousChoice,
    bool? permissionGranted,
  });

  /// Log when subscription prompt is shown
  Future<void> logSubscriptionPromptShown({bool? hadPreviousChoice});

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
  static const bool _isDebugMode = kDebugMode;

  final FirebaseAnalytics _analytics;
  AppUser? _currentUser;

  FirebaseAnalyticsService({FirebaseAnalytics? analytics})
    : _analytics = analytics ?? FirebaseAnalytics.instance;

  @override
  Future<void> initialize() async {
    try {
      if (_isDebugMode) {
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

      if (_isDebugMode) {
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
    DateTime? jokeCreationDate,
    bool? hasImages,
  }) async {
    await _logEvent(AnalyticsEvent.jokeSetupViewed, {
      AnalyticsParameters.jokeId: jokeId,
      if (jokeCreationDate != null)
        AnalyticsParameters.jokeCreationDate:
            jokeCreationDate.toIso8601String(),
      if (hasImages != null) AnalyticsParameters.jokeHasImages: hasImages,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokePunchlineViewed(
    String jokeId, {
    DateTime? jokeCreationDate,
    bool? hasImages,
  }) async {
    await _logEvent(AnalyticsEvent.jokePunchlineViewed, {
      AnalyticsParameters.jokeId: jokeId,
      if (jokeCreationDate != null)
        AnalyticsParameters.jokeCreationDate:
            jokeCreationDate.toIso8601String(),
      if (hasImages != null) AnalyticsParameters.jokeHasImages: hasImages,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeNavigation(
    String jokeId,
    int daysBack, {
    required String method,
  }) async {
    await _logEvent(AnalyticsEvent.jokeNavigated, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.daysBack: daysBack,
      AnalyticsParameters.navigationMethod: method,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logJokeReaction(
    String jokeId,
    JokeReactionType reactionType,
    bool isAdded,
  ) async {
    await _logEvent(AnalyticsEvent.jokeReactionToggled, {
      AnalyticsParameters.jokeId: jokeId,
      AnalyticsParameters.reactionType: reactionType.name,
      AnalyticsParameters.reactionAdded: isAdded,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionEvent(
    SubscriptionEventType eventType,
    SubscriptionSource source, {
    bool? hadPreviousChoice,
    bool? permissionGranted,
  }) async {
    await _logEvent(AnalyticsEvent.subscriptionSettingsToggled, {
      AnalyticsParameters.subscriptionEventType: eventType.value,
      AnalyticsParameters.subscriptionSource: source.value,
      if (hadPreviousChoice != null)
        AnalyticsParameters.hadPreviousChoice: hadPreviousChoice,
      if (permissionGranted != null)
        AnalyticsParameters.permissionGranted: permissionGranted,
      AnalyticsParameters.userType: _getUserType(_currentUser),
    });
  }

  @override
  Future<void> logSubscriptionPromptShown({bool? hadPreviousChoice}) async {
    await _logEvent(AnalyticsEvent.subscriptionPromptShown, {
      if (hadPreviousChoice != null)
        AnalyticsParameters.hadPreviousChoice: hadPreviousChoice,
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
      if (_isDebugMode) {
        debugPrint('ANALYTICS (DEBUG): ${event.eventName} - $parameters');
        return;
      }

      // Convert parameters to Map<String, Object> and filter out null values
      final analyticsParameters = <String, Object>{};
      for (final entry in parameters.entries) {
        if (entry.value != null) {
          analyticsParameters[entry.key] = entry.value;
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
