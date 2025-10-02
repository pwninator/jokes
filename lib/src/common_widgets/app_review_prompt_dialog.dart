import 'dart:math' as math;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';

/// Configuration for a review prompt variant
class ReviewPromptConfig {
  final ReviewPromptVariant variant;
  final String imagePath;
  final String title;
  final String message;
  final String dismissButtonText;
  final String acceptButtonText;

  const ReviewPromptConfig({
    required this.variant,
    required this.imagePath,
    required this.title,
    required this.message,
    required this.dismissButtonText,
    required this.acceptButtonText,
  });
}

/// Maps review prompt variants to their configurations
class ReviewPromptConfigs {
  static const Map<ReviewPromptVariant, ReviewPromptConfig> configs = {
    ReviewPromptVariant.bunny: ReviewPromptConfig(
      variant: ReviewPromptVariant.bunny,
      imagePath: 'assets/review_prompts/review_request_bunny_garden_600.webp',
      title: 'Help spread the smiles!',
      message:
          "We're a small family team that loves making you smile. Your review helps more families find us!",
      dismissButtonText: "No thanks",
      acceptButtonText: 'Leave a review',
    ),
    ReviewPromptVariant.kitten: ReviewPromptConfig(
      variant: ReviewPromptVariant.kitten,
      imagePath: 'assets/review_prompts/review_request_kitten2_600.webp',
      title: 'Help spread the smiles!',
      message:
          "Made by a small family team for families like yours. If the jokes helped brighten your day, a review helps others find us!",
      dismissButtonText: "No thanks",
      acceptButtonText: 'Leave a review',
    ),
  };

  static ReviewPromptConfig getConfig(ReviewPromptVariant variant) {
    return configs[variant] ?? configs[ReviewPromptVariant.bunny]!;
  }
}

/// Dialog shown before native app review request
///
/// Shows a cute image with a personal message asking for a review
class AppReviewPromptDialog extends StatelessWidget {
  final ReviewPromptVariant variant;
  final VoidCallback onAccept;
  final VoidCallback onDismiss;

  const AppReviewPromptDialog({
    super.key,
    required this.variant,
    required this.onAccept,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final config = ReviewPromptConfigs.getConfig(variant);

    return AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      contentPadding: const EdgeInsets.all(24),
      content: Builder(
        builder: (context) {
          final Size screen = MediaQuery.of(context).size;
          final bool isWide = screen.width > screen.height;

          final double dialogToScreenRatio = 0.7;
          final double imageToDialogShortRatio = 0.9;
          final double imageToDialogLongRatio = 0.4;

          // Constrain dialog to fit within the screen without scrolling
          final double maxDialogWidth = screen.width * dialogToScreenRatio;
          final double maxDialogHeight = screen.height * dialogToScreenRatio;

          // Dynamically size the image within the dialog constraints
          final double dialogLongSide = isWide
              ? maxDialogWidth
              : maxDialogHeight;
          final double dialogShortSide = isWide
              ? maxDialogHeight
              : maxDialogWidth;
          double imageSize = math.min(
            dialogLongSide * imageToDialogLongRatio,
            dialogShortSide * imageToDialogShortRatio,
          );
          imageSize = math.min(imageSize, 600.0);

          Widget imageWidget = SizedBox(
            width: imageSize,
            height: imageSize,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.asset(
                config.imagePath,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return Container(
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.image_not_supported,
                      size: 48,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                    ),
                  );
                },
              ),
            ),
          );

          Widget textAndActions = Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Title
              Text(
                config.title,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: theme.colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),

              // Message
              Text(
                config.message,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.9),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),

              // Action buttons
              Row(
                children: [
                  // Dismiss button
                  Expanded(
                    child: OutlinedButton(
                      key: Key(
                        'app_review_prompt_dialog-dismiss-button-${variant.name}',
                      ),
                      onPressed: onDismiss,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: theme.colorScheme.onSurface.withValues(
                          alpha: 0.8,
                        ),
                        side: BorderSide(
                          color: theme.colorScheme.outline,
                          width: 1,
                        ),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: Text(
                        config.dismissButtonText,
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Accept button
                  Expanded(
                    // flex: 2,
                    child: ElevatedButton(
                      key: Key(
                        'app_review_prompt_dialog-accept-button-${variant.name}',
                      ),
                      onPressed: onAccept,
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: Text(
                        config.acceptButtonText,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Feedback link
              RichText(
                key: Key(
                  'app_review_prompt_dialog-feedback-link-${variant.name}',
                ),
                textAlign: TextAlign.center,
                text: TextSpan(
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                  children: [
                    const TextSpan(text: 'Having issues? '),
                    TextSpan(
                      text: 'Send us feedback',
                      style: TextStyle(
                        color: theme.colorScheme.secondary,
                        fontWeight: FontWeight.bold,
                        decoration: TextDecoration.underline,
                        decorationColor: theme.colorScheme.secondary,
                      ),
                      recognizer: TapGestureRecognizer()
                        ..onTap = () async {
                          // Close this dialog
                          Navigator.of(context).pop();

                          // Open feedback screen
                          final router = GoRouter.maybeOf(context);
                          if (router != null) {
                            await router.pushNamed<bool>(RouteNames.feedback);
                          } else {
                            await Navigator.of(context).push<bool>(
                              MaterialPageRoute(
                                builder: (_) => const UserFeedbackScreen(),
                              ),
                            );
                          }
                        },
                    ),
                  ],
                ),
              ),
            ],
          );

          final Widget content = isWide
              ? Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    imageWidget,
                    const SizedBox(width: 20),
                    Flexible(child: textAndActions),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    imageWidget,
                    const SizedBox(height: 20),
                    textAndActions,
                  ],
                );

          return SizedBox(
            width: maxDialogWidth,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxHeight: maxDialogHeight),
              child: SafeArea(
                minimum: const EdgeInsets.all(12),
                child: SingleChildScrollView(child: content),
              ),
            ),
          );
        },
      ),
    );
  }
}
