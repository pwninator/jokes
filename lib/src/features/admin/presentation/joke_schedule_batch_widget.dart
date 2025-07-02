import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/admin/presentation/calendar_grid_widget.dart';

class JokeScheduleBatchWidget extends ConsumerWidget {
  final DateTime monthDate;

  const JokeScheduleBatchWidget({
    super.key,
    required this.monthDate,
  });

  static const monthNames = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
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
                          final daysInMonth = DateTime(monthDate.year, monthDate.month + 1, 0).day;
                          
                          return Text(
                            '$jokeCount of $daysInMonth days scheduled',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                            ),
                          );
                        },
                        loading: () => Text(
                          'Loading...',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                          ),
                        ),
                        error: (_, __) => Text(
                          'Error loading data',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.error,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                
                // Edit button
                FilledButton.tonal(
                  onPressed: selectedScheduleId != null 
                      ? () => _openBatchEditor(context, selectedScheduleId, monthDate) 
                      : null,
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.edit, size: 16),
                      SizedBox(width: 4),
                      Text('Edit'),
                    ],
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 16),
            
            // Calendar grid
            batchesAsync.when(
              data: (batches) {
                final batch = _findBatchForMonth(batches, monthDate);
                return CalendarGridWidget(
                  batch: batch,
                  monthDate: monthDate,
                );
              },
              loading: () => Container(
                height: 200,
                child: const Center(
                  child: CircularProgressIndicator(),
                ),
              ),
              error: (error, _) => Container(
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
                          color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
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

  JokeScheduleBatch? _findBatchForMonth(List<JokeScheduleBatch> batches, DateTime monthDate) {
    for (final batch in batches) {
      if (batch.year == monthDate.year && batch.month == monthDate.month) {
        return batch;
      }
    }
    return null;
  }

  void _openBatchEditor(BuildContext context, String scheduleId, DateTime monthDate) {
    // TODO: Navigate to JokeScheduleBatchEditorScreen
    // This will be implemented later as mentioned in the requirements
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Batch editor will be implemented in the next phase'),
      ),
    );
  }
} 