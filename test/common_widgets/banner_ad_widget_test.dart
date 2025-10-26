import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/common_widgets/banner_ad_widget.dart';
import 'package:snickerdoodle/src/core/providers/device_orientation_provider.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/ads/banner_ad_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

class FakeRemoteConfigValues implements RemoteConfigValues {
  FakeRemoteConfigValues(this.mode);
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
    if (param == RemoteParam.bannerAdPosition) {
      return BannerAdPosition.top as T;
    }
    throw UnimplementedError();
  }
}

class FakeBannerAd extends Fake implements BannerAd {
  @override
  AdSize get size => const AdSize(width: 320, height: 50);

  @override
  String get adUnitId => 'test-ad-unit-id';
}

Finder _bannerSizedBoxFinder() {
  return find.byWidgetPredicate(
    (widget) =>
        widget is SizedBox &&
        widget.height == AdSize.banner.height.toDouble() &&
        widget.width == AdSize.banner.width.toDouble(),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockAnalyticsService mockAnalyticsService;
  late SharedPreferences prefs;

  setUpAll(() {
    registerFallbackValue(FakeBannerAd());
  });

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();

    mockAnalyticsService = MockAnalyticsService();
  });

  testWidgets('renders SizedBox.shrink when remote config disables ads', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(400, 800); // portrait
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    final fakeRemoteConfig = FakeRemoteConfigValues(AdDisplayMode.none);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bannerAdEligibilityProvider.overrideWithValue(
            const BannerAdEligibility(
              isEligible: false,
              reason: BannerAdService.notBannerModeReason,
              position: BannerAdPosition.top,
            ),
          ),
          remoteConfigValuesProvider.overrideWithValue(fakeRemoteConfig),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: fakeRemoteConfig,
                analyticsService: mockAnalyticsService,
              ),
            ),
          ),
        ],
        child: const MaterialApp(
          home: DeviceOrientationObserver(
            child: Scaffold(
              body: AdBannerWidget(
                jokeContext: 'daily',
                position: BannerAdPosition.top,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Should render the widget but with SizedBox.shrink content
    expect(find.byType(AdBannerWidget), findsOneWidget);
    expect(find.byType(SizedBox), findsOneWidget);
    expect(find.byType(AdWidget), findsNothing);
  });

  testWidgets('renders SizedBox.shrink when in landscape orientation', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(800, 400); // landscape
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    final fakeRemoteConfig = FakeRemoteConfigValues(AdDisplayMode.banner);
    final eligibilityStateProvider = StateProvider<BannerAdEligibility>(
      (ref) => const BannerAdEligibility(
        isEligible: true,
        reason: BannerAdService.eligibleReason,
        position: BannerAdPosition.top,
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bannerAdEligibilityProvider.overrideWith(
            (ref) => ref.watch(eligibilityStateProvider),
          ),
          remoteConfigValuesProvider.overrideWithValue(fakeRemoteConfig),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: fakeRemoteConfig,
                analyticsService: mockAnalyticsService,
              ),
            ),
          ),
        ],
        child: const MaterialApp(
          home: DeviceOrientationObserver(
            child: Scaffold(
              body: AdBannerWidget(
                jokeContext: 'daily',
                position: BannerAdPosition.top,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();
    final container = ProviderScope.containerOf(
      tester.element(find.byType(AdBannerWidget)),
      listen: false,
    );
    container
        .read(eligibilityStateProvider.notifier)
        .state = const BannerAdEligibility(
      isEligible: false,
      reason: BannerAdService.notPortraitReason,
      position: BannerAdPosition.top,
    );
    await tester.pump();
    await tester.pump();

    // Should render the widget but with SizedBox.shrink content
    expect(find.byType(AdBannerWidget), findsOneWidget);
    expect(find.byType(SizedBox), findsOneWidget);
    expect(find.byType(AdWidget), findsNothing);
  });

  testWidgets('renders SizedBox.shrink when not in reveal mode', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(400, 800); // portrait
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    final fakeRemoteConfig = FakeRemoteConfigValues(AdDisplayMode.banner);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bannerAdEligibilityProvider.overrideWithValue(
            const BannerAdEligibility(
              isEligible: false,
              reason: 'Not reveal mode',
              position: BannerAdPosition.top,
            ),
          ),
          remoteConfigValuesProvider.overrideWithValue(fakeRemoteConfig),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: fakeRemoteConfig,
                analyticsService: mockAnalyticsService,
              ),
            )..state = false, // Set to false to simulate not in reveal mode
          ),
        ],
        child: const MaterialApp(
          home: DeviceOrientationObserver(
            child: Scaffold(
              body: AdBannerWidget(
                jokeContext: 'daily',
                position: BannerAdPosition.top,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Should render the widget but with SizedBox.shrink content
    expect(find.byType(AdBannerWidget), findsOneWidget);
    expect(find.byType(SizedBox), findsOneWidget);
    expect(find.byType(AdWidget), findsNothing);
  });

  testWidgets('admin override forces banner mode regardless of remote config', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(400, 800); // portrait
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    // Set up remote config to disable ads
    final fakeRemoteConfig = FakeRemoteConfigValues(AdDisplayMode.none);

    // Set admin override to true
    await prefs.setBool('admin_override_show_banner_ad', true);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bannerAdEligibilityProvider.overrideWithValue(
            const BannerAdEligibility(
              isEligible: true,
              reason: BannerAdService.eligibleReason,
              position: BannerAdPosition.top,
            ),
          ),
          remoteConfigValuesProvider.overrideWithValue(fakeRemoteConfig),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: fakeRemoteConfig,
                analyticsService: mockAnalyticsService,
              ),
            ),
          ),
        ],
        child: const MaterialApp(
          home: DeviceOrientationObserver(
            child: Scaffold(
              body: AdBannerWidget(
                jokeContext: 'daily',
                position: BannerAdPosition.top,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Should render the widget but with SizedBox.shrink content
    // (because no actual ad is loaded in test environment)
    expect(find.byType(AdBannerWidget), findsOneWidget);
    expect(_bannerSizedBoxFinder(), findsOneWidget);
    expect(find.byType(AdWidget), findsNothing);
  });

  testWidgets('admin override respects portrait and reveal mode constraints', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(800, 400); // landscape
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    // Set up remote config to disable ads
    final fakeRemoteConfig = FakeRemoteConfigValues(AdDisplayMode.none);
    final eligibilityStateProvider = StateProvider<BannerAdEligibility>(
      (ref) => const BannerAdEligibility(
        isEligible: true,
        reason: BannerAdService.eligibleReason,
        position: BannerAdPosition.top,
      ),
    );

    // Set admin override to true
    await prefs.setBool('admin_override_show_banner_ad', true);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bannerAdEligibilityProvider.overrideWith(
            (ref) => ref.watch(eligibilityStateProvider),
          ),
          remoteConfigValuesProvider.overrideWithValue(fakeRemoteConfig),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          sharedPreferencesProvider.overrideWithValue(prefs),
          jokeViewerRevealProvider.overrideWith(
            (ref) => JokeViewerRevealNotifier(
              JokeViewerSettingsService(
                settingsService: SettingsService(prefs),
                remoteConfigValues: fakeRemoteConfig,
                analyticsService: mockAnalyticsService,
              ),
            ),
          ),
        ],
        child: const MaterialApp(
          home: DeviceOrientationObserver(
            child: Scaffold(
              body: AdBannerWidget(
                jokeContext: 'daily',
                position: BannerAdPosition.top,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();
    final container = ProviderScope.containerOf(
      tester.element(find.byType(AdBannerWidget)),
      listen: false,
    );
    container
        .read(eligibilityStateProvider.notifier)
        .state = const BannerAdEligibility(
      isEligible: false,
      reason: BannerAdService.notPortraitReason,
      position: BannerAdPosition.top,
    );
    await tester.pump();
    await tester.pump();

    // Should render the widget but with SizedBox.shrink content
    expect(find.byType(AdBannerWidget), findsOneWidget);
    expect(find.byType(SizedBox), findsOneWidget);
    expect(find.byType(AdWidget), findsNothing);
  });
}
