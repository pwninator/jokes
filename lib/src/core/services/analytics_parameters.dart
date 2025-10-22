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
  static const String jokeViewerMode = 'joke_viewer_mode';
  static const String totalJokesViewed = 'total_jokes_viewed';
  static const String totalJokesSaved = 'total_jokes_saved';
  static const String totalJokesShared = 'total_jokes_shared';

  // Joke category parameters
  static const String jokeCategoryId = 'joke_category_id';

  // App usage parameters
  static const String numDaysUsed = 'num_days_used';

  // User interaction parameters
  static const String jokeScrollDepth = 'joke_scroll_depth';
  static const String reactionType = 'reaction_type';
  static const String reactionAdded = 'reaction_added';
  static const String shareMethod = 'share_method';
  static const String shareDestination = 'share_destination';
  static const String shareSuccess = 'share_success';
  static const String userType = 'user_type';

  // Ads
  static const String adUnitId = 'ad_unit_id';
  static const String errorCode = 'error_code';
  static const String adBannerStatus = 'ad_banner_status';

  // Navigation parameters
  static const String previousTab = 'previous_tab';
  static const String newTab = 'new_tab';
  static const String navigationMethod = 'navigation_method';

  // Subscription parameters
  static const String subscriptionSource = 'subscription_source';
  static const String subscriptionHour = 'subscription_hour';
  static const String permissionGranted = 'permission_granted';
  static const String subscriptionOnCount = 'subscription_on_count';

  // Subscription prompt parameters
  static const String subscriptionPromptShownCount =
      'subscription_prompt_shown_count';
  static const String subscriptionPromptAcceptedCount =
      'subscription_prompt_accepted_count';
  static const String subscriptionPromptDeclinedCount =
      'subscription_prompt_declined_count';
  static const String subscriptionPromptErrorCount =
      'subscription_prompt_error_count';

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

  // Share count parameters
  static const String shareInitiatedCount = 'share_initiated_count';
  static const String shareSuccessCount = 'share_success_count';
  static const String shareAbortedCount = 'share_aborted_count';
  static const String shareCanceledCount = 'share_canceled_count';
  static const String shareErrorCount = 'share_error_count';

  // Other joke interaction counters
  static const String jokeNavigatedCount = 'joke_navigated_count';
  static const String jokeViewedCount = 'joke_viewed_count';
  static const String jokeSavedCount = 'joke_saved_count';

  // App-level parameters
  static const String appTheme = 'app_theme';
  static const String screenOrientation = 'screen_orientation';

  // Review prompt parameters
  static const String appReviewAttemptedCount = 'app_review_attempted_count';
  static const String appReviewAcceptedCount = 'app_review_accepted_count';
  static const String appReviewDeclinedCount = 'app_review_declined_count';
  static const String appReviewPromptVariant = 'app_review_prompt_variant';
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
  static const String ctaRevealPunchline = 'cta_reveal_punchline';
  static const String ctaNextJoke = 'cta_next_joke';
}

/// Joke context values for analytics
class AnalyticsJokeContext {
  static const String dailyJokes = 'daily_jokes';
  static const String savedJokes = 'saved_jokes';
  static const String search = 'search';
  static const String category = 'category';
  static const String popular = 'popular';
}

/// Share method values for analytics
class AnalyticsShareMethod {
  static const String images = 'images';
  static const String text = 'text';
  static const String merged = 'merged';
  static const String watermarked = 'watermarked';
}

/// Screen orientation values for analytics
class AnalyticsScreenOrientation {
  static const String portrait = 'portrait';
  static const String landscape = 'landscape';
}
