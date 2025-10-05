import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/app_review_prompt_dialog.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

void main() {
  group('AppReviewPromptDialog', () {
    // Parameterized test for each variant that has a config
    for (final variant in ReviewPromptConfigs.configs.keys) {
      testWidgets('renders and handles interactions for ${variant.name}',
          (tester) async {
        bool acceptCalled = false;
        bool dismissCalled = false;
        bool feedbackCalled = false;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: AppReviewPromptDialog(
                variant: variant,
                onAccept: () => acceptCalled = true,
                onDismiss: () => dismissCalled = true,
                onFeedback: () => feedbackCalled = true,
              ),
            ),
          ),
        );

        // --- Renders correctly ---
        final dismissButtonFinder = find.byKey(
            Key('app_review_prompt_dialog-dismiss-button-${variant.name}'));
        final acceptButtonFinder = find.byKey(
            Key('app_review_prompt_dialog-accept-button-${variant.name}'));
        final richTextFinder = find.byKey(
            Key('app_review_prompt_dialog-feedback-link-${variant.name}'));

        expect(dismissButtonFinder, findsOneWidget);
        expect(acceptButtonFinder, findsOneWidget);
        expect(richTextFinder, findsOneWidget);
        expect(find.byType(Image), findsOneWidget);

        // --- Handles interactions ---
        expect(acceptCalled, false);
        expect(dismissCalled, false);
        expect(feedbackCalled, false);

        // Tap the dismiss button
        await tester.tap(dismissButtonFinder);
        await tester.pumpAndSettle();
        expect(dismissCalled, true);
        expect(acceptCalled, false);
        expect(feedbackCalled, false);

        // Reset and tap the accept button
        dismissCalled = false;
        await tester.tap(acceptButtonFinder);
        await tester.pumpAndSettle();
        expect(acceptCalled, true);
        expect(dismissCalled, false);
        expect(feedbackCalled, false);

        // Reset and manually trigger the feedback link's gesture recognizer
        acceptCalled = false;
        final RichText richTextWidget = tester.widget(richTextFinder);
        final TextSpan textSpan = richTextWidget.text as TextSpan;
        final feedbackTextSpan = textSpan.children!.firstWhere((span) =>
                span is TextSpan && span.text == 'Send us feedback')
            as TextSpan;

        final recognizer = feedbackTextSpan.recognizer as TapGestureRecognizer;
        recognizer.onTap!(); // Manually invoke the tap
        await tester.pumpAndSettle();

        expect(feedbackCalled, true);
        expect(acceptCalled, false);
        expect(dismissCalled, false);
      });
    }
  });

  group('ReviewPromptConfigs', () {
    // Test only for variants that have a config
    for (final variant in ReviewPromptConfigs.configs.keys) {
      test('config for ${variant.name} has correct variant and non-empty path',
          () {
        final config = ReviewPromptConfigs.configs[variant]!;
        expect(config.variant, variant);
        expect(config.imagePath, isNotEmpty);
        expect(config.imagePath.contains('/'), isTrue);
      });
    }
  });
}