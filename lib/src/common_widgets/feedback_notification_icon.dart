import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class FeedbackNotificationIcon extends ConsumerWidget {
  const FeedbackNotificationIcon({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadFeedback = ref.watch(unreadFeedbackProvider);

    if (unreadFeedback.isEmpty) {
      return const SizedBox.shrink();
    }

    final feedbackToShow = unreadFeedback.first;

    return Stack(
      children: [
        IconButton(
          icon: const Icon(Icons.feedback),
          onPressed: () {
            showDialog(
              context: context,
              builder: (context) => FeedbackDialog(
                feedbackEntry: feedbackToShow,
              ),
            );
            // Mark as read
            ref
                .read(feedbackServiceProvider)
                .updateLastUserViewTime(feedbackToShow.id);
          },
        ),
        Positioned(
          right: 8,
          top: 8,
          child: Container(
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(
              color: Colors.red,
              borderRadius: BorderRadius.circular(6),
            ),
            constraints: const BoxConstraints(
              minWidth: 12,
              minHeight: 12,
            ),
          ),
        )
      ],
    );
  }
}
