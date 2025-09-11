import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/core/providers/feedback_prompt_providers.dart';

void main() {
  testWidgets('shows feedback action when provider is true and opens dialog', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          shouldShowFeedbackActionProvider.overrideWith((ref) async => true),
        ],
        child: const MaterialApp(
          home: Scaffold(appBar: AppBarWidget(title: 'Test')),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('appbar-feedback-button')), findsOneWidget);

    await tester.tap(find.byKey(const Key('appbar-feedback-button')));
    await tester.pumpAndSettle();

    expect(find.byType(FeedbackDialog), findsOneWidget);
  });

  testWidgets('does not show feedback action when provider is false', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          shouldShowFeedbackActionProvider.overrideWith((ref) async => false),
        ],
        child: const MaterialApp(
          home: Scaffold(appBar: AppBarWidget(title: 'Test')),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('appbar-feedback-button')), findsNothing);
  });
}
