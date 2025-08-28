import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/features/admin/presentation/calendar_grid_widget.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

class JokeScheduleBatchWidget extends ConsumerWidget {
  final DateTime monthDate;

  const JokeScheduleBatchWidget({super.key, required this.monthDate});

  static const monthNames = [
    '',
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final batchesAsync = ref.watch(scheduleBatchesProvider);
    final selectedScheduleId = ref.watch(selectedScheduleProvider);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with month/year and edit button
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${monthNames[monthDate.month]} ${monthDate.year}',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      batchesAsync.when(
                        data: (batches) {
                          final batch = _findBatchForMonth(batches, monthDate);
                          final jokeCount = batch?.jokes.length ?? 0;
                          final daysInMonth = DateTime(
                            monthDate.year,
                            monthDate.month + 1,
                            0,
                          ).day;

                          return Text(
                            '$jokeCount of $daysInMonth days scheduled',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurface.withValues(
                                alpha: 0.6,
                              ),
                            ),
                          );
                        },
                        loading: () => Text(
                          'Loading...',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurface.withValues(
                              alpha: 0.6,
                            ),
                          ),
                        ),
                        error: (_, _) => Text(
                          'Error loading data',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.error,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                // Auto Fill button
                FilledButton.tonal(
                  key: const Key('auto-fill-button'),
                  onPressed: selectedScheduleId != null
                      ? () => _autoFillMonth(
                          context,
                          ref,
                          selectedScheduleId,
                          monthDate,
                        )
                      : null,
                  child:
                      () {
                        final state = ref.watch(autoFillProvider);
                        final monthKey =
                            '${selectedScheduleId ?? ''}_${monthDate.year}_${monthDate.month}';
                        return state.processingMonths.contains(monthKey);
                      }()
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            key: Key('auto-fill-loading'),
                            strokeWidth: 2,
                          ),
                        )
                      : const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.auto_awesome, size: 16),
                            SizedBox(width: 4),
                            Text('Auto Fill'),
                          ],
                        ),
                ),
                const SizedBox(width: 8),
                HoldableButton(
                  theme: theme,
                  icon: Icons.delete_outline,
                  color: theme.colorScheme.errorContainer,
                  onTap: () {
                    // Do nothing on tap
                  },
                  onHoldComplete: () {
                    if (selectedScheduleId != null) {
                      _deleteBatch(context, ref, selectedScheduleId, monthDate);
                    }
                  },
                  tooltip: "Delete this month's schedule",
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Calendar grid
            batchesAsync.when(
              data: (batches) {
                final batch = _findBatchForMonth(batches, monthDate);
                return CalendarGridWidget(batch: batch, monthDate: monthDate);
              },
              loading: () => SizedBox(
                height: 200,
                child: const Center(
                  child: CircularProgressIndicator(
                    key: Key('calendar-loading'),
                  ),
                ),
              ),
              error: (error, _) => SizedBox(
                height: 200,
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.error_outline,
                        color: theme.colorScheme.error,
                        size: 48,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Failed to load schedule data',
                        style: TextStyle(color: theme.colorScheme.error),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        error.toString(),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.6,
                          ),
                        ),
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  JokeScheduleBatch? _findBatchForMonth(
    List<JokeScheduleBatch> batches,
    DateTime monthDate,
  ) {
    for (final batch in batches) {
      if (batch.year == monthDate.year && batch.month == monthDate.month) {
        return batch;
      }
    }
    return null;
  }

  Future<void> _autoFillMonth(
    BuildContext context,
    WidgetRef ref,
    String scheduleId,
    DateTime monthDate,
  ) async {
    try {
      // Show confirmation dialog
      final confirmed = await _showAutoFillConfirmationDialog(
        context,
        monthDate,
      );
      if (!confirmed) return;

      // Execute auto-fill
      final success = await ref
          .read(autoFillProvider.notifier)
          .autoFillMonth(scheduleId, monthDate);

      if (!context.mounted) return;

      // Show result
      final result = ref.read(autoFillProvider).lastResult;
      if (result != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result.summaryMessage),
            backgroundColor: success
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.error,
            action: success && result.warnings.isNotEmpty
                ? SnackBarAction(
                    label: 'Details',
                    textColor: Colors.white,
                    onPressed: () {
                      _showWarningsDialog(context, result.warnings);
                    },
                  )
                : null,
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Auto-fill failed: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    }
  }

  Future<bool> _showAutoFillConfirmationDialog(
    BuildContext context,
    DateTime monthDate,
  ) async {
    final monthName = monthNames[monthDate.month];

    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            key: const Key('auto-fill-confirmation-dialog'),
            title: const Text('Auto Fill Schedule'),
            content: Text(
              key: const Key('auto-fill-dialog-content'),
              'Auto-fill $monthName ${monthDate.year} with eligible jokes?\n\n'
              'This will:\n'
              '• Fill empty days with jokes that have positive ratings\n'
              '• Randomize joke order\n'
              '• Skip jokes already scheduled in other months\n'
              '• Preserve any manually scheduled jokes',
            ),
            actions: [
              TextButton(
                key: const Key('auto-fill-cancel-button'),
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                key: const Key('auto-fill-confirm-button'),
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Auto Fill'),
              ),
            ],
          ),
        ) ??
        false;
  }

  void _showWarningsDialog(BuildContext context, List<String> warnings) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Auto Fill Warnings'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: warnings
              .map(
                (warning) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.warning_amber,
                        size: 16,
                        color: Theme.of(context).colorScheme.error,
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(warning)),
                    ],
                  ),
                ),
              )
              .toList(),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _deleteBatch(
    BuildContext context,
    WidgetRef ref,
    String scheduleId, // Made non-nullable
    DateTime monthDate,
  ) async {
    try {
      final batchId = JokeScheduleBatch.createBatchId(
        scheduleId,
        monthDate.year,
        monthDate.month,
      );
      await ref.read(jokeScheduleRepositoryProvider).deleteBatch(batchId);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Successfully deleted schedule for ${monthNames[monthDate.month]} ${monthDate.year}',
            ),
            backgroundColor: Theme.of(context).colorScheme.primary,
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to delete batch: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    }
  }
}
