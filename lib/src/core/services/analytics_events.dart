/// Analytics event names for Firebase Analytics
///
/// These events track user interactions and behaviors throughout the app.
/// Each event name follows Firebase Analytics naming conventions:
/// - lowercase with underscores
/// - descriptive but concise
/// - consistent naming patterns
enum AnalyticsEvent {
  // Joke viewing events
  jokeSetupViewed('joke_setup_viewed'),
  jokePunchlineViewed('joke_punchline_viewed'),
  jokeViewed('joke_viewed'),
  jokeViewedHigh('joke_viewed_high'),
  jokeNavigated('joke_navigated'),
  // Joke search event
  jokeSearch('joke_search'),
  // Similar search CTA event
  jokeSearchSimilar('joke_search_similar'),

  // Joke category events
  jokeCategoryViewed('joke_category_viewed'),

  // Joke reaction events
  jokeSaved('joke_saved'),
  jokeUnsaved('joke_unsaved'),

  // Joke sharing events
  jokeShareSuccess('joke_share_success'),
  // Share funnel flow events
  jokeShareInitiated('joke_share_initiated'),
  jokeShareCanceled('joke_share_canceled'),
  // Share aborted explicitly by user via preparation dialog
  jokeShareAborted('joke_share_aborted'),
  // Share funnel error events
  errorJokeShare('error_joke_share'),

  // Subscription events
  subscriptionPromptShown('subscription_prompt_shown'),
  subscriptionOnSettings('subscription_on_settings'),
  subscriptionOnPrompt('subscription_on_prompt'),
  subscriptionOffSettings('subscription_off_settings'),
  subscriptionTimeChanged('subscription_time_changed'),
  subscriptionDeclinedMaybeLater('subscription_declined_maybe_later'),
  subscriptionDeclinedPermissions('subscription_declined_permissions'),

  // Notification events
  notificationTapped('notification_tapped'),

  // Image reliability
  errorImageLoad('error_image_load'),
  errorImagePrecache('error_image_precache'),
  errorJokeImagesMissing('error_joke_images_missing'),

  // Data/content loading
  errorJokesLoad('error_jokes_load'),
  errorJokeFetch('error_joke_fetch'),

  // Reactions
  errorJokeSave('error_joke_save'),
  errorJokeReaction('error_joke_reaction'),

  // App navigation events
  tabChanged('tab_changed'),

  // App usage events
  appUsageDayIncremented('app_usage_day_incremented'),
  appReturnDaysIncremented('app_return_days_incremented'),

  // Feedback
  feedbackSubmitted('feedback_submitted'),
  feedbackDialogShown('feedback_dialog_shown'),

  // Navigation/routing
  errorRouteNavigation('error_route_navigation'),

  // Subscriptions and notifications
  errorSubscriptionPrompt('error_subscription_prompt'),
  errorSubscriptionPermission('error_subscription_permission'),
  errorNotificationHandling('error_notification_handling'),

  // Remote Config
  errorRemoteConfig('error_remote_config'),

  // Error events
  analyticsError('analytics_error'),

  // Auth
  errorAuthSignIn('error_auth_sign_in'),

  // Settings / subscriptions errors
  errorSubscriptionToggle('error_subscription_toggle'),
  errorSubscriptionTimeUpdate('error_subscription_time_update'),

  // Feedback
  errorFeedbackSubmit('error_feedback_submit'),

  // App review
  appReviewAttempt('app_review_attempt'),
  appReviewAccepted('app_review_accepted'),
  appReviewDeclined('app_review_declined'),
  errorAppReviewAvailability('error_app_review_availability'),
  errorAppReviewRequest('error_app_review_request'),

  // Settings
  jokeViewerSettingChanged('joke_viewer_setting_changed'),
  privacyPolicyOpened('privacy_policy_opened'),

  // Ad events
  adBannerSkipped('ad_banner_skipped'),
  adBannerLoaded('ad_banner_loaded'),
  adBannerFailedToLoad('ad_banner_failed_to_load'),
  adBannerClicked('ad_banner_clicked'),
  errorAdBanner('error_ad_banner');

  const AnalyticsEvent(this.eventName);

  /// The event name to send to Firebase Analytics
  final String eventName;
}

/// Subscription source tracking (where the subscription action originated)
enum SubscriptionSource {
  popup('popup'),
  settings('settings');

  const SubscriptionSource(this.value);
  final String value;
}

/// Tab names for navigation tracking
enum AppTab {
  dailyJokes('daily_jokes'),
  savedJokes('saved_jokes'),
  discover('discover'),
  settings('settings'),
  admin('admin');

  const AppTab(this.value);
  final String value;
}
