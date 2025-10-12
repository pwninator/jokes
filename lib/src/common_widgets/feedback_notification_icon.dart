import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/badged_icon.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';

class FeedbackNotificationIcon extends ConsumerWidget {
  const FeedbackNotificationIcon({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unread = ref.watch(unreadFeedbackProvider);
    final hasUnread = unread.isNotEmpty;

    return Stack(
      children: [
        IconButton(
          key: const Key('feedback_notification_icon-open-button'),
          icon: BadgedIcon(
            icon: Icons.feedback_outlined,
            showBadge: hasUnread,
            iconSemanticLabel: 'Feedback',
            badgeSemanticLabel: 'New reply',
          ),
          color: Theme.of(context).colorScheme.primary,
          tooltip: hasUnread ? 'Feedback reply' : 'Feedback',
          onPressed: () async {
            final router = GoRouter.maybeOf(context);
            final messenger = ScaffoldMessenger.of(context);
            final successColor = Theme.of(context).colorScheme.primary;

            Future<bool?> navigationFuture;
            if (router != null) {
              navigationFuture = router.pushNamed<bool>(RouteNames.feedback);
            } else {
              navigationFuture = Navigator.of(context).push<bool>(
                MaterialPageRoute(builder: (_) => const UserFeedbackScreen()),
              );
            }

            final result = await navigationFuture;
            if (!context.mounted || result != true) {
              return;
            }

            messenger.showSnackBar(
              SnackBar(
                content: const Text('Thanks for your feedback!'),
                backgroundColor: successColor,
              ),
            );
          },
        ),
      ],
    );
  }
}
