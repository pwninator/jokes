import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/startup/error_screen.dart';

void main() {
  testWidgets(
    'ErrorScreen mirrors loading screen aesthetic and exposes retry',
    (tester) async {
      var retryCalled = false;

      await tester.pumpWidget(
        ErrorScreen(
          onRetry: () {
            retryCalled = true;
          },
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('We hit a snag...'), findsOneWidget);
      expect(
        find.text('Something interrupted joke prep. Give it another try?'),
        findsOneWidget,
      );

      final logFinder = find.byKey(
        const Key('error_screen-error-details-text'),
      );
      expect(logFinder, findsNothing);

      final imageWidget = tester.widget<Image>(find.byType(Image));
      expect(imageWidget.image, isA<AssetImage>());
      expect(
        (imageWidget.image as AssetImage).assetName,
        'assets/images/icon_cookie_01_transparent_dark_300.png',
      );

      final retryButton = find.byKey(const Key('error_screen-retry-button'));
      expect(retryButton, findsOneWidget);

      await tester.tap(retryButton);
      await tester.pump();

      expect(retryCalled, isTrue);
    },
  );
}
