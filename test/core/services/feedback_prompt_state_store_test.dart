import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late SettingsService settingsService;
  late FeedbackPromptStateStore stateStore;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    settingsService = SettingsService(prefs);
    stateStore = FeedbackPromptStateStore(settingsService: settingsService);
  });

  test('hasViewed returns false when flag absent', () async {
    expect(await stateStore.hasViewed(), isFalse);
  });

  test('markViewed persists flag', () async {
    await stateStore.markViewed();

    expect(await stateStore.hasViewed(), isTrue);
  });
}
