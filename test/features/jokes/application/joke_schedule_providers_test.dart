import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
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

/// Helper functions for creating test data
class TestDataHelpers {
  static JokeSchedule createTestSchedule({String? id, String? name}) {
    return JokeSchedule(
      id: id ?? 'test_schedule',
      name: name ?? 'Test Schedule',
    );
  }

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

  static List<JokeSchedule> createTestSchedules() {
    return [
      createTestSchedule(id: 'daily_jokes', name: 'Daily Jokes'),
      createTestSchedule(id: 'weekly_comedy', name: 'Weekly Comedy'),
      createTestSchedule(id: 'holiday_special', name: 'Holiday Special'),
    ];
  }

  static List<JokeScheduleBatch> createTestBatches({String? scheduleId}) {
    final id = scheduleId ?? 'test_schedule';
    return [
      createTestBatch(scheduleId: id, year: 2024, month: 1),
      createTestBatch(scheduleId: id, year: 2024, month: 2),
      createTestBatch(scheduleId: id, year: 2024, month: 3),
    ];
  }
}

void main() {
  group('JokeScheduleProviders', () {
    late ProviderContainer container;
    late MockJokeScheduleRepository mockRepository;

    setUpAll(() {
      registerFallbackValue(FakeJokeSchedule());
      registerFallbackValue(FakeJokeScheduleBatch());
    });

    setUp(() {
      mockRepository = MockJokeScheduleRepository();

      // Setup default repository behaviors
      when(
        () => mockRepository.watchSchedules(),
      ).thenAnswer((_) => Stream.value([TestDataHelpers.createTestSchedule()]));
      when(
        () => mockRepository.watchBatchesForSchedule(any()),
      ).thenAnswer((_) => Stream.value([TestDataHelpers.createTestBatch()]));
      when(() => mockRepository.createSchedule(any())).thenAnswer((_) async {});
      when(() => mockRepository.updateBatch(any())).thenAnswer((_) async {});
      when(() => mockRepository.deleteBatch(any())).thenAnswer((_) async {});
      when(() => mockRepository.deleteSchedule(any())).thenAnswer((_) async {});

      container = ProviderContainer(
        overrides: [
          jokeScheduleRepositoryProvider.overrideWithValue(mockRepository),
          // Mock schedules provider to return empty list to prevent auto-selection
          jokeSchedulesProvider.overrideWith((ref) => Stream.value([])),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('jokeSchedulesProvider', () {
      test('provides schedules from repository', () async {
        // Arrange
        final testSchedules = TestDataHelpers.createTestSchedules();
        when(
          () => mockRepository.watchSchedules(),
        ).thenAnswer((_) => Stream.value(testSchedules));

        // Act
        final schedules = await container.read(jokeSchedulesProvider.future);

        // Assert
        expect(schedules, equals(testSchedules));
        expect(schedules.length, equals(3));
      });

      test('handles empty schedules list', () async {
        // Arrange
        when(
          () => mockRepository.watchSchedules(),
        ).thenAnswer((_) => Stream.value([]));

        // Act
        final schedules = await container.read(jokeSchedulesProvider.future);

        // Assert
        expect(schedules, isEmpty);
      });
    });

    group('selectedScheduleProvider', () {
      test('starts with null when no selection', () {
        // Act & Assert
        expect(container.read(selectedScheduleProvider), isNull);
      });

      test('can be set to specific schedule', () {
        // Act
        container.read(selectedScheduleProvider.notifier).state =
            'test_schedule';

        // Assert
        expect(
          container.read(selectedScheduleProvider),
          equals('test_schedule'),
        );
      });

      test('can be cleared', () {
        // Arrange
        container.read(selectedScheduleProvider.notifier).state =
            'test_schedule';
        expect(
          container.read(selectedScheduleProvider),
          equals('test_schedule'),
        );

        // Act
        container.read(selectedScheduleProvider.notifier).state = null;

        // Assert
        expect(container.read(selectedScheduleProvider), isNull);
      });
    });

    group('scheduleBatchesProvider', () {
      test('returns empty when no schedule selected', () async {
        // Arrange - ensure no schedule is selected
        // The scheduleBatchesProvider should return Stream.value([]) when selectedScheduleId is null

        // Act - use the future to wait for the stream to emit
        final batches = await container.read(scheduleBatchesProvider.future);

        // Assert - should return empty list when no schedule selected
        expect(batches, isEmpty);
      });

      test('watches batches for selected schedule', () async {
        // Arrange
        const selectedId = 'test_schedule';
        final testBatches = TestDataHelpers.createTestBatches(
          scheduleId: selectedId,
        );

        // Set selected schedule
        container.read(selectedScheduleProvider.notifier).state = selectedId;

        // Mock repository to return test batches
        when(
          () => mockRepository.watchBatchesForSchedule(selectedId),
        ).thenAnswer((_) => Stream.value(testBatches));

        // Act
        final batches = await container.read(scheduleBatchesProvider.future);

        // Assert
        expect(batches, equals(testBatches));
        expect(batches.every((b) => b.scheduleId == selectedId), isTrue);
      });

      test('switches batches when selected schedule changes', () async {
        // Arrange - start with first schedule
        const firstId = 'first_schedule';
        const secondId = 'second_schedule';

        final firstBatches = [
          TestDataHelpers.createTestBatch(scheduleId: firstId),
        ];
        final secondBatches = [
          TestDataHelpers.createTestBatch(scheduleId: secondId),
        ];

        // Set first schedule and mock its batches
        container.read(selectedScheduleProvider.notifier).state = firstId;
        when(
          () => mockRepository.watchBatchesForSchedule(firstId),
        ).thenAnswer((_) => Stream.value(firstBatches));

        // Act - get batches for first schedule
        final firstResult = await container.read(
          scheduleBatchesProvider.future,
        );
        expect(firstResult, equals(firstBatches));

        // Change to second schedule and mock its batches
        container.read(selectedScheduleProvider.notifier).state = secondId;
        when(
          () => mockRepository.watchBatchesForSchedule(secondId),
        ).thenAnswer((_) => Stream.value(secondBatches));

        // Get batches for second schedule
        final secondResult = await container.read(
          scheduleBatchesProvider.future,
        );

        // Assert
        expect(secondResult, equals(secondBatches));
      });
    });

    group('batchDateRangeProvider', () {
      test('returns empty when no batches available', () {
        // Act
        final dateRange = container.read(batchDateRangeProvider);

        // Assert
        expect(dateRange, isEmpty);
      });

      test('calculates range from existing batches', () async {
        // Arrange - test with actual loaded batches
        const selectedId = 'test_schedule';
        final testBatches = TestDataHelpers.createTestBatches(
          scheduleId: selectedId,
        );

        // Set selected schedule and mock batches
        container.read(selectedScheduleProvider.notifier).state = selectedId;
        when(
          () => mockRepository.watchBatchesForSchedule(selectedId),
        ).thenAnswer((_) => Stream.value(testBatches));

        // Act - ensure batches are loaded first, then check date range
        final batches = await container.read(scheduleBatchesProvider.future);
        expect(batches, isNotEmpty); // Verify batches loaded

        final dateRange = container.read(batchDateRangeProvider);

        // Assert - should have dates when batches exist
        expect(dateRange, isNotEmpty);
      });

      test('handles loading state', () {
        // Act
        final dateRange = container.read(batchDateRangeProvider);

        // Assert - should have empty value when no schedule selected
        expect(dateRange, isEmpty);
      });
    });

    group('UI state providers', () {
      test('newScheduleDialogProvider manages dialog state', () {
        // Arrange - initial state
        expect(container.read(newScheduleDialogProvider), isFalse);

        // Act - show dialog
        container.read(newScheduleDialogProvider.notifier).state = true;

        // Assert
        expect(container.read(newScheduleDialogProvider), isTrue);

        // Act - hide dialog
        container.read(newScheduleDialogProvider.notifier).state = false;

        // Assert
        expect(container.read(newScheduleDialogProvider), isFalse);
      });

      test('newScheduleNameProvider manages input state', () {
        // Arrange - initial state
        expect(container.read(newScheduleNameProvider), equals(''));

        // Act - set name
        container.read(newScheduleNameProvider.notifier).state =
            'Test Schedule';

        // Assert
        expect(
          container.read(newScheduleNameProvider),
          equals('Test Schedule'),
        );
      });

      test('loading state providers manage async operation states', () {
        // Test schedule creation loading
        expect(container.read(scheduleCreationLoadingProvider), isFalse);
        container.read(scheduleCreationLoadingProvider.notifier).state = true;
        expect(container.read(scheduleCreationLoadingProvider), isTrue);

        // Test batch update loading
        expect(container.read(batchUpdateLoadingProvider), isEmpty);
        container.read(batchUpdateLoadingProvider.notifier).state = {'batch1'};
        expect(container.read(batchUpdateLoadingProvider), equals({'batch1'}));
      });
    });
  });
}
