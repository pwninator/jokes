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
  jokeNavigated('joke_navigated'),

  // Joke reaction events
  jokeSaved('joke_saved'),

  // Joke sharing events
  jokeShared('joke_shared'),

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

  // App navigation events
  tabChanged('tab_changed'),

  // Error events
  analyticsError('analytics_error');

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
  settings('settings'),
  admin('admin');

  const AppTab(this.value);
  final String value;
}
