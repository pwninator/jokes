/// Analytics parameter names for Firebase Analytics
///
/// These parameters provide context for events. Parameter names follow
/// Firebase Analytics conventions:
/// - lowercase with underscores
/// - descriptive but concise
/// - consistent across events
class AnalyticsParameters {
  // Joke-related parameters
  static const String jokeId = 'joke_id';
  static const String jokeCreationDate = 'joke_creation_date';
  static const String jokeHasImages = 'joke_has_images';

  // User interaction parameters
  static const String daysBack = 'days_back';
  static const String reactionType = 'reaction_type';
  static const String reactionAdded = 'reaction_added';
  static const String userType = 'user_type';

  // Navigation parameters
  static const String previousTab = 'previous_tab';
  static const String newTab = 'new_tab';
  static const String navigationMethod = 'navigation_method';

  // Subscription parameters
  static const String subscriptionEventType = 'subscription_event_type';
  static const String subscriptionSource = 'subscription_source';
  static const String hadPreviousChoice = 'had_previous_choice';
  static const String permissionGranted = 'permission_granted';

  // Notification parameters
  static const String notificationId = 'notification_id';
  static const String notificationData = 'notification_data';

  // Error parameters
  static const String errorMessage = 'error_message';
  static const String errorContext = 'error_context';

  // Timing parameters
  static const String timeSpentMs = 'time_spent_ms';
  static const String sessionDurationMs = 'session_duration_ms';
}

/// User type values for analytics
class AnalyticsUserType {
  static const String anonymous = 'anonymous';
  static const String authenticated = 'authenticated';
  static const String admin = 'admin';
}

/// Navigation method values
class AnalyticsNavigationMethod {
  static const String tap = 'tap';
  static const String swipe = 'swipe';
  static const String notification = 'notification';
  static const String programmatic = 'programmatic';
}
