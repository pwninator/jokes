// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart'; // Import ProviderScope
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/app.dart'; // App widget is already imported

void main() {
  testWidgets('App smoke test - checks for Jokes screen title', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    // Wrap the App widget with a ProviderScope
    await tester.pumpWidget(
      const ProviderScope(
        child: App(),
      ),
    );

    // Verify that the initial screen (JokeViewerScreen via MainNavigationWidget)
    // shows the "Jokes" title in the AppBar.
    // It might take a frame or two for the stream provider to settle.
    await tester.pumpAndSettle(); // Allow time for async operations like providers to settle

    expect(find.widgetWithText(AppBar, 'Jokes'), findsOneWidget);
  });
}
