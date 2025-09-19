import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class FeedbackNotificationIcon extends ConsumerWidget {
  const FeedbackNotificationIcon({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unread = ref.watch(unreadFeedbackProvider);
    final FeedbackEntry? entryToShow = unread.isNotEmpty ? unread.first : null;
    return Stack(
      children: [
        IconButton(
          icon: const Icon(Icons.feedback_outlined),
          color: Theme.of(context).colorScheme.primary,
          tooltip: entryToShow != null ? 'Feedback reply' : 'Feedback',
          onPressed: () {
            showDialog(
              context: context,
              builder: (context) => FeedbackDialog(feedbackEntry: entryToShow),
            );
          },
        ),
        // Indicator for unread feedback - only show when feedbackEntry is provided
        if (entryToShow != null)
          Positioned(
            right: 8,
            top: 8,
            child: Semantics(
              label: 'New reply',
              container: true,
              child: Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.error,
                  borderRadius: BorderRadius.circular(6),
                ),
                constraints: const BoxConstraints(minWidth: 12, minHeight: 12),
              ),
            ),
          ),
      ],
    );
  }
}
