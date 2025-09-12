import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

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
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Fun emoji header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: theme.colorScheme.primaryContainer,
              shape: BoxShape.circle,
            ),
            child: const Text('😄', style: TextStyle(fontSize: 32)),
          ),
          const SizedBox(height: 20),

          // Main title
          Text(
            'Start Every Day with a Smile!',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: theme.colorScheme.onSurface,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),

          // Persuasive subtitle
          Text(
            "Keep the laughs coming! We can send one new, handpicked joke straight to your phone each day!",
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.8),
            ),
            textAlign: TextAlign.center,
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
                child: TextButton(
                  onPressed: _isLoading ? null : () => _handleMaybeLater(),
                  style: TextButton.styleFrom(
                    backgroundColor: theme.colorScheme.surfaceContainerHighest,
                    foregroundColor: theme.colorScheme.onSurface,
                  ),
                  child: Text(
                    'Maybe Later',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),

              // Subscribe button
              Expanded(
                flex: 2,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : () => _handleSubscribe(),
                  child: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text(
                          'Yes, Send Jokes!',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                ),
              ),
            ],
          ),
        ],
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
      analyticsService
          .logErrorSubscriptionPermission(
            source: 'prompt',
            errorMessage: e.toString(),
          )
          .catchError((_) {});
      success = false;
    }

    // Track analytics for subscription result
    if (success) {
      analyticsService.logSubscriptionOnPrompt().catchError((_) {});
    } else {
      analyticsService.logSubscriptionDeclinedPermissionsInPrompt().catchError(
        (_) {},
      );
    }

    if (success && mounted) {
      // Close dialog
      Navigator.of(context).pop();

      // Show success message
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              SizedBox(width: 8),
              Text('Successfully subscribed to daily jokes! 🎉'),
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
    analyticsService.logSubscriptionDeclinedMaybeLater().catchError((_) {});

    final subscriptionPromptNotifier = ref.read(
      subscriptionPromptProvider.notifier,
    );
    try {
      await subscriptionPromptNotifier.dismissPrompt();
    } catch (e) {
      analyticsService
          .logErrorSubscriptionPrompt(
            errorMessage: e.toString(),
            phase: 'dismiss_prompt',
          )
          .catchError((_) {});
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
