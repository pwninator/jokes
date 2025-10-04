import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/app_review_prompt_dialog.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

void main() {
  group('AppReviewPromptDialog', () {
    testWidgets('renders bunny variant with correct variant keys and image', (
      tester,
    ) async {
      bool acceptCalled = false;
      bool dismissCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.bunny,
              onAccept: () => acceptCalled = true,
              onDismiss: () => dismissCalled = true,
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Assert: variant-specific keys exist
      expect(
        find.byKey(const Key('app_review_prompt_dialog-dismiss-button-bunny')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('app_review_prompt_dialog-accept-button-bunny')),
        findsOneWidget,
      );

      // Assert: an image is present
      expect(find.byType(Image), findsOneWidget);

      // Verify buttons are not called yet
      expect(acceptCalled, false);
      expect(dismissCalled, false);
    });

    testWidgets('renders kitten variant with correct variant keys and image', (
      tester,
    ) async {
      bool acceptCalled = false;
      bool dismissCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.kitten,
              onAccept: () => acceptCalled = true,
              onDismiss: () => dismissCalled = true,
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Assert: variant-specific keys exist
      expect(
        find.byKey(const Key('app_review_prompt_dialog-dismiss-button-kitten')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('app_review_prompt_dialog-accept-button-kitten')),
        findsOneWidget,
      );

      // Assert: an image is present
      expect(find.byType(Image), findsOneWidget);

      // Verify buttons are not called yet
      expect(acceptCalled, false);
      expect(dismissCalled, false);
    });

    testWidgets('calls onDismiss when dismiss button is tapped (bunny)', (
      tester,
    ) async {
      bool acceptCalled = false;
      bool dismissCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.bunny,
              onAccept: () => acceptCalled = true,
              onDismiss: () => dismissCalled = true,
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Tap the dismiss button
      await tester.tap(
        find.byKey(const Key('app_review_prompt_dialog-dismiss-button-bunny')),
      );
      await tester.pumpAndSettle();

      expect(dismissCalled, true);
      expect(acceptCalled, false);
    });

    testWidgets('calls onAccept when accept button is tapped (bunny)', (
      tester,
    ) async {
      bool acceptCalled = false;
      bool dismissCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.bunny,
              onAccept: () => acceptCalled = true,
              onDismiss: () => dismissCalled = true,
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Tap the accept button
      await tester.tap(
        find.byKey(const Key('app_review_prompt_dialog-accept-button-bunny')),
      );
      await tester.pumpAndSettle();

      expect(acceptCalled, true);
      expect(dismissCalled, false);
    });

    testWidgets('calls onDismiss when dismiss button is tapped (kitten)', (
      tester,
    ) async {
      bool acceptCalled = false;
      bool dismissCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.kitten,
              onAccept: () => acceptCalled = true,
              onDismiss: () => dismissCalled = true,
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Tap the dismiss button
      await tester.tap(
        find.byKey(const Key('app_review_prompt_dialog-dismiss-button-kitten')),
      );
      await tester.pumpAndSettle();

      expect(dismissCalled, true);
      expect(acceptCalled, false);
    });

    testWidgets('calls onAccept when accept button is tapped (kitten)', (
      tester,
    ) async {
      bool acceptCalled = false;
      bool dismissCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.kitten,
              onAccept: () => acceptCalled = true,
              onDismiss: () => dismissCalled = true,
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Tap the accept button
      await tester.tap(
        find.byKey(const Key('app_review_prompt_dialog-accept-button-kitten')),
      );
      await tester.pumpAndSettle();

      expect(acceptCalled, true);
      expect(dismissCalled, false);
    });

    testWidgets('renders without errors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppReviewPromptDialog(
              variant: ReviewPromptVariant.bunny,
              onAccept: () {},
              onDismiss: () {},
              onFeedback: () {},
            ),
          ),
        ),
      );

      // Verify dialog renders without errors
      expect(find.byType(AppReviewPromptDialog), findsOneWidget);
    });
  });

  group('ReviewPromptConfigs', () {
    test('bunny entry in configs has correct variant and path', () {
      final config = ReviewPromptConfigs.configs[ReviewPromptVariant.bunny]!;
      expect(config.variant, ReviewPromptVariant.bunny);
      expect(
        config.imagePath,
        'assets/review_prompts/review_request_bunny_garden_600.webp',
      );
    });

    test('kitten entry in configs has correct variant and path', () {
      final config = ReviewPromptConfigs.configs[ReviewPromptVariant.kitten]!;
      expect(config.variant, ReviewPromptVariant.kitten);
      expect(
        config.imagePath,
        'assets/review_prompts/review_request_kitten2_600.webp',
      );
    });
  });
}
