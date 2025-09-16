import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

// Track which feedback IDs have been scheduled for READ update to avoid duplicates
final Set<String> _scheduledMarkReadIds = <String>{};

class JokeFeedbackScreen extends ConsumerWidget implements TitledScreen {
  const JokeFeedbackScreen({super.key});

  @override
  String get title => 'Feedback';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncFeedback = ref.watch(allFeedbackProvider);

    return AdaptiveAppBarScreen(
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
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final entry = items[index];
              final usageAsync = ref.watch(jokeUserUsageProvider(entry.userId));

              // Mark as READ if currently NEW, once per ID to prevent duplicates
              if (entry.state == FeedbackState.NEW) {
                if (!_scheduledMarkReadIds.contains(entry.id)) {
                  _scheduledMarkReadIds.add(entry.id);
                  Future.microtask(() async {
                    await ref
                        .read(feedbackRepositoryProvider)
                        .markFeedbackRead(entry.id);
                  });
                }
              }

              return Card(
                child: ListTile(
                  leading: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      const Icon(Icons.feedback),
                      if (entry.state == FeedbackState.NEW)
                        Positioned(
                          right: -2,
                          top: -2,
                          child: Container(
                            width: 10,
                            height: 10,
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.error,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                    ],
                  ),
                  title: Text(entry.feedbackText),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _formatTimestamp('Created', entry.creationTime),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).hintColor,
                        ),
                      ),
                      const SizedBox(height: 4),
                      usageAsync.when(
                        loading: () => const Text('Loading usage…'),
                        error: (e, st) => const Text('Usage unavailable'),
                        data: (usage) {
                          final u = usage;
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (u?.lastLoginAt != null)
                                Text(
                                  _formatTimestamp(
                                    'Last login',
                                    u!.lastLoginAt,
                                  ),
                                  style: Theme.of(context).textTheme.bodySmall
                                      ?.copyWith(
                                        color: Theme.of(context).hintColor,
                                      ),
                                ),
                              const SizedBox(height: 4),
                              Wrap(
                                spacing: 16,
                                runSpacing: 8,
                                children: [
                                  _metric(
                                    context,
                                    Icons.calendar_today,
                                    u?.clientNumDaysUsed,
                                    'days',
                                  ),
                                  _metric(
                                    context,
                                    Icons.visibility,
                                    u?.clientNumViewed,
                                    'views',
                                  ),
                                  _metric(
                                    context,
                                    Icons.favorite,
                                    u?.clientNumSaved,
                                    'saves',
                                  ),
                                  _metric(
                                    context,
                                    Icons.share,
                                    u?.clientNumShared,
                                    'shares',
                                  ),
                                ],
                              ),
                            ],
                          );
                        },
                      ),
                    ],
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
