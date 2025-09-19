import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';

class RescheduleDialog extends ConsumerWidget {
  final String jokeId;
  final DateTime initialDate;
  final String? scheduleId;
  final VoidCallback? onSuccess;
  final List<DateTime>? scheduledDates;

  const RescheduleDialog({
    super.key,
    required this.jokeId,
    required this.initialDate,
    this.scheduleId,
    this.onSuccess,
    this.scheduledDates,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    DateTime selectedDate = initialDate;

    return AlertDialog(
      title: const Text('Change scheduled date'),
      content: SizedBox(
        width: 300,
        height: 300,
        child: CalendarDatePicker(
          initialDate: initialDate,
          firstDate: DateTime.now().subtract(const Duration(days: 0)),
          lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
          selectableDayPredicate: (date) {
            // Allow selection of the current scheduled date (for the same joke)
            if (date.year == initialDate.year &&
                date.month == initialDate.month &&
                date.day == initialDate.day) {
              return true;
            }

            // Disable dates that already have jokes scheduled (excluding current joke)
            if (scheduledDates != null) {
              return !scheduledDates!.any(
                (scheduledDate) =>
                    scheduledDate.year == date.year &&
                    scheduledDate.month == date.month &&
                    scheduledDate.day == date.day,
              );
            }

            return true;
          },
          onDateChanged: (date) {
            selectedDate = DateTime(date.year, date.month, date.day);
          },
        ),
      ),
      actions: [
        TextButton(
          key: const Key('reschedule_dialog-cancel-button'),
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          key: const Key('reschedule_dialog-change-date-button'),
          onPressed: () async {
            try {
              final service = ref.read(jokeScheduleAutoFillServiceProvider);
              await service.scheduleJokeToDate(
                jokeId: jokeId,
                date: selectedDate,
                scheduleId: scheduleId ?? JokeConstants.defaultJokeScheduleId,
              );
              if (context.mounted) {
                Navigator.of(context).pop();
                onSuccess?.call();
              }
            } catch (e) {
              // Handle error gracefully - show a snackbar or just don't close the dialog
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Failed to reschedule joke: $e'),
                    backgroundColor: Theme.of(context).colorScheme.error,
                  ),
                );
              }
            }
          },
          child: const Text('Change date'),
        ),
      ],
    );
  }
}
