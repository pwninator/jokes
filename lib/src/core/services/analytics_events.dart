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
  jokeNavigated('joke_navigated'),

  // Joke reaction events
  jokeSaved('joke_saved'),

  // Joke sharing events
  jokeShared('joke_shared'),

  // Subscription events
  subscriptionPromptShown('subscription_prompt_shown'),
  subscriptionPromptAccepted('subscription_prompt_accepted'),
  subscriptionPromptDeclined('subscription_prompt_declined'),
  subscriptionSettingsToggled('subscription_settings_toggled'),

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

/// Subscription event types for more granular tracking
enum SubscriptionEventType {
  subscribed('subscribed'),
  unsubscribed('unsubscribed'),
  declined('declined'),
  maybeLater('maybe_later');

  const SubscriptionEventType(this.value);
  final String value;
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
