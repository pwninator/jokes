import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

/// Simple persistence for the one-time review prompt attempt flag
class ReviewPromptStateStore {
  ReviewPromptStateStore({required SettingsService settingsService})
    : _settings = settingsService;

  static const String _requestedKey = 'review_prompt_requested';
  final SettingsService _settings;

  bool hasRequested() {
    try {
      return _settings.getBool(_requestedKey) ?? false;
    } catch (e) {
      AppLogger.warn('REVIEW_STORE read error: $e');
      return false;
    }
  }

  Future<void> markRequested() async {
    try {
      await _settings.setBool(_requestedKey, true);
    } catch (e) {
      AppLogger.warn('REVIEW_STORE write error: $e');
    }
  }
}

final reviewPromptStateStoreProvider = Provider<ReviewPromptStateStore>((ref) {
  final settings = ref.read(settingsServiceProvider);
  return ReviewPromptStateStore(settingsService: settings);
});
