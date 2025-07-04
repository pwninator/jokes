import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';

class CalendarCellPopup extends ConsumerWidget {
  final Joke joke;
  final String dayLabel;
  final Offset cellPosition;
  final Size cellSize;

  const CalendarCellPopup({
    super.key,
    required this.joke,
    required this.dayLabel,
    required this.cellPosition,
    required this.cellSize,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final screenSize = MediaQuery.of(context).size;
    const popupWidth = 320.0;
    const popupHeight = 240.0;
    
    // Calculate popup position - center horizontally on cell, position above
    double left = cellPosition.dx + (cellSize.width / 2) - (popupWidth / 2);
    double top = cellPosition.dy - popupHeight - 8; // 8px gap above cell
    
    // Ensure popup stays within screen bounds
    left = left.clamp(16.0, screenSize.width - popupWidth - 16.0);
    top = top.clamp(16.0, screenSize.height - popupHeight - 16.0);

    return Positioned(
      left: left,
      top: top,
      child: Material(
        color: Colors.transparent,
        child: Container(
          width: popupWidth,
          height: popupHeight,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.3),
                blurRadius: 12,
                offset: const Offset(0, 6),
              ),
            ],
            border: Border.all(
              color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Header
              Text(
                'Day $dayLabel',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              
              // Side-by-side images
              Expanded(
                child: Row(
                  children: [
                    // Setup image
                    Expanded(
                      child: Column(
                        children: [
                          Text(
                            'Setup',
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Expanded(
                            child: CachedJokeImage(
                              imageUrl: joke.setupImageUrl,
                              fit: BoxFit.cover,
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    
                    // Punchline image
                    Expanded(
                      child: Column(
                        children: [
                          Text(
                            'Punchline',
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Expanded(
                            child: CachedJokeImage(
                              imageUrl: joke.punchlineImageUrl,
                              fit: BoxFit.cover,
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 12),
              
              // Joke text
              Text(
                joke.setupText,
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class NewScheduleDialog extends ConsumerWidget {
  const NewScheduleDialog({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoading = ref.watch(scheduleCreationLoadingProvider);
    final scheduleName = ref.watch(newScheduleNameProvider);

    return AlertDialog(
      title: const Text('Create New Schedule'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Schedule Name',
              hintText: 'Enter schedule name',
              border: OutlineInputBorder(),
            ),
            onChanged: (value) {
              ref.read(newScheduleNameProvider.notifier).state = value;
            },
            onSubmitted: (_) => _createSchedule(context, ref),
            enabled: !isLoading,
          ),
          if (scheduleName.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'ID: ${JokeSchedule.sanitizeId(scheduleName)}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                fontFamily: 'monospace',
              ),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: isLoading ? null : () => _cancelDialog(context, ref),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: isLoading || scheduleName.trim().isEmpty 
              ? null 
              : () => _createSchedule(context, ref),
          child: isLoading
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Create'),
        ),
      ],
    );
  }

  void _cancelDialog(BuildContext context, WidgetRef ref) {
    ref.read(newScheduleDialogProvider.notifier).state = false;
    ref.read(newScheduleNameProvider.notifier).state = '';
    Navigator.of(context).pop();
  }

  Future<void> _createSchedule(BuildContext context, WidgetRef ref) async {
    final name = ref.read(newScheduleNameProvider).trim();
    if (name.isEmpty) return;

    ref.read(scheduleCreationLoadingProvider.notifier).state = true;

    try {
      await ref.read(jokeScheduleRepositoryProvider).createSchedule(name);
      
      if (context.mounted) {
        // Close dialog first - this is the key fix
        Navigator.of(context).pop();
        
        // Then reset providers
        ref.read(newScheduleDialogProvider.notifier).state = false;
        ref.read(newScheduleNameProvider.notifier).state = '';
        
        // Show success message
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Created schedule "$name"')),
        );
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to create schedule: $error'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    } finally {
      ref.read(scheduleCreationLoadingProvider.notifier).state = false;
    }
  }
}

 