import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

abstract class JokeScheduleRepository {
  /// Stream of all joke schedules
  Stream<List<JokeSchedule>> watchSchedules();

  /// Stream of all batches for a specific schedule
  Stream<List<JokeScheduleBatch>> watchBatchesForSchedule(String scheduleId);

  /// Create a new joke schedule
  Future<void> createSchedule(String name);

  /// Update or create a joke schedule batch
  Future<void> updateBatch(JokeScheduleBatch batch);

  /// Delete a joke schedule batch
  Future<void> deleteBatch(String batchId);

  /// Delete a joke schedule and all its batches
  Future<void> deleteSchedule(String scheduleId);
} 