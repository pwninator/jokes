import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

final onboardingTourStateStoreProvider = Provider<OnboardingTourStateStore>((
  ref,
) {
  final settings = ref.read(settingsServiceProvider);
  final remoteValues = ref.watch(remoteConfigValuesProvider);
  final analytics = ref.read(analyticsServiceProvider);
  return OnboardingTourStateStore(
    settingsService: settings,
    remoteConfigValues: remoteValues,
    analyticsService: analytics,
    getFeedScreenStatus: () => ref.read(feedScreenStatusProvider),
  );
});

/// Persists whether the onboarding tour has been completed.
class OnboardingTourStateStore {
  OnboardingTourStateStore({
    required SettingsService settingsService,
    required RemoteConfigValues remoteConfigValues,
    required AnalyticsService analyticsService,
    required bool Function() getFeedScreenStatus,
  }) : _settings = settingsService,
       _remoteConfig = remoteConfigValues,
       _analytics = analyticsService,
       _getFeedScreenStatus = getFeedScreenStatus;

  static const String _completedKey = 'onboarding_tour_completed';
  final SettingsService _settings;
  final RemoteConfigValues _remoteConfig;
  final AnalyticsService _analytics;
  final bool Function() _getFeedScreenStatus;

  Future<bool> hasCompleted() async {
    try {
      bool? tourAlreadyCompleted = _settings.getBool(_completedKey);
      if (tourAlreadyCompleted == null) {
        // Initialize the value from remote config
        final shouldShowTour = _remoteConfig.getBool(
          RemoteParam.onboardingShowTour,
        );
        tourAlreadyCompleted = !shouldShowTour;
        await setCompleted(tourAlreadyCompleted);
        // If remote config initialized tour as already completed, log skipped
        if (!shouldShowTour) {
          _analytics.logTourSkipped();
        }
      }
      return tourAlreadyCompleted;
    } catch (e) {
      AppLogger.warn('ONBOARDING_TOUR_STORE read error: $e');
      return false;
    }
  }

  Future<void> markCompleted() async => setCompleted(true);

  Future<bool> shouldShowTour() async {
    // Tour should only show if feed screen is enabled
    if (!_getFeedScreenStatus()) {
      AppLogger.debug(
        'ONBOARDING_TOUR: Feed screen is disabled, skipping tour',
      );
      return false;
    }
    return !(await hasCompleted());
  }

  Future<void> setCompleted(bool value) async {
    try {
      await _settings.setBool(_completedKey, value);
      AppLogger.debug('ONBOARDING_TOUR: Store set completed to: $value');
    } catch (e) {
      AppLogger.warn('ONBOARDING_TOUR: Store write error: $e');
    }
  }
}
