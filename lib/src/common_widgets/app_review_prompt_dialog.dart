import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

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
      title: 'Your reviews help us grow!',
      message:
          "We're a small, family team that loves making you smile. A 5-star review from you would mean the world to us and help other families discover our little app!",
      dismissButtonText: 'Maybe later',
      acceptButtonText: 'Happy to help!',
    ),
    ReviewPromptVariant.kitten: ReviewPromptConfig(
      variant: ReviewPromptVariant.kitten,
      imagePath: 'assets/review_prompts/review_request_kitten_600.webp',
      title: 'Enjoying the giggles?',
      message:
          "We're a small, family team that loves making you smile. A 5-star review from you would mean the world to us and help other families discover our little app!",
      dismissButtonText: 'Maybe later',
      acceptButtonText: 'Happy to help!',
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
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.8),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),

              // Action buttons
              Row(
                children: [
                  // Dismiss button
                  Expanded(
                    child: TextButton(
                      key: Key(
                        'app_review_prompt_dialog-dismiss-button-${variant.name}',
                      ),
                      onPressed: onDismiss,
                      style: TextButton.styleFrom(
                        backgroundColor:
                            theme.colorScheme.surfaceContainerHighest,
                        foregroundColor: theme.colorScheme.onSurface,
                      ),
                      child: Text(
                        config.dismissButtonText,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.6,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Accept button
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      key: Key(
                        'app_review_prompt_dialog-accept-button-${variant.name}',
                      ),
                      onPressed: onAccept,
                      child: Text(
                        config.acceptButtonText,
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ],
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
