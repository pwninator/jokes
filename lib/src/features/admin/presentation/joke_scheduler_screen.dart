import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_batch_widget.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_widgets.dart';

class JokeSchedulerScreen extends ConsumerWidget {
  const JokeSchedulerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final schedulesAsync = ref.watch(jokeSchedulesProvider);
    final selectedScheduleId = ref.watch(selectedScheduleProvider);
    final dateRange = ref.watch(batchDateRangeProvider);
    final showDialog = ref.watch(newScheduleDialogProvider);

    // Show dialog when needed
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (showDialog) {
        _showNewScheduleDialog(context, ref);
      }
    });

    return Scaffold(
      appBar: const AppBarWidget(
        title: 'Joke Scheduler',
      ),
      body: Column(
        children: [
          // Schedule selector header
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                // Schedule dropdown
                Expanded(
                  child: schedulesAsync.when(
                    data: (schedules) => _buildScheduleDropdown(
                      context,
                      ref,
                      schedules,
                      selectedScheduleId,
                    ),
                    loading: () => const SizedBox(
                      height: 48,
                      child: Center(child: CircularProgressIndicator()),
                    ),
                    error: (error, _) => Container(
                      height: 48,
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: Theme.of(context).colorScheme.error,
                        ),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Center(
                        child: Text(
                          'Error loading schedules',
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                
                const SizedBox(width: 12),
                
                // Add schedule button
                FilledButton.tonal(
                  onPressed: () => _openNewScheduleDialog(ref),
                  child: const Icon(Icons.add),
                ),
              ],
            ),
          ),
          
          // Divider
          const Divider(),
          
          // Batch list
          Expanded(
            child: selectedScheduleId == null
                ? _buildEmptyState(context)
                : dateRange.isEmpty
                    ? _buildLoadingState()
                    : ListView.builder(
                        itemCount: dateRange.length,
                        itemBuilder: (context, index) {
                          return JokeScheduleBatchWidget(
                            monthDate: dateRange[index],
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildScheduleDropdown(
    BuildContext context,
    WidgetRef ref,
    List schedules,
    String? selectedScheduleId,
  ) {
    if (schedules.isEmpty) {
      return Container(
        height: 48,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          border: Border.all(
            color: Theme.of(context).colorScheme.outline,
          ),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Center(
          child: Text(
            'No schedules available',
            style: TextStyle(fontStyle: FontStyle.italic),
          ),
        ),
      );
    }

    return DropdownButtonFormField<String>(
      value: selectedScheduleId,
      decoration: const InputDecoration(
        labelText: 'Select Schedule',
        border: OutlineInputBorder(),
      ),
      items: schedules.map((schedule) {
        return DropdownMenuItem<String>(
          value: schedule.id,
          child: Text(schedule.name),
        );
      }).toList(),
      onChanged: (value) {
        ref.read(selectedScheduleProvider.notifier).state = value;
      },
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.schedule_outlined,
            size: 64,
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
          ),
          const SizedBox(height: 16),
          Text(
            'No schedule selected',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Create a schedule to get started',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Loading schedule data...'),
        ],
      ),
    );
  }

  void _openNewScheduleDialog(WidgetRef ref) {
    ref.read(newScheduleDialogProvider.notifier).state = true;
  }

  void _showNewScheduleDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (context) => const NewScheduleDialog(),
    ).then((_) {
      // Reset dialog state when closed
      ref.read(newScheduleDialogProvider.notifier).state = false;
    });
  }
} 