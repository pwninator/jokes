import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late SettingsService settingsService;
  late ReviewPromptStateStore stateStore;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    settingsService = SettingsService(prefs);
    stateStore = ReviewPromptStateStore(settingsService: settingsService);
  });

  test('hasRequested returns false when flag absent', () async {
    expect(stateStore.hasRequested(), isFalse);
  });

  test('markRequested persists flag', () async {
    await stateStore.markRequested();

    expect(stateStore.hasRequested(), isTrue);
  });
}
