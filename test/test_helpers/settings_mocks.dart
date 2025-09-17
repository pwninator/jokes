import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/domain/joke_viewer_mode.dart';
import 'package:shared_preferences/shared_preferences.dart';

class MockSharedPreferences extends Mock implements SharedPreferences {}

class MockJokeViewerModeNotifier extends StateNotifier<JokeViewerMode>
    implements JokeViewerModeNotifier {
  MockJokeViewerModeNotifier(JokeViewerMode mode) : super(mode);

  @override
  Future<void> setJokeViewerMode(JokeViewerMode mode) async {
    state = mode;
  }
}

class SettingsMocks {
  static Override getJokeViewerModeProviderOverride(
      {JokeViewerMode initialMode = JokeViewerMode.reveal}) {
    return jokeViewerModeProvider.overrideWith((ref) {
      return MockJokeViewerModeNotifier(initialMode);
    });
  }
}
