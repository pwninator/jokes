import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

/// Simple persistence for the one-time feedback dialog viewed flag
class FeedbackPromptStateStore {
  FeedbackPromptStateStore({required SettingsService settingsService})
    : _settings = settingsService;

  static const String _viewedKey = 'feedback_dialog_viewed';
  final SettingsService _settings;

  Future<bool> hasViewed() async {
    try {
      return _settings.getBool(_viewedKey) ?? false;
    } catch (e) {
      AppLogger.warn('FEEDBACK_STORE read error: $e');
      return false;
    }
  }

  Future<void> markViewed() async => setViewed(true);

  Future<void> setViewed(bool value) async {
    try {
      if (value) {
        await _settings.setBool(_viewedKey, true);
      } else {
        await _settings.remove(_viewedKey);
      }
    } catch (e) {
      AppLogger.warn('FEEDBACK_STORE write error: $e');
    }
  }
}

final feedbackPromptStateStoreProvider = Provider<FeedbackPromptStateStore>((
  ref,
) {
  final settings = ref.watch(settingsServiceProvider);
  return FeedbackPromptStateStore(settingsService: settings);
});
