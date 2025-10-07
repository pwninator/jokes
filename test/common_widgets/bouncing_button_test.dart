import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';

void main() {
  Future<double> _resolveElevation(WidgetTester tester, Finder finder) async {
    final ElevatedButton button = tester.widget<ElevatedButton>(finder);
    final MaterialStateProperty<double?>? property = button.style?.elevation;
    expect(property, isNotNull, reason: 'Expected button elevation to be set');
    return property!.resolve(<MaterialState>{})!;
  }

  Animation<double> _currentScale(WidgetTester tester, Finder finder) {
    final scaleTransition = tester.widget<ScaleTransition>(finder);
    return scaleTransition.scale;
  }

  testWidgets('BouncingButton squishes on press and bounces on release', (
    tester,
  ) async {
    var pressedCount = 0;
    const buttonKey = Key('bouncing_button-test-button');

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: BouncingButton(
              buttonKey: buttonKey,
              isPositive: true,
              onPressed: () => pressedCount++,
              child: const Text('Tap me'),
            ),
          ),
        ),
      ),
    );

    final Finder buttonFinder = find.byKey(buttonKey);
    final Finder scaleFinder = find.ancestor(
      of: buttonFinder,
      matching: find.byType(ScaleTransition),
    );

    final double baseElevation = await _resolveElevation(tester, buttonFinder);
    expect(_currentScale(tester, scaleFinder).value, closeTo(1.0, 0.0001));

    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(buttonFinder),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 90));

    final double squishScale = _currentScale(tester, scaleFinder).value;
    expect(squishScale, lessThan(1.0));
    final double squishElevation = await _resolveElevation(
      tester,
      buttonFinder,
    );
    expect(squishElevation, closeTo(1.0, 0.1));

    await gesture.up();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 140));

    final double overshootScale = _currentScale(tester, scaleFinder).value;
    expect(overshootScale, greaterThan(1.0));
    final double overshootElevation = await _resolveElevation(
      tester,
      buttonFinder,
    );
    expect(overshootElevation, greaterThan(baseElevation));

    await tester.pumpAndSettle();
    expect(_currentScale(tester, scaleFinder).value, closeTo(1.0, 0.0001));
    final double settledElevation = await _resolveElevation(
      tester,
      buttonFinder,
    );
    expect(settledElevation, closeTo(baseElevation, 0.05));
    expect(pressedCount, 1);
  });

  testWidgets('BouncingButton ignores press when disabled', (tester) async {
    const buttonKey = Key('bouncing_button-disabled-button');

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: BouncingButton(
              buttonKey: buttonKey,
              isPositive: true,
              onPressed: null,
              child: Text('Disabled'),
            ),
          ),
        ),
      ),
    );

    final Finder buttonFinder = find.byKey(buttonKey);
    final Finder scaleFinder = find.ancestor(
      of: buttonFinder,
      matching: find.byType(ScaleTransition),
    );

    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(buttonFinder),
    );
    await tester.pump(const Duration(milliseconds: 120));

    final Animation<double> animation = _currentScale(tester, scaleFinder);
    expect(animation, isA<AlwaysStoppedAnimation<double>>());
    expect(animation.value, 1.0);

    await gesture.up();
    await tester.pumpAndSettle();
    expect(_currentScale(tester, scaleFinder).value, closeTo(1.0, 0.0001));
  });
}
