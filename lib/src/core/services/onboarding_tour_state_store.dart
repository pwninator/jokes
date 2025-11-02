import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

/// Persists whether the onboarding tour has been completed.
class OnboardingTourStateStore {
  OnboardingTourStateStore({required SettingsService settingsService})
    : _settings = settingsService;

  static const String _completedKey = 'onboarding_tour_completed';
  final SettingsService _settings;

  Future<bool> hasCompleted() async {
    try {
      final value = _settings.getBool(_completedKey);
      if (value == null) {
        await _settings.setBool(_completedKey, false);
        return false;
      }
      return value;
    } catch (e) {
      AppLogger.warn('ONBOARDING_TOUR_STORE read error: $e');
      return false;
    }
  }

  Future<void> markCompleted() async => setCompleted(true);

  Future<void> setCompleted(bool value) async {
    try {
      await _settings.setBool(_completedKey, value);
    } catch (e) {
      AppLogger.warn('ONBOARDING_TOUR_STORE write error: $e');
    }
  }
}

final onboardingTourStateStoreProvider = Provider<OnboardingTourStateStore>((
  ref,
) {
  final settings = ref.read(settingsServiceProvider);
  return OnboardingTourStateStore(settingsService: settings);
});
