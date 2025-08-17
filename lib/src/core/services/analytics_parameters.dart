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
  static const String jokeContext = 'joke_context';
  static const String totalJokesViewed = 'total_jokes_viewed';
  static const String totalJokesSaved = 'total_jokes_saved';
  static const String totalJokesShared = 'total_jokes_shared';

  // User interaction parameters
  static const String jokeScrollDepth = 'joke_scroll_depth';
  static const String reactionType = 'reaction_type';
  static const String reactionAdded = 'reaction_added';
  static const String shareMethod = 'share_method';
  static const String shareSuccess = 'share_success';
  static const String userType = 'user_type';

  // Navigation parameters
  static const String previousTab = 'previous_tab';
  static const String newTab = 'new_tab';
  static const String navigationMethod = 'navigation_method';

  // Subscription parameters
  static const String subscriptionSource = 'subscription_source';
  static const String subscriptionHour = 'subscription_hour';
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

  // Extended diagnostics
  static const String phase = 'phase';
  static const String action = 'action';
  static const String source = 'source';
  static const String status = 'status';
  static const String imageType = 'image_type';
  static const String imageUrlHash = 'image_url_hash';
  static const String exceptionType = 'exception_type';
}

/// User type values for analytics
class AnalyticsUserType {
  static const String anonymous = 'anonymous';
  static const String authenticated = 'authenticated';
  static const String admin = 'admin';
}

/// Navigation method values
class AnalyticsNavigationMethod {
  static const String none = 'none';
  static const String tap = 'tap';
  static const String swipe = 'swipe';
  static const String notification = 'notification';
  static const String programmatic = 'programmatic';
}

/// Joke context values for analytics
class AnalyticsJokeContext {
  static const String dailyJokes = 'daily_jokes';
  static const String savedJokes = 'saved_jokes';
}

/// Share method values for analytics
class AnalyticsShareMethod {
  static const String images = 'images';
  static const String text = 'text';
  static const String merged = 'merged';
  static const String watermarked = 'watermarked';
}
