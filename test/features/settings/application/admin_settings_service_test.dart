import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

void main() {
  group('AdminSettingsService', () {
    late AdminSettingsService adminSettingsService;
    late SettingsService settingsService;

    setUp(() async {
      // Set up SharedPreferences for testing
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      settingsService = SettingsService(prefs);
      adminSettingsService = AdminSettingsService(settingsService);
    });

    group('admin override banner ads', () {
      test('getAdminOverrideShowBannerAd returns false by default', () {
        final value = adminSettingsService.getAdminOverrideShowBannerAd();
        expect(value, isFalse);
      });

      test(
        'setAdminOverrideShowBannerAd and getAdminOverrideShowBannerAd',
        () async {
          // Test setting to true
          await adminSettingsService.setAdminOverrideShowBannerAd(true);
          expect(adminSettingsService.getAdminOverrideShowBannerAd(), isTrue);

          // Test setting to false
          await adminSettingsService.setAdminOverrideShowBannerAd(false);
          expect(adminSettingsService.getAdminOverrideShowBannerAd(), isFalse);
        },
      );

      test('admin override persists across service instances', () async {
        // Set value with first service instance
        await adminSettingsService.setAdminOverrideShowBannerAd(true);
        expect(adminSettingsService.getAdminOverrideShowBannerAd(), isTrue);

        // Create new service instance with same SharedPreferences
        final prefs = await SharedPreferences.getInstance();
        final newSettingsService = SettingsService(prefs);
        final newAdminSettingsService = AdminSettingsService(
          newSettingsService,
        );

        // Value should persist
        expect(newAdminSettingsService.getAdminOverrideShowBannerAd(), isTrue);
      });
    });
  });
}
