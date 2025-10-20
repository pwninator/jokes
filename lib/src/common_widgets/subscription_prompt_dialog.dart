import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

const String cookieIconAssetPath = 'assets/icon/icon_cookie_01_preshrunk.webp';

class SubscriptionPromptDialog extends ConsumerStatefulWidget {
  const SubscriptionPromptDialog({super.key});

  @override
  ConsumerState<SubscriptionPromptDialog> createState() =>
      _SubscriptionPromptDialogState();
}

class _SubscriptionPromptDialogState
    extends ConsumerState<SubscriptionPromptDialog> {
  bool _isLoading = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      contentPadding: const EdgeInsets.all(24),
      content: Builder(
        builder: (dialogContext) {
          final Size screen = MediaQuery.of(dialogContext).size;
          final bool isWide = screen.width > screen.height;

          const double dialogToScreenRatio = 0.7;
          final double maxDialogWidth = screen.width * dialogToScreenRatio;
          final double maxDialogHeight = screen.height * dialogToScreenRatio;

          final double headerSizeBase = isWide
              ? (maxDialogHeight * 0.45)
              : (maxDialogWidth * 0.4);
          final double headerSize = headerSizeBase
              .clamp(96.0, isWide ? 180.0 : 140.0)
              .toDouble();

          final TextAlign textAlignment = isWide
              ? TextAlign.start
              : TextAlign.center;

          Widget buildHeaderImage() {
            return Container(
              width: headerSize,
              height: headerSize,
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer,
                shape: BoxShape.circle,
              ),
              padding: const EdgeInsets.all(4),
              child: ClipOval(
                child: Image.asset(
                  cookieIconAssetPath,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return Center(
                      child: Icon(
                        Icons.image_not_supported,
                        size: headerSize * 0.4,
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.3,
                        ),
                      ),
                    );
                  },
                ),
              ),
            );
          }

          final Widget textAndActions = Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Main title
              Text(
                'Start Every Day with a Smile!',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: theme.colorScheme.onSurface,
                ),
                textAlign: textAlignment,
              ),
              const SizedBox(height: 12),

              // Persuasive subtitle
              Text(
                "Keep the laughs coming! We can send one new, handpicked joke straight to your phone each day!",
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.8),
                ),
                textAlign: textAlignment,
              ),
              const SizedBox(height: 20),

              // Benefits list
              _buildBenefitsList(theme),
              const SizedBox(height: 24),

              // Action buttons
              Row(
                children: [
                  // Maybe Later button
                  Expanded(
                    child: BouncingButton(
                      buttonKey: const Key(
                        'subscription_prompt_dialog-maybe-later-button',
                      ),
                      isPositive: false,
                      onPressed: _isLoading ? null : () => _handleMaybeLater(),
                      child: Text(
                        'Maybe Later',
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

                  // Subscribe button
                  Expanded(
                    child: BouncingButton(
                      buttonKey: const Key(
                        'subscription_prompt_dialog-subscribe-button',
                      ),
                      isPositive: true,
                      onPressed: _isLoading ? null : () => _handleSubscribe(),
                      child: _isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text(
                              'Send Jokes!',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                    ),
                  ),
                ],
              ),
            ],
          );

          final Widget responsiveContent = isWide
              ? Row(
                  mainAxisSize: MainAxisSize.max,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: headerSize,
                      child: Align(
                        alignment: Alignment.topCenter,
                        child: buildHeaderImage(),
                      ),
                    ),
                    const SizedBox(width: 24),
                    Expanded(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 420),
                        child: textAndActions,
                      ),
                    ),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    buildHeaderImage(),
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
                child: SingleChildScrollView(child: responsiveContent),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildBenefitsList(ThemeData theme) {
    final benefits = [
      {'icon': '😂', 'text': 'Daily notifications with fresh jokes'},
      {'icon': '🆓', 'text': 'Completely free!'},
      {'icon': '👉', 'text': 'To get jokes, tap "Allow" on the next screen.'},
    ];

    return Column(
      children: benefits.map((benefit) {
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(benefit['icon']!, style: const TextStyle(fontSize: 16)),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  benefit['text']!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Future<void> _handleSubscribe() async {
    setState(() {
      _isLoading = true;
    });

    // Track analytics for subscription attempt
    final analyticsService = ref.read(analyticsServiceProvider);

    final subscriptionPromptNotifier = ref.read(
      subscriptionPromptProvider.notifier,
    );
    bool success = false;
    try {
      success = await subscriptionPromptNotifier.subscribeUser();
    } catch (e) {
      analyticsService.logErrorSubscriptionPermission(
        source: 'prompt',
        errorMessage: e.toString(),
      );
      success = false;
    }

    // Track analytics for subscription result
    if (success) {
      analyticsService.logSubscriptionOnPrompt();
    } else {
      analyticsService.logSubscriptionDeclinedPermissionsInPrompt();
    }

    if (success && mounted) {
      // Close dialog
      Navigator.of(context).pop();

      // Show success message
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Successfully subscribed to daily jokes! \u{1F389}',
                ),
              ),
            ],
          ),
          backgroundColor: Theme.of(context).colorScheme.primary,
          duration: const Duration(seconds: 3),
        ),
      );
    } else if (mounted) {
      // Close dialog
      Navigator.of(context).pop();

      // Show error message
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.error, color: Colors.white),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Notification permission is required for daily jokes. If you change your mind, you can subscribe anytime in Settings! 😊',
                ),
              ),
            ],
          ),
          backgroundColor: Theme.of(context).colorScheme.primary,
          duration: const Duration(seconds: 8),
        ),
      );
    }

    if (mounted) {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _handleMaybeLater() async {
    // Track analytics for maybe later choice
    final analyticsService = ref.read(analyticsServiceProvider);
    analyticsService.logSubscriptionDeclinedMaybeLater();

    final subscriptionPromptNotifier = ref.read(
      subscriptionPromptProvider.notifier,
    );
    try {
      await subscriptionPromptNotifier.dismissPrompt();
    } catch (e) {
      analyticsService.logErrorSubscriptionPrompt(
        errorMessage: e.toString(),
        phase: 'dismiss_prompt',
      );
    }

    if (mounted) {
      Navigator.of(context).pop();

      // Show snackbar informing user they can subscribe later in Settings
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.settings, color: Colors.white),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'No problem! If you ever change your mind, you can subscribe anytime in Settings',
                ),
              ),
            ],
          ),
          backgroundColor: Theme.of(context).colorScheme.secondary,
          duration: const Duration(seconds: 4),
        ),
      );
    }
  }
}
