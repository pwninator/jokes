// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/main_navigation_widget.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

void main() {
  testWidgets(
    'MainNavigationWidget smoke test - checks for Jokes screen title',
    (WidgetTester tester) async {
      // Build the MainNavigationWidget directly to avoid Firebase dependencies
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: lightTheme,
            home: const MainNavigationWidget(),
          ),
        ),
      );

      // Allow time for any async operations to settle
      await tester.pumpAndSettle();

      // Verify that the initial screen shows the "Jokes" title in the AppBar
      expect(find.widgetWithText(AppBar, 'Jokes'), findsOneWidget);
    },
  );
}
