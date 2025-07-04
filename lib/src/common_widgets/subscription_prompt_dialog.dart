import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

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
            'Never Miss a Laugh!',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: theme.colorScheme.onSurface,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),

          // Persuasive subtitle
          Text(
            "Enjoy that one? We'll deliver one perfectly punny joke to you each day. Allow notifications to get your daily dose of humor without lifting a finger.",
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
                  child:
                      _isLoading
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
      {'icon': '📱', 'text': 'Daily notifications with fresh jokes'},
      {'icon': '🆓', 'text': 'Completely free, forever'},
    ];

    return Column(
      children:
          benefits.map((benefit) {
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
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.7,
                        ),
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

    final subscriptionPromptNotifier = ref.read(
      subscriptionPromptProvider.notifier,
    );
    final success = await subscriptionPromptNotifier.subscribeUser();

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

      // Request notification permission
      await _requestNotificationPermission();
    } else if (mounted) {
      // Show error message
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.error, color: Colors.white),
              SizedBox(width: 8),
              Text('Failed to subscribe. Please try again.'),
            ],
          ),
          backgroundColor: Theme.of(context).appColors.authError,
          duration: const Duration(seconds: 3),
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
    final subscriptionPromptNotifier = ref.read(
      subscriptionPromptProvider.notifier,
    );
    await subscriptionPromptNotifier.dismissPrompt();

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

  Future<void> _requestNotificationPermission() async {
    try {
      final notificationService = NotificationService();
      final granted =
          await notificationService.requestNotificationPermissions();

      if (granted) {
        debugPrint('Notification permission granted');
      } else {
        debugPrint('Notification permission denied');
        // Show a non-intrusive message that they can still get jokes in the app
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('You can still enjoy jokes in the app anytime! 😊'),
              duration: Duration(seconds: 2),
            ),
          );
        }
      }
    } catch (e) {
      debugPrint('Error requesting notification permission: $e');
    }
  }
}
