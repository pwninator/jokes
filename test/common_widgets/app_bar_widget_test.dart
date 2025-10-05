import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/core/providers/feedback_prompt_providers.dart';

void main() {
  group('AppBarWidget', () {
    testWidgets('renders correctly with all properties',
        (WidgetTester tester) async {
      const title = 'Test Title';
      const customColor = Colors.red;
      const leadingIcon = Icon(Icons.menu, key: Key('custom-leading'));
      final actions = [
        const Icon(Icons.search, key: Key('search-action')),
        const Icon(Icons.more_vert, key: Key('menu-action')),
      ];
      const foregroundColor = Colors.green;
      const elevation = 8.0;
      const centerTitle = true;
      const automaticallyImplyLeading = false;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            shouldShowFeedbackActionProvider.overrideWith((ref) async => false),
          ],
          child: MaterialApp(
            home: Scaffold(
              appBar: AppBarWidget(
                title: title,
                backgroundColor: customColor,
                leading: leadingIcon,
                actions: actions,
                foregroundColor: foregroundColor,
                elevation: elevation,
                centerTitle: centerTitle,
                automaticallyImplyLeading: automaticallyImplyLeading,
              ),
            ),
          ),
        ),
      );

      // Verify title
      expect(find.text(title), findsOneWidget);

      // Verify custom leading widget
      expect(find.byKey(const Key('custom-leading')), findsOneWidget);

      // Verify action widgets
      expect(find.byKey(const Key('search-action')), findsOneWidget);
      expect(find.byKey(const Key('menu-action')), findsOneWidget);

      // Verify properties on the AppBar widget itself
      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.backgroundColor, customColor);
      expect(appBar.foregroundColor, foregroundColor);
      expect(appBar.elevation, elevation);
      expect(appBar.centerTitle, centerTitle);
      expect(appBar.automaticallyImplyLeading, automaticallyImplyLeading);
    });

    testWidgets('has correct preferred size', (WidgetTester tester) async {
      const appBarWidget = AppBarWidget(title: 'Test');
      expect(appBarWidget.preferredSize, const Size.fromHeight(kToolbarHeight));
    });

    testWidgets('displays feedback icon when shouldShowFeedbackAction is true',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            shouldShowFeedbackActionProvider.overrideWith((ref) async => true),
          ],
          child: MaterialApp(
            home: Scaffold(
              appBar: const AppBarWidget(title: 'Test'),
            ),
          ),
        ),
      );

      await tester.pump(); // Let the future resolve
      expect(find.byKey(const Key('feedback-notification-icon')),
          findsOneWidget);
    });
  });
}