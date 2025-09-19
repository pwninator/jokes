import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';

class FeedbackNotificationIcon extends ConsumerWidget {
  const FeedbackNotificationIcon({super.key, this.feedbackEntry});

  /// Optional feedback entry to display. If null, shows regular feedback icon.
  /// If provided, shows unread indicator and displays this specific feedback.
  final FeedbackEntry? feedbackEntry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Stack(
      children: [
        IconButton(
          icon: const Icon(Icons.feedback_outlined),
          color: Theme.of(context).colorScheme.primary,
          tooltip: 'Feedback',
          onPressed: () {
            showDialog(
              context: context,
              builder: (context) =>
                  FeedbackDialog(feedbackEntry: feedbackEntry),
            );
          },
        ),
        // Indicator for unread feedback - only show when feedbackEntry is provided
        if (feedbackEntry != null)
          Positioned(
            right: 8,
            top: 8,
            child: Container(
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                color: Colors.red,
                borderRadius: BorderRadius.circular(6),
              ),
              constraints: const BoxConstraints(minWidth: 12, minHeight: 12),
            ),
          ),
      ],
    );
  }
}
