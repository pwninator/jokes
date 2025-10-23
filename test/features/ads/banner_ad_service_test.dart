import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/ads/banner_ad_service.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class MockAdminSettingsService extends Mock implements AdminSettingsService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockRemoteConfigValues mockRemoteConfigValues;
  late MockAdminSettingsService mockAdminSettingsService;
  late BannerAdService service;
  late Orientation orientation;

  setUp(() {
    mockRemoteConfigValues = MockRemoteConfigValues();
    mockAdminSettingsService = MockAdminSettingsService();
    orientation = Orientation.portrait;
    service = BannerAdService(
      remoteConfigValues: mockRemoteConfigValues,
      adminSettingsService: mockAdminSettingsService,
      orientationResolver: () => orientation,
    );
  });

  group('evaluateEligibility', () {
    test('returns not eligible when ad display mode is not banner', () async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.none);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      final eligibility = service.evaluateEligibility();
      expect(eligibility, isNotNull);
      expect(eligibility.isEligible, isFalse);
      expect(eligibility.reason, BannerAdService.notBannerModeReason);
    });

    test('returns eligible when in banner mode and portrait', () async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.banner);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      orientation = Orientation.portrait;
      final eligibility = service.evaluateEligibility();
      expect(eligibility, isNotNull);
      expect(eligibility.isEligible, isTrue);
      expect(eligibility.reason, BannerAdService.eligibleReason);
    });

    test('returns not eligible when orientation is landscape', () async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.banner);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      orientation = Orientation.landscape;
      final eligibility = service.evaluateEligibility();
      expect(eligibility, isNotNull);
      expect(eligibility.isEligible, isFalse);
      expect(eligibility.reason, BannerAdService.notPortraitReason);
    });

    test('admin override forces banner mode', () async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.none);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(true);

      orientation = Orientation.portrait;
      final eligibility = service.evaluateEligibility();
      expect(eligibility, isNotNull);
      expect(eligibility.isEligible, isTrue);
      expect(eligibility.reason, BannerAdService.eligibleReason);
    });
  });
}
