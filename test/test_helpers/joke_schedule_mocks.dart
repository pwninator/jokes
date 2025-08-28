import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

// Mock classes for joke scheduling
class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

// Fake classes for Mocktail fallback values
class FakeJokeSchedule extends Fake implements JokeSchedule {}

class FakeJokeScheduleBatch extends Fake implements JokeScheduleBatch {}

/// Joke scheduler-specific mocks for unit tests
class JokeScheduleMocks {
  static MockJokeScheduleRepository? _mockRepository;

  /// Get or create mock joke schedule repository
  static MockJokeScheduleRepository get mockRepository {
    _mockRepository ??= MockJokeScheduleRepository();
    _setupFallbackValues();
    _setupRepositoryDefaults(_mockRepository!);
    return _mockRepository!;
  }

  /// Reset all joke schedule mocks (call this in setUp if needed)
  static void reset() {
    _mockRepository = null;
  }

  /// Get joke scheduler provider overrides
  static List<Override> getJokeScheduleProviderOverrides({
    List<JokeSchedule>? testSchedules,
    List<JokeScheduleBatch>? testBatches,
    String? selectedScheduleId,
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock repository
      jokeScheduleRepositoryProvider.overrideWithValue(mockRepository),

      // Mock schedules stream
      if (testSchedules != null)
        jokeSchedulesProvider.overrideWith(
          (ref) => Stream.value(testSchedules),
        ),

      // Mock selected schedule - always override to avoid auto-selection logic
      selectedScheduleProvider.overrideWith((ref) => selectedScheduleId),

      // Mock batches stream
      if (testBatches != null)
        scheduleBatchesProvider.overrideWith(
          (ref) => Stream.value(testBatches),
        ),

      // Add any additional overrides
      ...additionalOverrides,
    ];
  }

  /// Create test schedule
  static JokeSchedule createTestSchedule({String? id, String? name}) {
    return JokeSchedule(
      id: id ?? 'test_schedule',
      name: name ?? 'Test Schedule',
    );
  }

  /// Create test batch
  static JokeScheduleBatch createTestBatch({
    String? scheduleId,
    int? year,
    int? month,
    Map<String, Joke>? jokes,
  }) {
    final testScheduleId = scheduleId ?? 'test_schedule';
    final testYear = year ?? 2024;
    final testMonth = month ?? 1;

    return JokeScheduleBatch(
      id: JokeScheduleBatch.createBatchId(testScheduleId, testYear, testMonth),
      scheduleId: testScheduleId,
      year: testYear,
      month: testMonth,
      jokes: jokes ?? {},
    );
  }

  /// Create multiple test schedules
  static List<JokeSchedule> createTestSchedules() {
    return [
      createTestSchedule(id: 'daily_jokes', name: 'Daily Jokes'),
      createTestSchedule(id: 'weekly_comedy', name: 'Weekly Comedy'),
      createTestSchedule(id: 'holiday_special', name: 'Holiday Special'),
    ];
  }

  /// Create multiple test batches
  static List<JokeScheduleBatch> createTestBatches({String? scheduleId}) {
    final id = scheduleId ?? 'test_schedule';
    return [
      createTestBatch(scheduleId: id, year: 2024, month: 1),
      createTestBatch(scheduleId: id, year: 2024, month: 2),
      createTestBatch(scheduleId: id, year: 2024, month: 3),
    ];
  }

  static void _setupFallbackValues() {
    // Register fallback values for Mocktail
    registerFallbackValue(FakeJokeSchedule());
    registerFallbackValue(FakeJokeScheduleBatch());
  }

  static void _setupRepositoryDefaults(MockJokeScheduleRepository mock) {
    // Setup default behaviors that won't throw
    when(
      () => mock.watchSchedules(),
    ).thenAnswer((_) => Stream.value([createTestSchedule()]));

    when(
      () => mock.watchBatchesForSchedule(any()),
    ).thenAnswer((_) => Stream.value([createTestBatch()]));

    when(() => mock.createSchedule(any())).thenAnswer((_) async {});

    when(() => mock.updateBatch(any())).thenAnswer((_) async {});

    when(() => mock.deleteBatch(any())).thenAnswer((_) async {});

    when(() => mock.deleteSchedule(any())).thenAnswer((_) async {});
  }
}
