import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_auto_fill_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy_registry.dart';

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

  return ref
      .watch(jokeScheduleRepositoryProvider)
      .watchBatchesForSchedule(selectedScheduleId);
});

// Date range provider - calculates which months to show
final batchDateRangeProvider = Provider<List<DateTime>>((ref) {
  final batchesAsync = ref.watch(scheduleBatchesProvider);

  return batchesAsync.when(
    data: (batches) {
      final now = DateTime.now();
      final nextMonth = DateTime(now.year, now.month + 1);
      final prevMonth = DateTime(now.year, now.month - 1);

      DateTime topBound = nextMonth; // Default: next month
      DateTime bottomBound = prevMonth; // Default: previous month

      if (batches.isNotEmpty) {
        // Find earliest and latest batches
        final sortedBatches = batches.toList()
          ..sort((a, b) {
            final aDate = DateTime(a.year, a.month);
            final bDate = DateTime(b.year, b.month);
            return aDate.compareTo(bDate);
          });

        final earliestBatch = DateTime(
          sortedBatches.first.year,
          sortedBatches.first.month,
        );
        final latestBatch = DateTime(
          sortedBatches.last.year,
          sortedBatches.last.month,
        );

        // Apply the user's requirements:
        // Top: latest batch OR next month, whichever is later
        // Bottom: earliest batch OR previous month, whichever is earlier
        topBound = latestBatch.isAfter(nextMonth) ? latestBatch : nextMonth;
        bottomBound = earliestBatch.isBefore(prevMonth)
            ? earliestBatch
            : prevMonth;
      }

      // Generate all months between bounds (inclusive)
      final months = <DateTime>[];
      var current = bottomBound;
      while (current.isBefore(topBound) || current.isAtSameMomentAs(topBound)) {
        months.add(current);
        current = DateTime(current.year, current.month + 1);
      }

      // Sort chronologically with earliest at top (chronological order)
      months.sort((a, b) => a.compareTo(b));

      return months;
    },
    loading: () => [], // Empty while loading
    error: (_, _) => [], // Empty on error
  );
});

// UI state providers
final newScheduleDialogProvider = StateProvider<bool>((ref) => false);
final newScheduleNameProvider = StateProvider<String>((ref) => '');

// Loading states for async operations
final scheduleCreationLoadingProvider = StateProvider<bool>((ref) => false);
final batchUpdateLoadingProvider = StateProvider<Set<String>>((ref) => {});

// ============================================================================
// Auto-Fill Providers
// ============================================================================

// Auto-fill service provider
final jokeScheduleAutoFillServiceProvider =
    Provider<JokeScheduleAutoFillService>((ref) {
      final jokeRepository = ref.watch(jokeRepositoryProvider);
      final scheduleRepository = ref.watch(jokeScheduleRepositoryProvider);

      return JokeScheduleAutoFillService(
        jokeRepository: jokeRepository,
        scheduleRepository: scheduleRepository,
      );
    });

// Selected auto-fill strategy
final selectedAutoFillStrategyProvider = StateProvider<String>(
  (ref) => 'thumbs_up',
);

// Auto-fill state
class AutoFillState {
  final bool isLoading;
  final String? error;
  final AutoFillResult? lastResult;
  final Set<String> processingMonths; // Track which months are being processed

  const AutoFillState({
    this.isLoading = false,
    this.error,
    this.lastResult,
    this.processingMonths = const {},
  });

  AutoFillState copyWith({
    bool? isLoading,
    String? error,
    AutoFillResult? lastResult,
    Set<String>? processingMonths,
    bool clearError = false,
    bool clearResult = false,
  }) {
    return AutoFillState(
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      lastResult: clearResult ? null : (lastResult ?? this.lastResult),
      processingMonths: processingMonths ?? this.processingMonths,
    );
  }
}

// Auto-fill notifier
class AutoFillNotifier extends StateNotifier<AutoFillState> {
  AutoFillNotifier(this._service, this._ref) : super(const AutoFillState()) {
    // Initialize default strategies
    JokeEligibilityStrategyRegistry.initializeDefaultStrategies();
  }

  final JokeScheduleAutoFillService _service;
  final Ref _ref;

  /// Auto-fill a specific month using the currently selected strategy
  Future<bool> autoFillMonth(String scheduleId, DateTime monthDate) async {
    final monthKey = '${scheduleId}_${monthDate.year}_${monthDate.month}';

    // Add month to processing set
    state = state.copyWith(
      isLoading: true,
      processingMonths: {...state.processingMonths, monthKey},
      clearError: true,
    );

    try {
      // Get selected strategy
      final strategyName = _ref.read(selectedAutoFillStrategyProvider);
      final strategy = JokeEligibilityStrategyRegistry.getStrategy(
        strategyName,
      );

      // Execute auto-fill
      final result = await _service.autoFillMonth(
        scheduleId: scheduleId,
        monthDate: monthDate,
        strategy: strategy,
      );

      // Update state with result
      final updatedMonths = Set<String>.from(state.processingMonths)
        ..remove(monthKey);
      state = state.copyWith(
        isLoading: updatedMonths.isNotEmpty,
        lastResult: result,
        processingMonths: updatedMonths,
        error: result.success ? null : result.error,
      );

      return result.success;
    } catch (e) {
      // Handle error
      final updatedMonths = Set<String>.from(state.processingMonths)
        ..remove(monthKey);
      state = state.copyWith(
        isLoading: updatedMonths.isNotEmpty,
        error: 'Auto-fill failed: $e',
        processingMonths: updatedMonths,
      );
      return false;
    }
  }

  /// Check if a specific month is currently being processed
  bool isMonthProcessing(String scheduleId, DateTime monthDate) {
    final monthKey = '${scheduleId}_${monthDate.year}_${monthDate.month}';
    return state.processingMonths.contains(monthKey);
  }

  /// Clear error state
  void clearError() {
    state = state.copyWith(clearError: true);
  }

  /// Clear last result
  void clearResult() {
    state = state.copyWith(clearResult: true);
  }

  /// Get preview of eligible jokes for current strategy
  Future<List<Joke>> previewEligibleJokes(
    String scheduleId,
    DateTime monthDate,
  ) async {
    final strategyName = _ref.read(selectedAutoFillStrategyProvider);
    final strategy = JokeEligibilityStrategyRegistry.getStrategy(strategyName);

    return await _service.previewEligibleJokes(
      scheduleId: scheduleId,
      monthDate: monthDate,
      strategy: strategy,
    );
  }

  /// Get eligibility statistics for current strategy
  Future<Map<String, int>> getEligibilityStats(String scheduleId) async {
    final strategyName = _ref.read(selectedAutoFillStrategyProvider);
    final strategy = JokeEligibilityStrategyRegistry.getStrategy(strategyName);

    return await _service.getEligibilityStats(
      scheduleId: scheduleId,
      strategy: strategy,
    );
  }
}

// Auto-fill provider
final autoFillProvider = StateNotifierProvider<AutoFillNotifier, AutoFillState>(
  (ref) {
    final service = ref.watch(jokeScheduleAutoFillServiceProvider);
    return AutoFillNotifier(service, ref);
  },
);

// Available strategies provider
final availableStrategiesProvider = Provider<List<String>>((ref) {
  return JokeEligibilityStrategyRegistry.getAllStrategyNames();
});
