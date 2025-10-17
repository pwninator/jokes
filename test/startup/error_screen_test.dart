import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/startup/error_screen.dart';

void main() {
  group('ErrorScreen', () {
    testWidgets('displays correct error messages', (tester) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      await tester.pumpAndSettle();

      expect(find.text('We hit a snag...'), findsOneWidget);
      expect(
        find.text('Something interrupted joke prep. Give it another try?'),
        findsOneWidget,
      );
    });

    testWidgets('displays correct cookie icon', (tester) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      await tester.pumpAndSettle();

      final imageWidget = tester.widget<Image>(find.byType(Image));
      expect(imageWidget.image, isA<AssetImage>());
      expect(
        (imageWidget.image as AssetImage).assetName,
        JokeConstants.iconCookie01TransparentDark300,
      );
      expect(imageWidget.width, 250);
      expect(imageWidget.height, 250);
      expect(imageWidget.fit, BoxFit.cover);
    });

    testWidgets('displays retry button with correct key', (tester) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      await tester.pumpAndSettle();

      final retryButton = find.byKey(const Key('error_screen-retry-button'));
      expect(retryButton, findsOneWidget);
      expect(find.text('Retry Startup'), findsOneWidget);
    });

    testWidgets('calls onRetry when retry button is tapped', (tester) async {
      var retryCalled = false;

      await tester.pumpWidget(
        ErrorScreen(
          onRetry: () {
            retryCalled = true;
          },
        ),
      );

      await tester.pumpAndSettle();

      final retryButton = find.byKey(const Key('error_screen-retry-button'));
      await tester.tap(retryButton);
      await tester.pump();

      expect(retryCalled, isTrue);
    });

    testWidgets('applies correct theme and styling', (tester) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      await tester.pumpAndSettle();

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.themeMode, ThemeMode.dark);
      expect(materialApp.debugShowCheckedModeBanner, false);

      final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
      expect(scaffold.backgroundColor, Colors.black);
    });

    testWidgets('handles animation correctly', (tester) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      // Initially, the opacity should be 0 (begin value)
      final opacityWidget = tester.widget<Opacity>(find.byType(Opacity));
      expect(opacityWidget.opacity, 0.0);

      // After animation completes, opacity should be 1.0
      await tester.pumpAndSettle();
      final finalOpacityWidget = tester.widget<Opacity>(find.byType(Opacity));
      expect(finalOpacityWidget.opacity, 1.0);
    });

    testWidgets('positions content correctly with LayoutBuilder', (
      tester,
    ) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      await tester.pumpAndSettle();

      // Verify LayoutBuilder is present
      expect(find.byType(LayoutBuilder), findsOneWidget);

      // Verify widget structure - there may be multiple Stack widgets in the tree
      expect(find.byType(Stack), findsWidgets);
      expect(find.byType(Center), findsOneWidget);
      expect(find.byType(Positioned), findsOneWidget);
    });

    testWidgets('does not display error details text', (tester) async {
      await tester.pumpWidget(ErrorScreen(onRetry: () {}));

      await tester.pumpAndSettle();

      // Verify that error details text is not displayed
      final errorDetailsFinder = find.byKey(
        const Key('error_screen-error-details-text'),
      );
      expect(errorDetailsFinder, findsNothing);
    });
  });
}
