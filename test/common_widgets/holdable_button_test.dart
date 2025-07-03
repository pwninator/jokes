import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

void main() {
  group('HoldableButton Widget Tests', () {
    Widget createTestWidget({required Widget child}) {
      return MaterialApp(
        theme: lightTheme,
        home: Scaffold(
          body: Row(
            children: [child],
          ), // HoldableButton needs Flex parent due to Expanded
        ),
      );
    }

    group('Basic Widget Properties', () {
      testWidgets('should display correct icon when enabled', (tester) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.edit), findsOneWidget);
        expect(find.byIcon(Icons.refresh), findsNothing);
      });

      testWidgets('should use custom icon when holdCompleteIcon provided', (
        tester,
      ) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          holdCompleteIcon: Icons.star,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.edit), findsOneWidget);
        expect(find.byIcon(Icons.star), findsNothing);
      });

      testWidgets('should display spinner when disabled', (tester) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
          isEnabled: false,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.byIcon(Icons.edit), findsNothing);
      });
    });

    group('Color Customization', () {
      testWidgets('should use default tertiary colors when no color provided', (
        tester,
      ) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert - Widget builds without error using default colors
        expect(find.byType(HoldableButton), findsOneWidget);
      });

      testWidgets('should use custom color when provided', (tester) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
          color: Colors.red,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert - Widget builds without error using custom color
        expect(find.byType(HoldableButton), findsOneWidget);
      });
    });

    group('Tap Behavior', () {
      testWidgets('should call onTap when tapped quickly', (tester) async {
        // arrange
        bool tapCalled = false;
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () => tapCalled = true,
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.tap(find.byType(HoldableButton));
        await tester.pumpAndSettle();

        // assert
        expect(tapCalled, isTrue);
        expect(holdCompleteCalled, isFalse);
      });

      testWidgets('should not call callbacks when disabled and tapped', (
        tester,
      ) async {
        // arrange
        bool tapCalled = false;
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () => tapCalled = true,
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
          isEnabled: false,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.tap(find.byType(HoldableButton));
        await tester
            .pump(); // Use pump instead of pumpAndSettle for disabled state

        // assert
        expect(tapCalled, isFalse);
        expect(holdCompleteCalled, isFalse);
      });
    });

    group('Hold Behavior', () {
      testWidgets('should call onHoldComplete when held for full duration', (
        tester,
      ) async {
        // arrange
        bool tapCalled = false;
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          holdCompleteIcon: Icons.refresh,
          onTap: () => tapCalled = true,
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
          holdDuration: const Duration(
            milliseconds: 100,
          ), // Short duration for test
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // Start holding
        await tester.startGesture(
          tester.getCenter(find.byType(HoldableButton)),
        );

        // Wait for hold duration plus some buffer
        await tester.pump(const Duration(milliseconds: 50));
        expect(holdCompleteCalled, isFalse); // Should not be called yet

        await tester.pump(const Duration(milliseconds: 100));
        await tester.pumpAndSettle();

        // assert
        expect(holdCompleteCalled, isTrue);
        expect(tapCalled, isFalse);
      });

      testWidgets('should not call onHoldComplete when released early', (
        tester,
      ) async {
        // arrange
        bool tapCalled = false;
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () => tapCalled = true,
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
          holdDuration: const Duration(milliseconds: 200),
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // Start holding then release early
        final gesture = await tester.startGesture(
          tester.getCenter(find.byType(HoldableButton)),
        );
        await tester.pump(); // Start the animation
        await tester.pump(
          const Duration(milliseconds: 50),
        ); // Hold briefly (should not complete)
        await gesture.up(); // Release early
        await tester.pump(); // Process the release

        // assert
        expect(holdCompleteCalled, isFalse);
        expect(
          tapCalled,
          isFalse,
        ); // Should not trigger tap either when held then released
      });

      // Note: Hold completion behavior is already tested in "should call onHoldComplete when held for full duration" test above

      testWidgets('should not call onHoldComplete when disabled and held', (
        tester,
      ) async {
        // arrange
        bool tapCalled = false;
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () => tapCalled = true,
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
          isEnabled: false,
          holdDuration: const Duration(milliseconds: 100),
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // Try to hold
        await tester.startGesture(
          tester.getCenter(find.byType(HoldableButton)),
        );
        await tester.pump(const Duration(milliseconds: 150));
        await tester
            .pump(); // Use pump instead of pumpAndSettle for disabled state

        // assert
        expect(holdCompleteCalled, isFalse);
        expect(tapCalled, isFalse);
      });
    });

    group('Custom Hold Duration', () {
      testWidgets('should respect custom hold duration', (tester) async {
        // arrange
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
          holdDuration: const Duration(milliseconds: 300),
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // Start holding
        await tester.startGesture(
          tester.getCenter(find.byType(HoldableButton)),
        );

        // Should not complete before duration
        await tester.pump(const Duration(milliseconds: 200));
        expect(holdCompleteCalled, isFalse);

        // Should complete after duration
        await tester.pump(const Duration(milliseconds: 150));
        await tester.pumpAndSettle();

        // assert
        expect(holdCompleteCalled, isTrue);
      });
    });

    group('Animation Reset', () {
      testWidgets('should reset animation when gesture is cancelled', (
        tester,
      ) async {
        // arrange
        bool tapCalled = false;
        bool holdCompleteCalled = false;

        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () => tapCalled = true,
          onHoldComplete: () => holdCompleteCalled = true,
          theme: lightTheme,
          holdDuration: const Duration(milliseconds: 200),
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // Start gesture then cancel
        final gesture = await tester.startGesture(
          tester.getCenter(find.byType(HoldableButton)),
        );
        await tester.pump(const Duration(milliseconds: 50));
        await gesture.cancel(); // Cancel gesture
        await tester.pumpAndSettle();

        // Start new quick tap
        await tester.tap(find.byType(HoldableButton));
        await tester.pumpAndSettle();

        // assert
        expect(holdCompleteCalled, isFalse);
        expect(tapCalled, isTrue); // Should work normally after cancel
      });
    });

    group('Widget Properties', () {
      testWidgets('should contain Expanded widget', (tester) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(Expanded), findsOneWidget);
        expect(find.byType(HoldableButton), findsOneWidget);
      });

      testWidgets('should have correct height', (tester) async {
        // arrange
        final widget = HoldableButton(
          icon: Icons.edit,
          onTap: () {},
          onHoldComplete: () {},
          theme: lightTheme,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        final sizedBoxes = tester.widgetList<SizedBox>(
          find.descendant(
            of: find.byType(HoldableButton),
            matching: find.byType(SizedBox),
          ),
        );
        // Find the SizedBox with height 40 (there might be others for spinner)
        final mainSizedBox = sizedBoxes.firstWhere((box) => box.height == 40.0);
        expect(mainSizedBox.height, equals(40.0));
      });
    });
  });
}
