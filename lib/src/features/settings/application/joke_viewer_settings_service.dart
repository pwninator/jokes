import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';

/// Service to manage the Joke Viewer reveal setting backed by SharedPreferences
/// with a Remote Config-provided default on first run.
final jokeViewerSettingsServiceProvider = Provider<JokeViewerSettingsService>((
  ref,
) {
  final settings = ref.watch(settingsServiceProvider);
  final rc = ref.watch(remoteConfigValuesProvider);
  final analytics = ref.watch(analyticsServiceProvider);
  return JokeViewerSettingsService(
    settingsService: settings,
    remoteConfigValues: rc,
    analyticsService: analytics,
  );
});

class JokeViewerSettingsService {
  JokeViewerSettingsService({
    required SettingsService settingsService,
    required RemoteConfigValues remoteConfigValues,
    required AnalyticsService analyticsService,
  }) : _settings = settingsService,
       _rc = remoteConfigValues,
       _analytics = analyticsService;

  final SettingsService _settings;
  final RemoteConfigValues _rc;
  final AnalyticsService _analytics;

  static const String _prefKeyReveal = 'joke_viewer_reveal';

  /// Returns whether the user prefers REVEAL mode.
  /// If the preference is missing, uses Remote Config default and persists it.
  Future<bool> getReveal() async {
    final stored = await _settings.getBool(_prefKeyReveal);
    if (stored != null) return stored;
    final defaultReveal = _rc.getBool(RemoteParam.defaultJokeViewerReveal);
    await _settings.setBool(_prefKeyReveal, defaultReveal);
    return defaultReveal;
  }

  Future<void> setReveal(bool reveal) async {
    await _settings.setBool(_prefKeyReveal, reveal);
    // Analytics: log event with chosen mode
    try {
      _analytics.logJokeViewerSettingChanged(mode: reveal ? 'reveal' : 'both');
    } catch (_) {}
  }
}

/// State notifier that exposes the reveal setting reactively
final jokeViewerRevealProvider =
    StateNotifierProvider<JokeViewerRevealNotifier, bool>((ref) {
      return JokeViewerRevealNotifier(
        ref.read(jokeViewerSettingsServiceProvider),
      );
    });

class JokeViewerRevealNotifier extends StateNotifier<bool> {
  JokeViewerRevealNotifier(this._service) : super(false) {
    _load();
  }

  final JokeViewerSettingsService _service;

  Future<void> _load() async {
    final reveal = await _service.getReveal();
    state = reveal;
  }

  Future<void> setReveal(bool value) async {
    state = value;
    await _service.setReveal(value);
  }
}
