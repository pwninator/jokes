import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: lightTheme,
      home: Scaffold(
        body: Row(children: [child]),
      ),
    );

void main() {
  group('HoldableButton', () {
    testWidgets('quick tap triggers onTap only', (tester) async {
      var tapCount = 0;
      var holdCount = 0;

      await tester.pumpWidget(
        _wrap(
          HoldableButton(
            icon: Icons.edit,
            theme: lightTheme,
            onTap: () => tapCount++,
            onHoldComplete: () => holdCount++,
          ),
        ),
      );

      await tester.tap(find.byType(HoldableButton));
      await tester.pumpAndSettle();

      expect(tapCount, 1);
      expect(holdCount, 0);
    });

    testWidgets('holding past duration triggers hold completion', (
      tester,
    ) async {
      var tapCount = 0;
      final holdCompleter = Completer<void>();

      await tester.pumpWidget(
        _wrap(
          HoldableButton(
            icon: Icons.play_arrow,
            holdCompleteIcon: Icons.check,
            theme: lightTheme,
            holdDuration: const Duration(milliseconds: 120),
            onTap: () => tapCount++,
            onHoldComplete: () => holdCompleter.complete(),
          ),
        ),
      );

      final gesture = await tester.startGesture(
        tester.getCenter(find.byType(HoldableButton)),
      );
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pumpAndSettle();

      expect(holdCompleter.isCompleted, isTrue);

      await gesture.up();
      await tester.pump();

      expect(tapCount, 1);
    });

    testWidgets('short press fires tap but not hold completion', (
      tester,
    ) async {
      var tapCount = 0;
      final holdCompleter = Completer<void>();

      await tester.pumpWidget(
        _wrap(
          HoldableButton(
            icon: Icons.timer,
            theme: lightTheme,
            holdDuration: const Duration(milliseconds: 200),
            onTap: () => tapCount++,
            onHoldComplete: () => holdCompleter.complete(),
          ),
        ),
      );

      final gesture = await tester.startGesture(
        tester.getCenter(find.byType(HoldableButton)),
      );
      await tester.pump(const Duration(milliseconds: 80));
      await gesture.up();
      await tester.pump();

      expect(tapCount, 1);
      expect(holdCompleter.isCompleted, isFalse);
    });

    testWidgets('disabled button ignores gestures', (tester) async {
      var tapCount = 0;
      var holdCount = 0;

      await tester.pumpWidget(
        _wrap(
          HoldableButton(
            icon: Icons.block,
            theme: lightTheme,
            isEnabled: false,
            onTap: () => tapCount++,
            onHoldComplete: () => holdCount++,
          ),
        ),
      );

      await tester.tap(find.byType(HoldableButton));
      await tester.pump();

      final gesture = await tester.startGesture(
        tester.getCenter(find.byType(HoldableButton)),
      );
      await tester.pump(const Duration(milliseconds: 150));
      await gesture.up();
      await tester.pump();

      expect(tapCount, 0);
      expect(holdCount, 0);
    });

    testWidgets('loading state shows spinner and blocks tap', (tester) async {
      var tapCount = 0;

      await tester.pumpWidget(
        _wrap(
          HoldableButton(
            icon: Icons.refresh,
            theme: lightTheme,
            isLoading: true,
            onTap: () => tapCount++,
            onHoldComplete: () {},
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.tap(find.byType(HoldableButton));
      await tester.pump();

      expect(tapCount, 0);
    });

    testWidgets('cancelled gesture resets state allowing subsequent tap', (
      tester,
    ) async {
      var tapCount = 0;
      var holdCount = 0;

      await tester.pumpWidget(
        _wrap(
          HoldableButton(
            icon: Icons.refresh,
            theme: lightTheme,
            holdDuration: const Duration(milliseconds: 200),
            onTap: () => tapCount++,
            onHoldComplete: () => holdCount++,
          ),
        ),
      );

      final gesture = await tester.startGesture(
        tester.getCenter(find.byType(HoldableButton)),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await gesture.cancel();
      await tester.pumpAndSettle();

      await tester.tap(find.byType(HoldableButton));
      await tester.pumpAndSettle();

      expect(holdCount, 0);
      expect(tapCount, 1);
    });
  });
}
