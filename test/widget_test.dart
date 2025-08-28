// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

void main() {
  testWidgets('Basic app theme and material app smoke test', (
    WidgetTester tester,
  ) async {
    // Build a simple MaterialApp with our theme to test basic functionality
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: lightTheme,
          home: const Scaffold(
            appBar: null,
            body: Center(child: Text('Test App')),
          ),
        ),
      ),
    );

    // Allow time for any async operations to settle
    await tester.pumpAndSettle();

    // Verify that the app renders without issues
    expect(find.text('Test App'), findsOneWidget);
  });
}
