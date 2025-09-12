import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_dialog.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

/// Global overlay that listens to subscription prompt state and shows dialog when needed
class SubscriptionPromptOverlay extends ConsumerStatefulWidget {
  final Widget child;

  const SubscriptionPromptOverlay({super.key, required this.child});

  @override
  ConsumerState<SubscriptionPromptOverlay> createState() =>
      _SubscriptionPromptOverlayState();
}

class _SubscriptionPromptOverlayState
    extends ConsumerState<SubscriptionPromptOverlay> {
  bool _isDialogShowing = false;

  @override
  Widget build(BuildContext context) {
    // Listen to subscription prompt state.
    // CRITICAL: Listening to subscriptionPromptProvider here is needed to trigger
    // a notification sync in the background in SubscriptionNotifier's constructor.
    ref.listen<SubscriptionPromptState>(subscriptionPromptProvider, (
      previous,
      current,
    ) {
      // Show dialog when state changes to shouldShowPrompt = true
      if (current.shouldShowPrompt && !_isDialogShowing) {
        _showSubscriptionDialog();
      }
    });

    return widget.child;
  }

  Future<void> _showSubscriptionDialog() async {
    // Ensure we're not already showing the dialog
    if (_isDialogShowing) return;

    _isDialogShowing = true;

    // Track analytics for prompt shown
    final analyticsService = ref.read(analyticsServiceProvider);

    // Wait for the next frame to ensure UI is ready
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;

      try {
        // Check mounted again after async operation
        if (!mounted) return;

        await showDialog<void>(
          context: context,
          barrierDismissible: false, // User must choose an option
          builder: (context) => const SubscriptionPromptDialog(),
        );
        analyticsService.logSubscriptionPromptShown().catchError((_) {});
      } catch (e) {
        debugPrint('Error showing subscription dialog: $e');
        analyticsService
            .logErrorSubscriptionPrompt(
              errorMessage: e.toString(),
              phase: 'show_dialog',
            )
            .catchError((_) {});
      } finally {
        if (mounted) {
          _isDialogShowing = false;
        }
      }
    });
  }
}
