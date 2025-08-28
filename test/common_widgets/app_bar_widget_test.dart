import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';

void main() {
  group('AppBarWidget', () {
    testWidgets('displays title correctly', (WidgetTester tester) async {
      const title = 'Test Title';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(appBar: const AppBarWidget(title: title)),
        ),
      );

      expect(find.text(title), findsOneWidget);
    });

    testWidgets('uses custom background color when provided', (
      WidgetTester tester,
    ) async {
      const customColor = Colors.red;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: const AppBarWidget(
              title: 'Test',
              backgroundColor: customColor,
            ),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.backgroundColor, customColor);
    });

    testWidgets('displays custom leading widget', (WidgetTester tester) async {
      const leadingIcon = Icon(Icons.menu, key: Key('custom-leading'));

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: const AppBarWidget(title: 'Test', leading: leadingIcon),
          ),
        ),
      );

      expect(find.byKey(const Key('custom-leading')), findsOneWidget);
    });

    testWidgets('displays action widgets', (WidgetTester tester) async {
      final actions = [
        const Icon(Icons.search, key: Key('search-action')),
        const Icon(Icons.more_vert, key: Key('menu-action')),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBarWidget(title: 'Test', actions: actions),
          ),
        ),
      );

      expect(find.byKey(const Key('search-action')), findsOneWidget);
      expect(find.byKey(const Key('menu-action')), findsOneWidget);
    });

    testWidgets('applies custom foreground color', (WidgetTester tester) async {
      const customColor = Colors.green;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: const AppBarWidget(
              title: 'Test',
              foregroundColor: customColor,
            ),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.foregroundColor, customColor);
    });

    testWidgets('applies custom elevation', (WidgetTester tester) async {
      const customElevation = 8.0;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: const AppBarWidget(
              title: 'Test',
              elevation: customElevation,
            ),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.elevation, customElevation);
    });

    testWidgets('applies centerTitle setting', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: const AppBarWidget(title: 'Test', centerTitle: true),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.centerTitle, true);
    });

    testWidgets('has correct preferred size', (WidgetTester tester) async {
      const appBarWidget = AppBarWidget(title: 'Test');

      expect(appBarWidget.preferredSize, const Size.fromHeight(kToolbarHeight));
    });

    testWidgets('handles automaticallyImplyLeading setting', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: const AppBarWidget(
              title: 'Test',
              automaticallyImplyLeading: false,
            ),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.automaticallyImplyLeading, false);
    });
  });
}
