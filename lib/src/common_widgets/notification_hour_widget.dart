import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

/// Formats hour (0-23) to 12-hour format with AM/PM
String _formatHour(int hour) {
  if (hour == 0) {
    return '12:00 AM';
  } else if (hour < 12) {
    return '${hour.toString().padLeft(2, '0')}:00 AM';
  } else if (hour == 12) {
    return '12:00 PM';
  } else {
    return '${(hour - 12).toString().padLeft(2, '0')}:00 PM';
  }
}

/// A custom 24-hour picker widget using CupertinoPicker spinner
///
/// Displays hours in 24-hour format (0-23) with a native iOS-style spinner interface.
/// Users can scroll/swipe to select the desired time.
class HourPickerWidget extends StatefulWidget {
  const HourPickerWidget({
    super.key,
    required this.selectedHour,
    required this.onHourChanged,
  });

  /// Currently selected hour (0-23)
  final int selectedHour;

  /// Callback when hour is changed
  final ValueChanged<int> onHourChanged;

  @override
  State<HourPickerWidget> createState() => _HourPickerWidgetState();
}

class _HourPickerWidgetState extends State<HourPickerWidget> {
  late FixedExtentScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _scrollController = FixedExtentScrollController(
      initialItem: widget.selectedHour,
    );
  }

  @override
  void didUpdateWidget(HourPickerWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.selectedHour != oldWidget.selectedHour) {
      _scrollController.jumpToItem(widget.selectedHour);
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.3),
          width: 1,
        ),
        color: theme.colorScheme.surface,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(Icons.schedule, size: 20, color: theme.colorScheme.primary),
              const SizedBox(width: 12),
              Text(
                'Notification time:',
                style: theme.textTheme.titleSmall!.copyWith(
                  color: theme.colorScheme.onSurface,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 200,
            child: CupertinoPicker(
              scrollController: _scrollController,
              itemExtent: 40,
              onSelectedItemChanged: (int index) {
                widget.onHourChanged(index);
              },
              children: List.generate(24, (int index) {
                return Center(
                  child: Text(
                    _formatHour(index),
                    style: theme.textTheme.titleMedium!.copyWith(
                      color: theme.colorScheme.onSurface,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }
}

/// A comprehensive hour display widget that manages notification hour selection
///
/// This widget encapsulates all logic for:
/// - Displaying the current notification hour
/// - Showing hour picker dialog on tap
/// - Handling hour changes and re-subscription
/// - Managing loading states and error handling
/// - Analytics tracking
class HourDisplayWidget extends ConsumerStatefulWidget {
  const HourDisplayWidget({super.key});

  @override
  ConsumerState<HourDisplayWidget> createState() => _HourDisplayWidgetState();
}

class _HourDisplayWidgetState extends ConsumerState<HourDisplayWidget> {
  bool _showingHourPicker = false;

  @override
  Widget build(BuildContext context) {
    // Watch the reactive subscription state
    final subscriptionState = ref.watch(subscriptionProvider);
    final hour = subscriptionState.hour;

    final hourDisplay = _formatHour(hour);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          'Notification time: $hourDisplay',
          style: TextStyle(
            color: Theme.of(
              context,
            ).colorScheme.onSurface.withValues(alpha: 0.7),
            fontSize: 14,
          ),
        ),
        TextButton(
          key: const Key('notification_hour_widget-change-hour-button'),
          onPressed: () => _showHourPickerDialog(hour),
          child: Text(
            'Change',
            style: TextStyle(
              color: Theme.of(context).colorScheme.primary,
              fontSize: 14,
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _showHourPickerDialog(int currentHour) async {
    if (_showingHourPicker) return;

    setState(() {
      _showingHourPicker = true;
    });

    int selectedHour = currentHour;

    final result = await showDialog<int>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change Notification Time'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'When would you like to receive your daily joke notifications?',
            ),
            const SizedBox(height: 20),
            HourPickerWidget(
              selectedHour: selectedHour,
              onHourChanged: (hour) {
                selectedHour = hour;
              },
            ),
          ],
        ),
        actions: [
          TextButton(
            key: const Key('notification_hour_widget-cancel-button'),
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('notification_hour_widget-save-button'),
            onPressed: () => Navigator.of(context).pop(selectedHour),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    setState(() {
      _showingHourPicker = false;
    });

    if (result != null && result != currentHour) {
      await _updateNotificationHour(result);
    }
  }

  Future<void> _updateNotificationHour(int newHour) async {
    final subscriptionNotifier = ref.read(subscriptionProvider.notifier);

    try {
      // Update hour using the reactive notifier (fast operation)
      await subscriptionNotifier.setHour(newHour);

      // Track analytics for hour change (fire-and-forget)
      final analyticsService = ref.read(analyticsServiceProvider);
      analyticsService.logSubscriptionTimeChanged(subscriptionHour: newHour);

      // Show success message
      if (mounted) {
        final hourDisplay = _formatHour(newHour);

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.white),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('Notification time updated to $hourDisplay'),
                ),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.primary,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } catch (e) {
      debugPrint('ERROR: _updateNotificationHour: $e');
      // Log analytics/crash for hour update failure
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logErrorSubscriptionTimeUpdate(
        source: 'notification_hour_widget',
        errorMessage: 'notification_hour_update_failed',
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error, color: Colors.white),
                const SizedBox(width: 8),
                Expanded(child: Text('Error updating notification time')),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.error,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    }
  }
}
