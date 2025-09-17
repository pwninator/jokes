import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/settings/domain/joke_viewer_mode.dart';

class JokeViewerModeNotifier extends StateNotifier<JokeViewerMode> {
  JokeViewerModeNotifier({
    required SharedPreferences prefs,
    required AnalyticsService analytics,
  })  : _prefs = prefs,
        _analytics = analytics,
        super(JokeViewerMode.reveal) {
    _init();
  }

  final SharedPreferences _prefs;
  final AnalyticsService _analytics;

  static const String _jokeViewerModeKey = 'joke_viewer_hide_punchline_key';

  void _init() {
    final bool hidePunchline = _prefs.getBool(_jokeViewerModeKey) ?? true; // Default to hide
    state = hidePunchline ? JokeViewerMode.reveal : JokeViewerMode.auto;
  }

  Future<void> setJokeViewerMode(JokeViewerMode mode) async {
    final bool hidePunchline = mode == JokeViewerMode.reveal;
    await _prefs.setBool(_jokeViewerModeKey, hidePunchline);
    state = mode;
    _analytics.logJokeViewerModeChanged(
      mode: mode.name,
      source: 'user_settings_screen',
    );
  }
}

final jokeViewerModeProvider =
    StateNotifierProvider<JokeViewerModeNotifier, JokeViewerMode>((ref) {
  final prefs = ref.watch(sharedPreferencesInstanceProvider);
  final analytics = ref.watch(analyticsServiceProvider);
  return JokeViewerModeNotifier(prefs: prefs, analytics: analytics);
});
