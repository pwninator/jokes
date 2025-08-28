import 'dart:math';

import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';

/// Result of an auto-fill operation
class AutoFillResult {
  final bool success;
  final int jokesFilled;
  final int totalDays;
  final String strategyUsed;
  final String? error;
  final List<String> warnings;

  const AutoFillResult({
    required this.success,
    required this.jokesFilled,
    required this.totalDays,
    required this.strategyUsed,
    this.error,
    this.warnings = const [],
  });

  /// Success result
  factory AutoFillResult.success({
    required int jokesFilled,
    required int totalDays,
    required String strategyUsed,
    List<String> warnings = const [],
  }) {
    return AutoFillResult(
      success: true,
      jokesFilled: jokesFilled,
      totalDays: totalDays,
      strategyUsed: strategyUsed,
      warnings: warnings,
    );
  }

  /// Error result
  factory AutoFillResult.error({
    required String error,
    required String strategyUsed,
  }) {
    return AutoFillResult(
      success: false,
      jokesFilled: 0,
      totalDays: 0,
      strategyUsed: strategyUsed,
      error: error,
    );
  }

  /// Get completion percentage
  double get completionPercentage {
    if (totalDays == 0) return 0.0;
    return (jokesFilled / totalDays) * 100;
  }

  /// Get summary message
  String get summaryMessage {
    if (!success) {
      return error ?? 'Auto-fill failed';
    }

    if (jokesFilled == totalDays) {
      return 'Successfully filled all $totalDays days';
    } else if (jokesFilled > 0) {
      return 'Filled $jokesFilled of $totalDays days (${completionPercentage.toStringAsFixed(1)}%)';
    } else {
      return 'No eligible jokes found';
    }
  }
}

/// Service for auto-filling joke schedules with eligible jokes
class JokeScheduleAutoFillService {
  final JokeRepository _jokeRepository;
  final JokeScheduleRepository _scheduleRepository;

  const JokeScheduleAutoFillService({
    required JokeRepository jokeRepository,
    required JokeScheduleRepository scheduleRepository,
  }) : _jokeRepository = jokeRepository,
       _scheduleRepository = scheduleRepository;

  /// Auto-fill a month with jokes using the specified strategy
  Future<AutoFillResult> autoFillMonth({
    required String scheduleId,
    required DateTime monthDate,
    required JokeEligibilityStrategy strategy,
    bool replaceExisting = false,
  }) async {
    try {
      // 1. Get all jokes
      final allJokes = await _jokeRepository.getJokes().first;

      if (allJokes.isEmpty) {
        return AutoFillResult.error(
          error: 'No jokes available in the system',
          strategyUsed: strategy.name,
        );
      }

      // 2. Get existing batches for context
      final existingBatches = await _scheduleRepository
          .watchBatchesForSchedule(scheduleId)
          .first;

      // 3. Create eligibility context
      final context = EligibilityContext(
        scheduleId: scheduleId,
        existingBatches: existingBatches,
        targetMonth: monthDate,
      );

      // 4. Apply strategy to get eligible jokes
      final eligibleJokes = await strategy.getEligibleJokes(allJokes, context);

      if (eligibleJokes.isEmpty) {
        return AutoFillResult.error(
          error:
              'No jokes meet the eligibility criteria for "${strategy.description}"',
          strategyUsed: strategy.name,
        );
      }

      // 5. Execute the auto-fill
      return await _executeAutoFill(
        eligibleJokes: eligibleJokes,
        scheduleId: scheduleId,
        monthDate: monthDate,
        context: context,
        strategy: strategy,
        replaceExisting: replaceExisting,
      );
    } catch (e) {
      return AutoFillResult.error(
        error: 'Auto-fill failed: $e',
        strategyUsed: strategy.name,
      );
    }
  }

  /// Execute the core auto-fill logic (strategy-independent)
  Future<AutoFillResult> _executeAutoFill({
    required List<Joke> eligibleJokes,
    required String scheduleId,
    required DateTime monthDate,
    required EligibilityContext context,
    required JokeEligibilityStrategy strategy,
    required bool replaceExisting,
  }) async {
    final warnings = <String>[];

    // Get existing batch for this month
    final batchId = JokeScheduleBatch.createBatchId(
      scheduleId,
      monthDate.year,
      monthDate.month,
    );

    final existingBatch = context.existingBatches
        .where((batch) => batch.id == batchId)
        .firstOrNull;

    // Start with existing jokes if we're not replacing
    final assignments = <String, Joke>{};
    if (!replaceExisting && existingBatch != null) {
      assignments.addAll(existingBatch.jokes);
    }

    // Randomize eligible jokes for fair distribution
    final shuffledJokes = List<Joke>.from(eligibleJokes);
    shuffledJokes.shuffle(Random());

    // Get days in month
    final daysInMonth = DateTime(monthDate.year, monthDate.month + 1, 0).day;

    // Fill empty days in ascending date order
    int jokeIndex = 0;

    for (
      int day = 1;
      day <= daysInMonth && jokeIndex < shuffledJokes.length;
      day++
    ) {
      final dayKey = day.toString().padLeft(2, '0');

      // Skip if day already has a joke and we're not replacing
      if (!replaceExisting && assignments.containsKey(dayKey)) {
        continue;
      }

      // Assign joke to this day
      assignments[dayKey] = shuffledJokes[jokeIndex];
      jokeIndex++;
    }

    // Check if we couldn't fill all days
    final unfilledDays = daysInMonth - assignments.length;
    if (unfilledDays > 0) {
      warnings.add(
        'Could not fill $unfilledDays days due to insufficient eligible jokes',
      );
    }

    // Create/update batch
    final batch = JokeScheduleBatch(
      id: batchId,
      scheduleId: scheduleId,
      year: monthDate.year,
      month: monthDate.month,
      jokes: assignments,
    );

    await _scheduleRepository.updateBatch(batch);

    return AutoFillResult.success(
      jokesFilled: assignments.length,
      totalDays: daysInMonth,
      strategyUsed: strategy.name,
      warnings: warnings,
    );
  }

  /// Preview what jokes would be selected without actually scheduling them
  Future<List<Joke>> previewEligibleJokes({
    required String scheduleId,
    required DateTime monthDate,
    required JokeEligibilityStrategy strategy,
  }) async {
    try {
      // Get all jokes
      final allJokes = await _jokeRepository.getJokes().first;

      // Get existing batches for context
      final existingBatches = await _scheduleRepository
          .watchBatchesForSchedule(scheduleId)
          .first;

      // Create eligibility context
      final context = EligibilityContext(
        scheduleId: scheduleId,
        existingBatches: existingBatches,
        targetMonth: monthDate,
      );

      // Apply strategy
      return await strategy.getEligibleJokes(allJokes, context);
    } catch (e) {
      return [];
    }
  }

  /// Get statistics about available jokes for a strategy
  Future<Map<String, int>> getEligibilityStats({
    required String scheduleId,
    required JokeEligibilityStrategy strategy,
  }) async {
    try {
      // Get all jokes
      final allJokes = await _jokeRepository.getJokes().first;

      // Get existing batches
      final existingBatches = await _scheduleRepository
          .watchBatchesForSchedule(scheduleId)
          .first;

      // Create dummy context for current month
      final context = EligibilityContext(
        scheduleId: scheduleId,
        existingBatches: existingBatches,
        targetMonth: DateTime.now(),
      );

      // Apply strategy
      final eligibleJokes = await strategy.getEligibleJokes(allJokes, context);

      return {
        'total_jokes': allJokes.length,
        'eligible_jokes': eligibleJokes.length,
        'already_scheduled': allJokes.length - eligibleJokes.length,
      };
    } catch (e) {
      return {'total_jokes': 0, 'eligible_jokes': 0, 'already_scheduled': 0};
    }
  }
}
