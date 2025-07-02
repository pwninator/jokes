import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

import '../../../../test_helpers/test_helpers.dart';

void main() {
  group('JokeScheduleRepository', () {
    late JokeScheduleRepository repository;

    setUp(() {
      TestHelpers.resetAllMocks();
      repository = JokeScheduleMocks.mockRepository;
    });

    group('watchSchedules', () {
      test('returns stream of schedules', () async {
        // Arrange
        final testSchedules = JokeScheduleMocks.createTestSchedules();
        when(() => repository.watchSchedules())
            .thenAnswer((_) => Stream.value(testSchedules));

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
        when(() => repository.watchSchedules())
            .thenAnswer((_) => Stream.value([]));

        // Act
        final stream = repository.watchSchedules();
        final schedules = await stream.first;

        // Assert
        expect(schedules, isEmpty);
        verify(() => repository.watchSchedules()).called(1);
      });

      test('handles stream errors', () async {
        // Arrange
        when(() => repository.watchSchedules())
            .thenAnswer((_) => Stream.error(Exception('Test error')));

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
        final testBatches = JokeScheduleMocks.createTestBatches(
          scheduleId: scheduleId,
        );
        when(() => repository.watchBatchesForSchedule(scheduleId))
            .thenAnswer((_) => Stream.value(testBatches));

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
        when(() => repository.watchBatchesForSchedule(scheduleId))
            .thenAnswer((_) => Stream.value([]));

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
        when(() => repository.createSchedule(scheduleName))
            .thenAnswer((_) async {});

        // Act
        await repository.createSchedule(scheduleName);

        // Assert
        verify(() => repository.createSchedule(scheduleName)).called(1);
      });

      test('handles creation errors', () async {
        // Arrange
        const scheduleName = 'Error Schedule';
        when(() => repository.createSchedule(scheduleName))
            .thenThrow(Exception('Creation failed'));

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
        final testBatch = JokeScheduleMocks.createTestBatch();
        when(() => repository.updateBatch(testBatch))
            .thenAnswer((_) async {});

        // Act
        await repository.updateBatch(testBatch);

        // Assert
        verify(() => repository.updateBatch(testBatch)).called(1);
      });

      test('handles update errors', () async {
        // Arrange
        final testBatch = JokeScheduleMocks.createTestBatch();
        when(() => repository.updateBatch(testBatch))
            .thenThrow(Exception('Update failed'));

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
        when(() => repository.deleteBatch(batchId))
            .thenAnswer((_) async {});

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
        when(() => repository.deleteSchedule(scheduleId))
            .thenAnswer((_) async {});

        // Act
        await repository.deleteSchedule(scheduleId);

        // Assert
        verify(() => repository.deleteSchedule(scheduleId)).called(1);
      });

      test('handles deletion errors', () async {
        // Arrange
        const scheduleId = 'error_schedule';
        when(() => repository.deleteSchedule(scheduleId))
            .thenThrow(Exception('Deletion failed'));

        // Act & Assert
        expect(
          () => repository.deleteSchedule(scheduleId),
          throwsA(isA<Exception>()),
        );
      });
    });
  });
} 