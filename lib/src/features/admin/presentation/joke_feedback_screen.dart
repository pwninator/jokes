import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class JokeFeedbackScreen extends ConsumerWidget implements TitledScreen {
  const JokeFeedbackScreen({super.key});

  @override
  String get title => 'Feedback';

  /// Gets the latest message from a user in the conversation
  FeedbackConversationEntry? _getLatestUserMessage(FeedbackEntry entry) {
    for (int i = entry.conversation.length - 1; i >= 0; i--) {
      final message = entry.conversation[i];
      if (message.speaker == SpeakerType.user) {
        return message;
      }
    }
    return null;
  }

  Color _getIconColor(FeedbackEntry entry, BuildContext context) {
    if (entry.conversation.isEmpty) {
      return Colors.red;
    }
    final last = entry.conversation.last;
    // Yellow for user messages, Green for admin messages
    return last.speaker == SpeakerType.user ? Colors.yellow : Colors.green;
  }

  IconData _getIcon(FeedbackEntry entry) {
    if (entry.conversation.isEmpty) {
      return Icons.feedback;
    }
    final last = entry.conversation.last;

    // Check if the last message has been read based on who sent it
    bool isRead = false;
    if (last.speaker == SpeakerType.user) {
      // User message - check if admin has viewed it
      final adminViewTime = entry.lastAdminViewTime;
      isRead = adminViewTime != null && adminViewTime.isAfter(last.timestamp);
    } else {
      // Admin message - check if user has viewed it
      final userViewTime = entry.lastUserViewTime;
      isRead = userViewTime != null && userViewTime.isAfter(last.timestamp);
    }

    // Solid icon if unread, outline icon if read
    return isRead ? Icons.feedback_outlined : Icons.feedback;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncFeedback = ref.watch(allFeedbackProvider);

    return AppBarConfiguredScreen(
      title: title,
      body: asyncFeedback.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => Center(child: Text('Error: $e')),
        data: (items) {
          if (items.isEmpty) {
            return const Center(child: Text('No feedback yet'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(8),
            itemCount: items.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final entry = items[index];
              final usageAsync = ref.watch(jokeUserUsageProvider(entry.userId));

              return Card(
                child: ListTile(
                  leading: Icon(
                    _getIcon(entry),
                    color: _getIconColor(entry, context),
                  ),
                  title: Text(() {
                    final latestUserMessage = _getLatestUserMessage(entry);
                    if (latestUserMessage != null) {
                      return latestUserMessage.text;
                    }
                    return entry.conversation.isNotEmpty
                        ? 'Admin response only'
                        : 'No messages yet';
                  }()),
                  subtitle: usageAsync.when(
                    loading: () => const Text('Loading usage...'),
                    error: (e, st) => const Text('Usage unavailable'),
                    data: (usage) {
                      final style = Theme.of(context).textTheme.bodySmall
                          ?.copyWith(color: Theme.of(context).hintColor);
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _formatTimestamp('First login', usage?.createdAt),
                            style: style,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            _formatTimestamp('Last login', usage?.lastLoginAt),
                            style: style,
                          ),
                          const SizedBox(height: 4),
                          Wrap(
                            spacing: 16,
                            runSpacing: 8,
                            children: [
                              _metric(
                                context,
                                Icons.calendar_today,
                                usage?.clientNumDaysUsed,
                                'days',
                              ),
                              _metric(
                                context,
                                Icons.visibility,
                                usage?.clientNumViewed,
                                'views',
                              ),
                              _metric(
                                context,
                                Icons.favorite,
                                usage?.clientNumSaved,
                                'saves',
                              ),
                              _metric(
                                context,
                                Icons.share,
                                usage?.clientNumShared,
                                'shares',
                              ),
                            ],
                          ),
                        ],
                      );
                    },
                  ),
                  onTap: () => context.pushNamed(
                    RouteNames.adminFeedbackDetails,
                    pathParameters: {'feedbackId': entry.id},
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

String _formatTimestamp(String label, DateTime? dt) {
  if (dt == null) return '$label: —';
  return '$label: ${_laDateString(dt)}';
}

Widget _metric(
  BuildContext context,
  IconData icon,
  int? value,
  String semanticsLabel,
) {
  final color = Theme.of(context).colorScheme.onSurfaceVariant;
  return Semantics(
    label: '$semanticsLabel: ${value ?? '-'}',
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: 4),
        Text('${value ?? '-'}'),
      ],
    ),
  );
}

String _laDateString(DateTime dt) {
  // Initialize TZ database lazily
  // Safe to call multiple times; no-ops after first init
  tzdata.initializeTimeZones();
  final la = tz.getLocation('America/Los_Angeles');
  // Convert instant to LA timezone and format as YYYY-MM-DD
  final laDt = tz.TZDateTime.from(dt.isUtc ? dt : dt.toUtc(), la);
  final y = laDt.year.toString().padLeft(4, '0');
  final m = laDt.month.toString().padLeft(2, '0');
  final d = laDt.day.toString().padLeft(2, '0');
  return '$y-$m-$d';
}
