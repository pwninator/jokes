import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

final themeSettingsServiceProvider = Provider<ThemeSettingsService>((ref) {
  return ThemeSettingsService(ref.watch(settingsServiceProvider));
});

final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>((
  ref,
) {
  return ThemeModeNotifier(ref.watch(themeSettingsServiceProvider));
});

class ThemeSettingsService {
  ThemeSettingsService(this._settingsService);

  final SettingsService _settingsService;
  static const String _themeModeKey = 'theme_mode';

  Future<ThemeMode> getThemeMode() async {
    final themeModeString = _settingsService.getString(_themeModeKey);
    return _parseThemeMode(themeModeString);
  }

  Future<void> setThemeMode(ThemeMode themeMode) async {
    await _settingsService.setString(_themeModeKey, themeMode.name);
  }

  ThemeMode _parseThemeMode(String? themeModeString) {
    switch (themeModeString) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      case 'system':
      default:
        return ThemeMode.system;
    }
  }
}

class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier(this._themeSettingsService) : super(ThemeMode.system) {
    _loadThemeMode();
  }

  final ThemeSettingsService _themeSettingsService;

  Future<void> _loadThemeMode() async {
    final themeMode = await _themeSettingsService.getThemeMode();
    state = themeMode;
  }

  Future<void> setThemeMode(ThemeMode themeMode) async {
    state = themeMode;
    await _themeSettingsService.setThemeMode(themeMode);
  }
}
