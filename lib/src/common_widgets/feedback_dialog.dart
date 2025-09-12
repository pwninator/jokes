import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';

class FeedbackDialog extends ConsumerStatefulWidget {
  const FeedbackDialog({super.key});

  @override
  ConsumerState<FeedbackDialog> createState() => _FeedbackDialogState();
}

class _FeedbackDialogState extends ConsumerState<FeedbackDialog> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    // Focus the text field after the dialog is built
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
    // Log analytics for dialog shown and mark viewed
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final analytics = ref.read(analyticsServiceProvider);
        analytics.logFeedbackDialogShown();
      } catch (_) {}
      try {
        final store = ref.read(feedbackPromptStateStoreProvider);
        await store.markViewed();
        // Invalidate eligibility so the app bar button hides immediately
        ref.read(appUsageEventsProvider.notifier).state++;
      } catch (_) {}
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Help Us Perfect the Recipe! 🍪'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Our mission is to brighten your day, one joke at a time. How are we doing?\n\n'
              "Whether you have a joke you'd like to submit, a feature request, found a pesky bug, or just want to say hello, "
              'we read every message and appreciate you helping us improve!',
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: 500,
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                maxLines: 5,
                decoration: const InputDecoration(border: OutlineInputBorder()),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _submitting ? null : _handleSubmit,
          child: _submitting
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Submit'),
        ),
      ],
    );
  }

  Future<void> _handleSubmit() async {
    setState(() => _submitting = true);
    try {
      final service = ref.read(feedbackServiceProvider);
      final currentUser = ref.read(currentUserProvider);
      await service.submitFeedback(_controller.text, currentUser);
      if (mounted) {
        Navigator.of(context).pop(true);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Thanks for your feedback!'),
            backgroundColor: Theme.of(context).colorScheme.primary,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } catch (e) {
      debugPrint('ERROR: feedback_dialog: _handleSubmit: $e');
      // Log analytics/crash for feedback submission failure
      try {
        final analytics = ref.read(analyticsServiceProvider);
        analytics.logErrorFeedbackSubmit(
          errorMessage: 'feedback_submit_failed',
        );
      } catch (_) {}
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to submit feedback'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }
}
