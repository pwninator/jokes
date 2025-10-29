import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

part 'admin_settings_service.g.dart';

@Riverpod(keepAlive: true)
AdminSettingsService adminSettingsService(Ref ref) {
  return AdminSettingsService(ref.watch(settingsServiceProvider));
}

class AdminSettingsService {
  AdminSettingsService(this._settingsService);

  final SettingsService _settingsService;
  static const String _adminOverrideShowBannerAdKey =
      'admin_override_show_banner_ad';
  static const String _adminShowJokeDataSourceKey =
      'admin_show_joke_data_source';

  bool getAdminOverrideShowBannerAd() {
    return _settingsService.getBool(_adminOverrideShowBannerAdKey) ?? false;
  }

  Future<void> setAdminOverrideShowBannerAd(bool value) async {
    await _settingsService.setBool(_adminOverrideShowBannerAdKey, value);
  }

  bool getAdminShowJokeDataSource() {
    return _settingsService.getBool(_adminShowJokeDataSourceKey) ?? false;
  }

  Future<void> setAdminShowJokeDataSource(bool value) async {
    await _settingsService.setBool(_adminShowJokeDataSourceKey, value);
  }
}
