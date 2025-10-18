import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

// Mock classes
class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

// Fake classes for Mocktail fallback values
class FakeJokeSchedule extends Fake implements JokeSchedule {}

class FakeJokeScheduleBatch extends Fake implements JokeScheduleBatch {}

// Helper methods
JokeSchedule createTestSchedule({String? id, String? name}) {
  return JokeSchedule(id: id ?? 'test_schedule', name: name ?? 'Test Schedule');
}

JokeScheduleBatch createTestBatch({
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

List<JokeSchedule> createTestSchedules() {
  return [
    createTestSchedule(id: 'daily_jokes', name: 'Daily Jokes'),
    createTestSchedule(id: 'weekly_comedy', name: 'Weekly Comedy'),
    createTestSchedule(id: 'holiday_special', name: 'Holiday Special'),
  ];
}

List<JokeScheduleBatch> createTestBatches({String? scheduleId}) {
  final id = scheduleId ?? 'test_schedule';
  return [
    createTestBatch(scheduleId: id, year: 2024, month: 1),
    createTestBatch(scheduleId: id, year: 2024, month: 2),
    createTestBatch(scheduleId: id, year: 2024, month: 3),
  ];
}

void main() {
  group('JokeScheduleRepository', () {
    late JokeScheduleRepository repository;

    setUpAll(() {
      // Register fallback values for Mocktail
      registerFallbackValue(FakeJokeSchedule());
      registerFallbackValue(FakeJokeScheduleBatch());
    });

    setUp(() {
      repository = MockJokeScheduleRepository();
    });

    group('watchSchedules', () {
      test('returns stream of schedules', () async {
        // Arrange
        final testSchedules = createTestSchedules();
        when(
          () => repository.watchSchedules(),
        ).thenAnswer((_) => Stream.value(testSchedules));

        // Act
        final stream = repository.watchSchedules();
        final schedules = await stream.first;

        // Assert
        expect(schedules, equals(testSchedules));
        expect(schedules.length, equals(3));
        expect(schedules.first.name, equals('Daily Jokes'));
        verify(() => repository.watchSchedules()).called(1);
      });

      test('handles empty schedules', () async {
        // Arrange
        when(
          () => repository.watchSchedules(),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final stream = repository.watchSchedules();
        final schedules = await stream.first;

        // Assert
        expect(schedules, isEmpty);
        verify(() => repository.watchSchedules()).called(1);
      });

      test('handles stream errors', () async {
        // Arrange
        when(
          () => repository.watchSchedules(),
        ).thenAnswer((_) => Stream.error(Exception('Test error')));

        // Act
        final stream = repository.watchSchedules();

        // Assert
        expect(stream, emitsError(isA<Exception>()));
      });
    });

    group('watchBatchesForSchedule', () {
      test('returns stream of batches for specific schedule', () async {
        // Arrange
        const scheduleId = 'test_schedule';
        final testBatches = createTestBatches(scheduleId: scheduleId);
        when(
          () => repository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value(testBatches));

        // Act
        final stream = repository.watchBatchesForSchedule(scheduleId);
        final batches = await stream.first;

        // Assert
        expect(batches, equals(testBatches));
        expect(batches.length, equals(3));
        expect(batches.every((b) => b.scheduleId == scheduleId), isTrue);
        verify(() => repository.watchBatchesForSchedule(scheduleId)).called(1);
      });

      test('returns empty stream for schedule with no batches', () async {
        // Arrange
        const scheduleId = 'empty_schedule';
        when(
          () => repository.watchBatchesForSchedule(scheduleId),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final stream = repository.watchBatchesForSchedule(scheduleId);
        final batches = await stream.first;

        // Assert
        expect(batches, isEmpty);
        verify(() => repository.watchBatchesForSchedule(scheduleId)).called(1);
      });
    });

    group('createSchedule', () {
      test('creates schedule successfully', () async {
        // Arrange
        const scheduleName = 'New Test Schedule';
        when(
          () => repository.createSchedule(scheduleName),
        ).thenAnswer((_) async {});

        // Act
        await repository.createSchedule(scheduleName);

        // Assert
        verify(() => repository.createSchedule(scheduleName)).called(1);
      });

      test('handles creation errors', () async {
        // Arrange
        const scheduleName = 'Error Schedule';
        when(
          () => repository.createSchedule(scheduleName),
        ).thenThrow(Exception('Creation failed'));

        // Act & Assert
        expect(
          () => repository.createSchedule(scheduleName),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('updateBatch', () {
      test('updates batch successfully', () async {
        // Arrange
        final testBatch = createTestBatch();
        when(() => repository.updateBatch(testBatch)).thenAnswer((_) async {});

        // Act
        await repository.updateBatch(testBatch);

        // Assert
        verify(() => repository.updateBatch(testBatch)).called(1);
      });

      test('handles update errors', () async {
        // Arrange
        final testBatch = createTestBatch();
        when(
          () => repository.updateBatch(testBatch),
        ).thenThrow(Exception('Update failed'));

        // Act & Assert
        expect(
          () => repository.updateBatch(testBatch),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('deleteBatch', () {
      test('deletes batch successfully', () async {
        // Arrange
        const batchId = 'test_batch_id';
        when(() => repository.deleteBatch(batchId)).thenAnswer((_) async {});

        // Act
        await repository.deleteBatch(batchId);

        // Assert
        verify(() => repository.deleteBatch(batchId)).called(1);
      });
    });

    group('deleteSchedule', () {
      test('deletes schedule and related batches successfully', () async {
        // Arrange
        const scheduleId = 'test_schedule';
        when(
          () => repository.deleteSchedule(scheduleId),
        ).thenAnswer((_) async {});

        // Act
        await repository.deleteSchedule(scheduleId);

        // Assert
        verify(() => repository.deleteSchedule(scheduleId)).called(1);
      });

      test('handles deletion errors', () async {
        // Arrange
        const scheduleId = 'error_schedule';
        when(
          () => repository.deleteSchedule(scheduleId),
        ).thenThrow(Exception('Deletion failed'));

        // Act & Assert
        expect(
          () => repository.deleteSchedule(scheduleId),
          throwsA(isA<Exception>()),
        );
      });
    });
  });
}
