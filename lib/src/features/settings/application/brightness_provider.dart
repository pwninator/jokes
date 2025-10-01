import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';

/// Provides the actual brightness of the application (light or dark).
/// This is used to determine the theme for analytics events.
final brightnessProvider = Provider<Brightness>((ref) {
  final themeMode = ref.watch(themeModeProvider);
  if (themeMode == ThemeMode.system) {
    return WidgetsBinding.instance.platformDispatcher.platformBrightness;
  } else {
    return themeMode == ThemeMode.light ? Brightness.light : Brightness.dark;
  }
});
