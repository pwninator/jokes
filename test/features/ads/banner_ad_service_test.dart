import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/device_orientation_provider.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/ads/banner_ad_service.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class MockAdminSettingsService extends Mock implements AdminSettingsService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockRemoteConfigValues mockRemoteConfigValues;
  late MockAdminSettingsService mockAdminSettingsService;
  late ProviderContainer container;

  setUp(() {
    mockRemoteConfigValues = MockRemoteConfigValues();
    mockAdminSettingsService = MockAdminSettingsService();
    container = ProviderContainer(
      overrides: [
        remoteConfigValuesProvider.overrideWithValue(mockRemoteConfigValues),
        adminSettingsServiceProvider.overrideWithValue(
          mockAdminSettingsService,
        ),
      ],
    );
    addTearDown(container.dispose);
  });

  group('bannerAdEligibilityProvider', () {
    test('returns not eligible when ad display mode is not banner', () {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.none);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      final eligibility = container.read(bannerAdEligibilityProvider);
      expect(eligibility.isEligible, isFalse);
      expect(eligibility.reason, BannerAdService.notBannerModeReason);
    });

    test('returns eligible when in banner mode and portrait', () {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.banner);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      final eligibility = container.read(bannerAdEligibilityProvider);
      expect(eligibility.isEligible, isTrue);
      expect(eligibility.reason, BannerAdService.eligibleReason);
    });

    test('returns not eligible when orientation is landscape', () {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.banner);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      container.read(deviceOrientationProvider.notifier).state =
          Orientation.landscape;
      final eligibility = container.read(bannerAdEligibilityProvider);
      expect(eligibility.isEligible, isFalse);
      expect(eligibility.reason, BannerAdService.notPortraitReason);
    });

    test('admin override forces banner mode', () {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.none);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(true);

      final eligibility = container.read(bannerAdEligibilityProvider);
      expect(eligibility.isEligible, isTrue);
      expect(eligibility.reason, BannerAdService.eligibleReason);
    });
  });
}
