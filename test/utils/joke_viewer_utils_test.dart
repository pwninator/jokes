import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_context.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/utils/joke_viewer_utils.dart';

class _FakeJokeViewerSettingsService implements JokeViewerSettingsService {
  @override
  Future<bool> getReveal() async => true;

  @override
  Future<void> setReveal(bool value) async {}
}

void main() {
  testWidgets('getJokeViewerContext reflects portrait and reveal mode', (
    tester,
  ) async {
    JokeViewerContext? captured;

    // Force portrait orientation for the test environment
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(400, 800);
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          jokeViewerSettingsServiceProvider.overrideWithValue(
            _FakeJokeViewerSettingsService(),
          ),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: Consumer(
              builder: (context, ref, _) {
                captured = getJokeViewerContext(context, ref);
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      ),
    );
    // Allow async notifier to load value from fake service
    await tester.pump();
    await tester.pump();

    expect(captured, isNotNull);
    expect(captured!.isPortrait, true);
    expect(captured!.isRevealMode, true);
    expect(captured!.jokeViewerMode.toString().contains('reveal'), true);
  });

  testWidgets('getJokeViewerContext reflects landscape orientation', (
    tester,
  ) async {
    JokeViewerContext? captured;

    // Force landscape orientation for the test environment
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(800, 400);
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          jokeViewerSettingsServiceProvider.overrideWithValue(
            _FakeJokeViewerSettingsService(),
          ),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: Consumer(
              builder: (context, ref, _) {
                captured = getJokeViewerContext(context, ref);
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      ),
    );

    // Allow async notifier to load value from fake service
    await tester.pump();
    await tester.pump();

    expect(captured, isNotNull);
    expect(captured!.isPortrait, false);
    expect(captured!.screenOrientation, 'landscape');
  });
}
