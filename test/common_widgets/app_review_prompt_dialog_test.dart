import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/app_review_prompt_dialog.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

class _FailingAssetBundle extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) => Future.error('missing asset: $key');
}

Future<void> _pumpDialog(
  WidgetTester tester, {
  required ReviewPromptVariant variant,
  VoidCallback? onAccept,
  VoidCallback? onDismiss,
  VoidCallback? onFeedback,
  AssetBundle? assetBundle,
}) async {
  await tester.pumpWidget(
    DefaultAssetBundle(
      bundle: assetBundle ?? rootBundle,
      child: MaterialApp(
        home: Scaffold(
          body: AppReviewPromptDialog(
            variant: variant,
            onAccept: onAccept ?? () {},
            onDismiss: onDismiss ?? () {},
            onFeedback: onFeedback,
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  group('AppReviewPromptDialog', () {
    for (final variant in ReviewPromptVariant.values) {
      testWidgets('displays ${variant.name} copy and actions', (tester) async {
        await _pumpDialog(tester, variant: variant);
        final config = ReviewPromptConfigs.getConfig(variant);

        expect(find.text(config.title), findsOneWidget);
        expect(find.text(config.message), findsOneWidget);
        expect(
          find.byKey(Key('app_review_prompt_dialog-dismiss-button-${variant.name}')),
          findsOneWidget,
        );
        expect(
          find.byKey(Key('app_review_prompt_dialog-accept-button-${variant.name}')),
          findsOneWidget,
        );
      });
    }

    testWidgets('tapping accept and dismiss triggers callbacks', (tester) async {
      var accepted = 0;
      var dismissed = 0;

      await _pumpDialog(
        tester,
        variant: ReviewPromptVariant.bunny,
        onAccept: () => accepted++,
        onDismiss: () => dismissed++,
      );

      await tester.tap(
        find.byKey(const Key('app_review_prompt_dialog-accept-button-bunny')),
      );
      await tester.pump();
      await tester.tap(
        find.byKey(const Key('app_review_prompt_dialog-dismiss-button-bunny')),
      );
      await tester.pump();

      expect(accepted, 1);
      expect(dismissed, 1);
    });

    testWidgets('feedback link invokes callback', (tester) async {
      var feedbackTapped = false;

      await _pumpDialog(
        tester,
        variant: ReviewPromptVariant.kitten,
        onFeedback: () => feedbackTapped = true,
      );

      final richText = tester.widget<RichText>(
        find.byKey(const Key('app_review_prompt_dialog-feedback-link-kitten')),
      );
      final span = richText.text as TextSpan;
      final linkSpan = span.children!.whereType<TextSpan>().last;
      (linkSpan.recognizer as TapGestureRecognizer).onTap?.call();

      expect(feedbackTapped, isTrue);
    });

    testWidgets('shows placeholder icon when image fails to load', (tester) async {
      await _pumpDialog(
        tester,
        variant: ReviewPromptVariant.bunny,
        assetBundle: _FailingAssetBundle(),
      );

      expect(find.byIcon(Icons.image_not_supported), findsOneWidget);
    });

    testWidgets('uses horizontal layout for wide screens', (tester) async {
      tester.view.physicalSize = const Size(900, 400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await _pumpDialog(tester, variant: ReviewPromptVariant.kitten);

      expect(find.byType(Row), findsWidgets);
    });

    testWidgets('uses vertical layout for tall screens', (tester) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await _pumpDialog(tester, variant: ReviewPromptVariant.bunny);

      expect(find.byType(Column), findsWidgets);
    });
  });

  group('ReviewPromptConfigs', () {
    test('bunny entry exposes expected asset', () {
      final config = ReviewPromptConfigs.getConfig(ReviewPromptVariant.bunny);
      expect(config.variant, ReviewPromptVariant.bunny);
      expect(
        config.imagePath,
        'assets/review_prompts/review_request_bunny_garden_600.webp',
      );
    });

    test('kitten entry exposes expected asset', () {
      final config = ReviewPromptConfigs.getConfig(ReviewPromptVariant.kitten);
      expect(config.variant, ReviewPromptVariant.kitten);
      expect(
        config.imagePath,
        'assets/review_prompts/review_request_kitten2_600.webp',
      );
    });
  });
}
