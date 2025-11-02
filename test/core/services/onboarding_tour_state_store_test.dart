import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/onboarding_tour_state_store.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class _FakeRemoteConfigValues implements RemoteConfigValues {
  _FakeRemoteConfigValues({required this.showTour});

  bool showTour;

  @override
  bool getBool(RemoteParam param) {
    if (param == RemoteParam.onboardingShowTour) {
      return showTour;
    }
    return false;
  }

  @override
  double getDouble(RemoteParam param) => 0;

  @override
  int getInt(RemoteParam param) => 0;

  @override
  String getString(RemoteParam param) => '';

  @override
  T getEnum<T>(RemoteParam param) => throw UnimplementedError();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late SettingsService settingsService;
  late OnboardingTourStateStore stateStore;
  late _FakeRemoteConfigValues remoteValues;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    settingsService = SettingsService(prefs);
    remoteValues = _FakeRemoteConfigValues(showTour: true);
    stateStore = OnboardingTourStateStore(
      settingsService: settingsService,
      remoteConfigValues: remoteValues,
    );
  });

  const completedKey = 'onboarding_tour_completed';

  test('hasCompleted returns false and persists flag when absent', () async {
    expect(await stateStore.hasCompleted(), isFalse);
    expect(settingsService.getBool(completedKey), isFalse);
  });

  test('hasCompleted returns true when remote config disables tour', () async {
    remoteValues.showTour = false;

    expect(await stateStore.hasCompleted(), isTrue);
    expect(settingsService.getBool(completedKey), isTrue);
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
