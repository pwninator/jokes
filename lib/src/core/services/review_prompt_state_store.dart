import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Simple persistence for the one-time review prompt attempt flag
class ReviewPromptStateStore {
  ReviewPromptStateStore({required SharedPreferences prefs}) : _prefs = prefs;

  static const String _requestedKey = 'review_prompt_requested';
  final SharedPreferences _prefs;

  Future<bool> hasRequested() async {
    try {
      return _prefs.getBool(_requestedKey) ?? false;
    } catch (e) {
      AppLogger.warn('REVIEW_STORE read error: $e');
      return false;
    }
  }

  Future<void> markRequested() async {
    try {
      await _prefs.setBool(_requestedKey, true);
    } catch (e) {
      AppLogger.warn('REVIEW_STORE write error: $e');
    }
  }
}

final reviewPromptStateStoreProvider = Provider<ReviewPromptStateStore>((ref) {
  final prefs = ref.watch(sharedPreferencesInstanceProvider);
  return ReviewPromptStateStore(prefs: prefs);
});
