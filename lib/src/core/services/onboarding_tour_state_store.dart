import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

final onboardingTourStateStoreProvider = Provider<OnboardingTourStateStore>((
  ref,
) {
  final settings = ref.read(settingsServiceProvider);
  final remoteValues = ref.watch(remoteConfigValuesProvider);
  return OnboardingTourStateStore(
    settingsService: settings,
    remoteConfigValues: remoteValues,
  );
});

/// Persists whether the onboarding tour has been completed.
class OnboardingTourStateStore {
  OnboardingTourStateStore({
    required SettingsService settingsService,
    required RemoteConfigValues remoteConfigValues,
  }) : _settings = settingsService,
       _remoteConfig = remoteConfigValues;

  static const String _completedKey = 'onboarding_tour_completed';
  final SettingsService _settings;
  final RemoteConfigValues _remoteConfig;

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
      }
      return tourAlreadyCompleted;
    } catch (e) {
      AppLogger.warn('ONBOARDING_TOUR_STORE read error: $e');
      return false;
    }
  }

  Future<void> markCompleted() async => setCompleted(true);

  Future<bool> shouldShowTour() async => !(await hasCompleted());

  Future<void> setCompleted(bool value) async {
    try {
      await _settings.setBool(_completedKey, value);
      AppLogger.debug('ONBOARDING_TOUR: Store set completed to: $value');
    } catch (e) {
      AppLogger.warn('ONBOARDING_TOUR: Store write error: $e');
    }
  }
}
