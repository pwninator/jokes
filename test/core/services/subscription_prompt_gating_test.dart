import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

class _FakeRemoteConfigValues extends Fake implements RemoteConfigValues {}

class _MockSyncService extends Mock implements DailyJokeSubscriptionService {}

void main() {
  setUpAll(() {
    registerFallbackValue(_FakeRemoteConfigValues());
  });

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  test('does not show prompt if jokes viewed below remote threshold', () async {
    final prefs = await SharedPreferences.getInstance();
    final sync = _MockSyncService();

    when(
      () => sync.ensureSubscriptionSync(
        unsubscribeOthers: any(named: 'unsubscribeOthers'),
      ),
    ).thenAnswer((_) async => true);
    final subscriptionNotifier = SubscriptionNotifier(prefs, sync);
    final rcValues = _TestRCValues(threshold: 7);
    final promptNotifier = SubscriptionPromptNotifier(
      subscriptionNotifier,
      remoteConfigValues: rcValues,
    );

    promptNotifier.considerPromptAfterJokeViewed(5);

    expect(promptNotifier.state.shouldShowPrompt, isFalse);
  });

  test('shows prompt when jokes viewed meets remote threshold', () async {
    final prefs = await SharedPreferences.getInstance();
    final sync = _MockSyncService();

    when(
      () => sync.ensureSubscriptionSync(
        unsubscribeOthers: any(named: 'unsubscribeOthers'),
      ),
    ).thenAnswer((_) async => true);
    final subscriptionNotifier = SubscriptionNotifier(prefs, sync);
    final rcValues = _TestRCValues(threshold: 5);
    final promptNotifier = SubscriptionPromptNotifier(
      subscriptionNotifier,
      remoteConfigValues: rcValues,
    );

    promptNotifier.considerPromptAfterJokeViewed(5);

    expect(promptNotifier.state.shouldShowPrompt, isTrue);
  });
}

class _TestRCValues implements RemoteConfigValues {
  _TestRCValues({required this.threshold});
  final int threshold;

  @override
  bool getBool(RemoteParam param) => false;

  @override
  double getDouble(RemoteParam param) => 0;

  @override
  int getInt(RemoteParam param) {
    if (param == RemoteParam.subscriptionPromptMinJokesViewed) return threshold;
    return 0;
  }

  @override
  String getString(RemoteParam param) => '';

  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}
