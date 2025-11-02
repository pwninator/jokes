import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/onboarding_tour_state_store.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late SettingsService settingsService;
  late OnboardingTourStateStore stateStore;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    settingsService = SettingsService(prefs);
    stateStore = OnboardingTourStateStore(settingsService: settingsService);
  });

  const completedKey = 'onboarding_tour_completed';

  test('hasCompleted returns false and persists flag when absent', () async {
    expect(await stateStore.hasCompleted(), isFalse);
    expect(settingsService.getBool(completedKey), isFalse);
  });

  test('markCompleted persists flag', () async {
    await stateStore.markCompleted();

    expect(await stateStore.hasCompleted(), isTrue);
  });

  test('setCompleted(false) writes false without removing key', () async {
    await stateStore.markCompleted();

    await stateStore.setCompleted(false);

    expect(await stateStore.hasCompleted(), isFalse);
    expect(settingsService.getBool(completedKey), isFalse);
  });
}
