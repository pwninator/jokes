import 'package:flutter/material.dart';
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

  setUp(() {
    mockRemoteConfigValues = MockRemoteConfigValues();
    mockAdminSettingsService = MockAdminSettingsService();
    service = BannerAdService(
      remoteConfigValues: mockRemoteConfigValues,
      adminSettingsService: mockAdminSettingsService,
    );
  });

  group('evaluateEligibility', () {
    testWidgets('returns not eligible when ad display mode is not banner', (
      tester,
    ) async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.none);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      BannerAdEligibility? eligibility;
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: Builder(
            builder: (context) {
              eligibility = service.evaluateEligibility(context);
              return const SizedBox.shrink();
            },
          ),
        ),
      );

      expect(eligibility, isNotNull);
      expect(eligibility!.isEligible, isFalse);
      expect(eligibility!.reason, BannerAdService.notBannerModeReason);
    });

    testWidgets('returns eligible when in banner mode and portrait', (
      tester,
    ) async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.banner);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      BannerAdEligibility? eligibility;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(400, 800),
              devicePixelRatio: 1.0,
            ),
            child: Builder(
              builder: (context) {
                eligibility = service.evaluateEligibility(context);
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      );

      expect(eligibility, isNotNull);
      expect(eligibility!.isEligible, isTrue);
      expect(eligibility!.reason, BannerAdService.eligibleReason);
    });

    testWidgets('returns not eligible when orientation is landscape', (
      tester,
    ) async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.banner);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(false);

      BannerAdEligibility? eligibility;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(800, 400),
              devicePixelRatio: 1.0,
            ),
            child: Builder(
              builder: (context) {
                eligibility = service.evaluateEligibility(context);
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      );

      expect(eligibility, isNotNull);
      expect(eligibility!.isEligible, isFalse);
      expect(eligibility!.reason, BannerAdService.notPortraitReason);
    });

    testWidgets('admin override forces banner mode', (tester) async {
      when(
        () => mockRemoteConfigValues.getEnum<AdDisplayMode>(
          RemoteParam.adDisplayMode,
        ),
      ).thenReturn(AdDisplayMode.none);
      when(
        () => mockAdminSettingsService.getAdminOverrideShowBannerAd(),
      ).thenReturn(true);

      BannerAdEligibility? eligibility;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(400, 800),
              devicePixelRatio: 1.0,
            ),
            child: Builder(
              builder: (context) {
                eligibility = service.evaluateEligibility(context);
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      );

      expect(eligibility, isNotNull);
      expect(eligibility!.isEligible, isTrue);
      expect(eligibility!.reason, BannerAdService.eligibleReason);
    });
  });
}
