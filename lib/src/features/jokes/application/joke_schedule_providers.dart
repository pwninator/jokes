import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

// Repository provider
final jokeScheduleRepositoryProvider = Provider<JokeScheduleRepository>((ref) {
  return FirestoreJokeScheduleRepository();
});

// Real-time schedules stream
final jokeSchedulesProvider = StreamProvider<List<JokeSchedule>>((ref) {
  return ref.watch(jokeScheduleRepositoryProvider).watchSchedules();
});

// Selected schedule state with auto-selection
final selectedScheduleProvider = StateProvider<String?>((ref) {
  // Auto-select first schedule when schedules are loaded
  ref.listen(jokeSchedulesProvider, (previous, next) {
    next.whenData((schedules) {
      final currentState = ref.controller.state;
      if (schedules.isNotEmpty && currentState == null) {
        ref.controller.state = schedules.first.id;
      } else if (schedules.isEmpty && currentState != null) {
        ref.controller.state = null;
      }
    });
  });
  
  return null;
});

// Real-time batches for selected schedule
final scheduleBatchesProvider = StreamProvider<List<JokeScheduleBatch>>((ref) {
  final selectedScheduleId = ref.watch(selectedScheduleProvider);
  if (selectedScheduleId == null) return Stream.value([]);
  
  return ref.watch(jokeScheduleRepositoryProvider)
      .watchBatchesForSchedule(selectedScheduleId);
});

// Date range provider - calculates which months to show
final batchDateRangeProvider = Provider<List<DateTime>>((ref) {
  final batchesAsync = ref.watch(scheduleBatchesProvider);
  
  return batchesAsync.when(
    data: (batches) {
      final now = DateTime.now();
      final thisMonth = DateTime(now.year, now.month);
      final nextMonth = DateTime(now.year, now.month + 1);
      final prevMonth = DateTime(now.year, now.month - 1);
      
      DateTime topBound = nextMonth; // Default: next month
      DateTime bottomBound = prevMonth; // Default: previous month
      
      if (batches.isNotEmpty) {
        // Find earliest and latest batches
        final sortedBatches = batches.toList()..sort((a, b) {
          final aDate = DateTime(a.year, a.month);
          final bDate = DateTime(b.year, b.month);
          return aDate.compareTo(bDate);
        });
        
        final earliestBatch = DateTime(sortedBatches.first.year, sortedBatches.first.month);
        final latestBatch = DateTime(sortedBatches.last.year, sortedBatches.last.month);
        
        // Apply the user's requirements:
        // Top: latest batch OR next month, whichever is later
        // Bottom: earliest batch OR previous month, whichever is earlier
        topBound = latestBatch.isAfter(nextMonth) ? latestBatch : nextMonth;
        bottomBound = earliestBatch.isBefore(prevMonth) ? earliestBatch : prevMonth;
      }
      
      // Generate all months between bounds (inclusive)
      final months = <DateTime>[];
      var current = bottomBound;
      while (current.isBefore(topBound) || current.isAtSameMomentAs(topBound)) {
        months.add(current);
        current = DateTime(current.year, current.month + 1);
      }
      
      // Sort chronologically with latest at top (reverse order)
      months.sort((a, b) => b.compareTo(a));
      
      return months;
    },
    loading: () => [], // Empty while loading
    error: (_, __) => [], // Empty on error
  );
});

// UI state providers
final newScheduleDialogProvider = StateProvider<bool>((ref) => false);
final newScheduleNameProvider = StateProvider<String>((ref) => '');

// Loading states for async operations
final scheduleCreationLoadingProvider = StateProvider<bool>((ref) => false);
final batchUpdateLoadingProvider = StateProvider<Set<String>>((ref) => {}); 