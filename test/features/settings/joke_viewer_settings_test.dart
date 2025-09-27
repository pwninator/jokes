import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import '../../test_helpers/test_helpers.dart';

class _FakeRemoteValues implements RemoteConfigValues {
  final Map<RemoteParam, Object> _map;
  _FakeRemoteValues(this._map);
  @override
  int getInt(RemoteParam param) => _map[param] as int;
  @override
  bool getBool(RemoteParam param) => _map[param] as bool;
  @override
  double getDouble(RemoteParam param) => _map[param] as double;
  @override
  String getString(RemoteParam param) => _map[param] as String;
  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

Widget _wrap(Widget child, {required RemoteConfigValues rcValues}) {
  return ProviderScope(
    overrides: [
      ...TestHelpers.getAllMockOverrides(testUser: TestHelpers.anonymousUser),
      remoteConfigValuesProvider.overrideWithValue(rcValues),
    ],
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    registerAnalyticsFallbackValues();
  });

  group('Joke Viewer setting UI', () {
    testWidgets('defaults from RC=false to show both (toggle off)', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({});

      await tester.pumpWidget(
        _wrap(
          const UserSettingsScreen(),
          rcValues: _FakeRemoteValues({
            RemoteParam.defaultJokeViewerReveal: false,
          }),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Joke Viewer'), findsOneWidget);
      expect(find.text('Always show both images'), findsOneWidget);

      // Toggle on -> reveal
      await tester.tap(find.byKey(const Key('joke-viewer-toggle')));
      await tester.pumpAndSettle();
      expect(find.text('Hide punchline image for a surprise!'), findsOneWidget);
    });

    testWidgets('defaults from RC=true to reveal (toggle on)', (tester) async {
      SharedPreferences.setMockInitialValues({});

      await tester.pumpWidget(
        _wrap(
          const UserSettingsScreen(),
          rcValues: _FakeRemoteValues({
            RemoteParam.defaultJokeViewerReveal: true,
          }),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Hide punchline image for a surprise!'), findsOneWidget);

      // Toggle off -> both
      await tester.tap(find.byKey(const Key('joke-viewer-toggle')));
      await tester.pumpAndSettle();
      expect(find.text('Always show both images'), findsOneWidget);
    });
  });
}
