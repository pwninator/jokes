import 'dart:math';

import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

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
  final tz.Location? _laLocation; // injected for testing/timezone

  const JokeScheduleAutoFillService({
    required JokeRepository jokeRepository,
    required JokeScheduleRepository scheduleRepository,
    tz.Location? laLocation,
  }) : _jokeRepository = jokeRepository,
       _scheduleRepository = scheduleRepository,
       _laLocation = laLocation;

  /// Publish a joke immediately with current date in Los Angeles time
  Future<void> publishJokeImmediately(String jokeId) async {
    // Ensure timezone database is initialized when used outside app startup
    tzdata.initializeTimeZones();
    final la = _laLocation ?? tz.getLocation('America/Los_Angeles');

    // Get the start of today in LA time
    final now = tz.TZDateTime.now(la);
    final startOfToday = tz.TZDateTime(la, now.year, now.month, now.day);

    // Publish the joke (not as a daily joke)
    await _jokeRepository.setJokesPublished({jokeId: startOfToday}, false);
  }

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
      final candidate = shuffledJokes[jokeIndex];
      // Validate candidate state is APPROVED
      if (candidate.state != JokeState.approved) {
        return AutoFillResult.error(
          error: 'Joke "${candidate.id}" must be APPROVED before scheduling',
          strategyUsed: strategy.name,
        );
      }
      assignments[dayKey] = candidate;
      jokeIndex++;
    }

    // Check if we couldn't fill all days
    final unfilledDays = daysInMonth - assignments.length;
    if (unfilledDays > 0) {
      warnings.add(
        'Could not fill $unfilledDays days due to insufficient eligible jokes',
      );
    }

    // Compute LA start-of-day timestamps and publish jokes
    final publishMap = <String, DateTime>{};
    // Ensure timezone database is initialized when used outside app startup
    tzdata.initializeTimeZones();
    final la = _laLocation ?? tz.getLocation('America/Los_Angeles');
    assignments.forEach((dayKey, joke) {
      final dayInt = int.parse(dayKey);
      final laMidnight = tz.TZDateTime(
        la,
        monthDate.year,
        monthDate.month,
        dayInt,
      );
      publishMap[joke.id] = laMidnight;
    });
    await _jokeRepository.setJokesPublished(publishMap, true);

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
}
