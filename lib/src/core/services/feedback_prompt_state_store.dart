import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Simple persistence for the one-time feedback dialog viewed flag
class FeedbackPromptStateStore {
  FeedbackPromptStateStore({required SharedPreferences prefs}) : _prefs = prefs;

  static const String _viewedKey = 'feedback_dialog_viewed';
  final SharedPreferences _prefs;

  Future<bool> hasViewed() async {
    try {
      return _prefs.getBool(_viewedKey) ?? false;
    } catch (e) {
      AppLogger.warn('FEEDBACK_STORE read error: $e');
      return false;
    }
  }

  Future<void> markViewed() async {
    try {
      await _prefs.setBool(_viewedKey, true);
    } catch (e) {
      AppLogger.warn('FEEDBACK_STORE write error: $e');
    }
  }
}

final feedbackPromptStateStoreProvider = Provider<FeedbackPromptStateStore>((
  ref,
) {
  final prefs = ref.watch(sharedPreferencesInstanceProvider);
  return FeedbackPromptStateStore(prefs: prefs);
});
