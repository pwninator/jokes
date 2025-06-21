import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

void main() {
  group('TitledScreen Tests', () {
    testWidgets('JokeViewerScreen returns correct title', (tester) async {
      const screen = JokeViewerScreen();
      expect((screen as TitledScreen).title, equals('Jokes'));
    });

    testWidgets('UserSettingsScreen returns correct title', (tester) async {
      const screen = UserSettingsScreen();
      expect((screen as TitledScreen).title, equals('Settings'));
    });

    testWidgets('JokeAdminScreen returns correct title', (tester) async {
      const screen = JokeAdminScreen();
      expect((screen as TitledScreen).title, equals('Admin'));
    });
  });
}
