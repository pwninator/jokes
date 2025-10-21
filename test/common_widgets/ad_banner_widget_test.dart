import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/common_widgets/ad_banner_widget.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class _MockAnalytics extends Mock implements AnalyticsService {}

class _FakeRemoteValues implements RemoteConfigValues {
  _FakeRemoteValues(this.mode);
  final AdDisplayMode mode;
  @override
  bool getBool(RemoteParam param) => false;
  @override
  double getDouble(RemoteParam param) => 0.0;
  @override
  int getInt(RemoteParam param) => 0;
  @override
  String getString(RemoteParam param) => '';
  @override
  T getEnum<T>(RemoteParam param) {
    if (param == RemoteParam.adDisplayMode) return mode as T;
    throw UnimplementedError();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockAnalytics analytics;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    analytics = _MockAnalytics();
    when(() => analytics.logAdBannerSkipped(reason: any(named: 'reason')))
        .thenReturn(null);
  });

  testWidgets('hidden when RC=none', (tester) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(400, 800);
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          remoteConfigValuesProvider.overrideWithValue(
            _FakeRemoteValues(AdDisplayMode.none),
          ),
          analyticsServiceProvider.overrideWithValue(analytics),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: _FakeRemoteValues(AdDisplayMode.none),
                analyticsService: analytics,
              ),
            ),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: AdBannerWidget(jokeContext: 'daily')),
        ),
      ),
    );

    await tester.pumpAndSettle();
    // Should not render an AdWidget when RC disables banner
    expect(find.byType(AdBannerWidget), findsOneWidget);
  });

  testWidgets('hidden when landscape orientation', (tester) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(800, 400); // landscape
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          remoteConfigValuesProvider.overrideWithValue(
            _FakeRemoteValues(AdDisplayMode.banner),
          ),
          analyticsServiceProvider.overrideWithValue(analytics),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: _FakeRemoteValues(AdDisplayMode.banner),
                analyticsService: analytics,
              ),
            ),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: AdBannerWidget(jokeContext: 'daily')),
        ),
      ),
    );

    await tester.pump();
    verify(() => analytics.logAdBannerSkipped(reason: 'Not portrait mode'))
        .called(greaterThanOrEqualTo(1));
  });

  testWidgets('hidden when viewer mode is bothAdaptive', (tester) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(400, 800); // portrait
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          remoteConfigValuesProvider.overrideWithValue(
            _FakeRemoteValues(AdDisplayMode.banner),
          ),
          analyticsServiceProvider.overrideWithValue(analytics),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: _FakeRemoteValues(AdDisplayMode.banner),
                analyticsService: analytics,
              ),
            )..state = false,
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: AdBannerWidget(jokeContext: 'daily')),
        ),
      ),
    );

    await tester.pump();
    verify(() => analytics.logAdBannerSkipped(reason: 'Not reveal mode'))
        .called(greaterThanOrEqualTo(1));
  });
}
