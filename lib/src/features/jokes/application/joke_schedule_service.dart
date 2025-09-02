import 'dart:math';

import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
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

  /// Unpublish a joke by resetting it to APPROVED state and clearing public_timestamp
  Future<void> unpublishJoke(String jokeId) async {
    await _jokeRepository.resetJokesToApproved([jokeId], JokeState.published);
  }

  /// Add a joke to the next available date in the daily joke schedule
  Future<void> addJokeToNextAvailableDailySchedule(String jokeId) async {
    // 1. Get the joke to verify it's in PUBLISHED state
    final joke = await _jokeRepository.getJokeByIdStream(jokeId).first;
    if (joke == null) {
      throw Exception('Joke with ID "$jokeId" not found');
    }
    if (joke.state != JokeState.published) {
      throw Exception(
        'Joke "$jokeId" must be in PUBLISHED state to add to daily schedule',
      );
    }

    // 2. Load all batches for the daily schedule
    final allBatches = await _scheduleRepository
        .watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId)
        .first;

    // 3. Check for duplicate joke across all batches (past and future)
    for (final batch in allBatches) {
      if (batch.jokes.values.any((j) => j.id == jokeId)) {
        throw Exception(
          'Joke "$jokeId" is already scheduled in batch ${batch.year}-${batch.month.toString().padLeft(2, '0')}',
        );
      }
    }

    // 4. Find next available date starting from today
    final nextDate = await _findNextAvailableDate(allBatches);

    // 5. Get or create batch for the target month
    final targetBatch = await _getOrCreateBatchForDate(
      allBatches,
      nextDate,
      JokeConstants.defaultJokeScheduleId,
    );

    // 6. Add joke to the batch
    final dayKey = nextDate.day.toString().padLeft(2, '0');
    targetBatch.jokes[dayKey] = joke;

    // 7. Save the updated batch
    await _scheduleRepository.updateBatch(targetBatch);

    // 8. Update joke's public timestamp
    tzdata.initializeTimeZones();
    final la = _laLocation ?? tz.getLocation('America/Los_Angeles');
    final laMidnight = tz.TZDateTime(
      la,
      nextDate.year,
      nextDate.month,
      nextDate.day,
    );
    await _jokeRepository.setJokesPublished({jokeId: laMidnight}, true);
  }

  /// Remove a joke from the daily schedule
  Future<void> removeJokeFromDailySchedule(String jokeId) async {
    // 1. Get the joke to verify it's in DAILY state
    final joke = await _jokeRepository.getJokeByIdStream(jokeId).first;
    if (joke == null) {
      throw Exception('Joke with ID "$jokeId" not found');
    }
    if (joke.state != JokeState.daily) {
      throw Exception(
        'Joke "$jokeId" must be in DAILY state to remove from daily schedule',
      );
    }

    // 2. Load all batches for the daily schedule
    final allBatches = await _scheduleRepository
        .watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId)
        .first;

    // 3. Get current date in LA timezone
    tzdata.initializeTimeZones();
    final la = _laLocation ?? tz.getLocation('America/Los_Angeles');
    final now = tz.TZDateTime.now(la);
    final currentMonthStart = tz.TZDateTime(la, now.year, now.month, 1);

    // 4. Find the batch containing this joke (only in current/future months)
    JokeScheduleBatch? targetBatch;
    String? dayKey;
    bool foundInPastBatch = false;

    for (final batch in allBatches) {
      final batchDate = DateTime(batch.year, batch.month);

      // Skip past months
      if (batchDate.isBefore(
        DateTime(currentMonthStart.year, currentMonthStart.month),
      )) {
        // Check if joke exists in past batch (to provide better error message)
        for (final entry in batch.jokes.entries) {
          if (entry.value.id == jokeId) {
            foundInPastBatch = true;
            break;
          }
        }
        continue;
      }

      // Check current/future months
      for (final entry in batch.jokes.entries) {
        if (entry.value.id == jokeId) {
          // Check if this specific day is in the past within the current month
          if (batch.year == now.year && batch.month == now.month) {
            final dayInt = int.parse(entry.key);
            final jokeDate = tz.TZDateTime(la, batch.year, batch.month, dayInt);
            if (jokeDate.isBefore(DateTime(now.year, now.month, now.day))) {
              throw Exception(
                'Cannot remove joke "$jokeId" from past schedule. Joke is scheduled for a date that has already passed (${jokeDate.year}-${jokeDate.month.toString().padLeft(2, '0')}-${jokeDate.day.toString().padLeft(2, '0')}).',
              );
            }
          }

          targetBatch = batch;
          dayKey = entry.key;
          break;
        }
      }
      if (targetBatch != null) break;
    }

    if (foundInPastBatch) {
      throw Exception(
        'Cannot remove joke "$jokeId" from past schedule. Joke is scheduled for a date that has already passed.',
      );
    }

    if (targetBatch == null || dayKey == null) {
      // If joke is in DAILY state but not found in batches, still reset its state
      await _jokeRepository.resetJokesToApproved([jokeId], JokeState.daily);
      return; // Early return since there's nothing to remove from batches
    }

    // 5. Remove joke from the batch
    final updatedJokes = Map<String, Joke>.from(targetBatch.jokes);
    updatedJokes.remove(dayKey);

    final updatedBatch = targetBatch.copyWith(jokes: updatedJokes);

    // 6. Save the updated batch
    await _scheduleRepository.updateBatch(updatedBatch);

    // 7. Reset joke's state to APPROVED
    await _jokeRepository.resetJokesToApproved([jokeId], JokeState.daily);
  }

  /// Find the next available date starting from today
  Future<DateTime> _findNextAvailableDate(
    List<JokeScheduleBatch> allBatches,
  ) async {
    tzdata.initializeTimeZones();
    final la = _laLocation ?? tz.getLocation('America/Los_Angeles');
    final today = tz.TZDateTime.now(la);
    final startDate = DateTime(today.year, today.month, today.day);

    // Sort batches by date for sequential traversal
    final sortedBatches = allBatches.toList()
      ..sort((a, b) {
        final aDate = DateTime(a.year, a.month);
        final bDate = DateTime(b.year, b.month);
        return aDate.compareTo(bDate);
      });

    // Traverse through sorted batches
    for (final batch in sortedBatches) {
      final batchDate = DateTime(batch.year, batch.month);

      // Skip batches that are completely in the past
      if (batchDate.isBefore(DateTime(startDate.year, startDate.month))) {
        continue;
      }

      // Check each day in this batch
      final daysInMonth = DateTime(batch.year, batch.month + 1, 0).day;
      final startDay =
          (batch.year == startDate.year && batch.month == startDate.month)
          ? startDate.day
          : 1;

      for (int day = startDay; day <= daysInMonth; day++) {
        final dayKey = day.toString().padLeft(2, '0');
        if (!batch.jokes.containsKey(dayKey)) {
          return DateTime(batch.year, batch.month, day);
        }
      }
    }

    // If we get here, all existing batches are full
    // Find the last batch and create a date in the next month
    if (sortedBatches.isNotEmpty) {
      final lastBatch = sortedBatches.last;
      // Dart's DateTime constructor automatically handles month overflow
      return DateTime(lastBatch.year, lastBatch.month + 1, 1);
    }

    // No batches exist, start with current month
    return startDate;
  }

  /// Get existing batch for date or create new one
  Future<JokeScheduleBatch> _getOrCreateBatchForDate(
    List<JokeScheduleBatch> allBatches,
    DateTime date,
    String scheduleId,
  ) async {
    final existingBatch = allBatches.firstWhere(
      (batch) => batch.year == date.year && batch.month == date.month,
      orElse: () => JokeScheduleBatch(
        id: JokeScheduleBatch.createBatchId(scheduleId, date.year, date.month),
        scheduleId: scheduleId,
        year: date.year,
        month: date.month,
        jokes: {},
      ),
    );

    return existingBatch;
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
