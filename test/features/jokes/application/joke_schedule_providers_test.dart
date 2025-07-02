import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';

import '../../../test_helpers/test_helpers.dart';

void main() {
  group('JokeScheduleProviders', () {
    late ProviderContainer container;

    setUp(() {
      TestHelpers.resetAllMocks();
      container = ProviderContainer(
        overrides: JokeScheduleMocks.getJokeScheduleProviderOverrides(),
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('jokeSchedulesProvider', () {
      test('provides schedules from repository', () async {
        // Arrange
        final testSchedules = JokeScheduleMocks.createTestSchedules();
        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              testSchedules: testSchedules,
            ),
          ],
        );

        // Act
        final schedules = await container.read(jokeSchedulesProvider.future);

        // Assert
        expect(schedules, equals(testSchedules));
        expect(schedules.length, equals(3));
      });

      test('handles empty schedules list', () async {
        // Arrange
        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              testSchedules: [],
            ),
          ],
        );

        // Act
        final schedules = await container.read(jokeSchedulesProvider.future);

        // Assert
        expect(schedules, isEmpty);
      });
    });

    group('selectedScheduleProvider', () {
      test('starts with null when no selection', () {
        // Arrange
        container = ProviderContainer(
          overrides: [...JokeScheduleMocks.getJokeScheduleProviderOverrides()],
        );

        // Act & Assert
        expect(container.read(selectedScheduleProvider), isNull);
      });

      test('can be set to specific schedule', () {
        // Arrange
        container = ProviderContainer(
          overrides: [...JokeScheduleMocks.getJokeScheduleProviderOverrides()],
        );

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
        container = ProviderContainer(
          overrides: [...JokeScheduleMocks.getJokeScheduleProviderOverrides()],
        );

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
        // Arrange - no schedule selected
        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              selectedScheduleId: null,
            ),
          ],
        );

        // Act
        final batches = await container.read(scheduleBatchesProvider.future);

        // Assert
        expect(batches, isEmpty);
      });

      test('watches batches for selected schedule', () async {
        // Arrange
        const selectedId = 'test_schedule';
        final testBatches = JokeScheduleMocks.createTestBatches(
          scheduleId: selectedId,
        );

        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              selectedScheduleId: selectedId,
              testBatches: testBatches,
            ),
          ],
        );

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
          JokeScheduleMocks.createTestBatch(scheduleId: firstId),
        ];
        final secondBatches = [
          JokeScheduleMocks.createTestBatch(scheduleId: secondId),
        ];

        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              selectedScheduleId: firstId,
              testBatches: firstBatches,
            ),
          ],
        );

        // Act - get batches for first schedule
        final firstResult = await container.read(
          scheduleBatchesProvider.future,
        );
        expect(firstResult, equals(firstBatches));

        // Change to container with second schedule
        container.dispose();
        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              selectedScheduleId: secondId,
              testBatches: secondBatches,
            ),
          ],
        );

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
        // Arrange - no batches
        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              testBatches: [],
            ),
          ],
        );

        // Act
        final dateRange = container.read(batchDateRangeProvider);

        // Assert
        expect(dateRange, isEmpty);
      });

      test('calculates range from existing batches', () async {
        // Arrange - test with actual loaded batches
        const selectedId = 'test_schedule';
        final testBatches = JokeScheduleMocks.createTestBatches(
          scheduleId: selectedId,
        );

        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              selectedScheduleId: selectedId,
              testBatches: testBatches,
            ),
          ],
        );

        // Act - ensure batches are loaded first, then check date range
        final batches = await container.read(scheduleBatchesProvider.future);
        expect(batches, isNotEmpty); // Verify batches loaded
        
        final dateRange = container.read(batchDateRangeProvider);

        // Assert - should have dates when batches exist
        expect(dateRange, isNotEmpty);
      });

      test('handles loading state', () {
        // Arrange - no selected schedule
        container = ProviderContainer(
          overrides: [
            ...JokeScheduleMocks.getJokeScheduleProviderOverrides(
              selectedScheduleId: null,
            ),
          ],
        );

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
