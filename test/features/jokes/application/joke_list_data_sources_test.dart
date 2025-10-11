import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';

void main() {
  group('Daily Jokes Stale Data Detection', () {
    test('getCurrentDate returns normalized date', () {
      final date = getCurrentDate();
      final now = DateTime.now();
      final expected = DateTime(now.year, now.month, now.day);

      expect(date, expected);
    });

    test('dailyJokesCheckNowProvider starts at 0', () {
      final container = ProviderContainer();

      final initialValue = container.read(dailyJokesCheckNowProvider);
      expect(initialValue, 0);

      container.dispose();
    });

    test('dailyJokesCheckNowProvider can be incremented', () {
      final container = ProviderContainer();

      final initialValue = container.read(dailyJokesCheckNowProvider);
      container.read(dailyJokesCheckNowProvider.notifier).state++;
      final newValue = container.read(dailyJokesCheckNowProvider);

      expect(newValue, initialValue + 1);

      container.dispose();
    });

    test('dailyJokesLastResetDateProvider starts as null', () {
      final container = ProviderContainer();

      final initialValue = container.read(dailyJokesLastResetDateProvider);
      expect(initialValue, null);

      container.dispose();
    });

    test('dailyJokesLastResetDateProvider can store date', () {
      final container = ProviderContainer();

      final today = getCurrentDate();
      container.read(dailyJokesLastResetDateProvider.notifier).state = today;
      final storedDate = container.read(dailyJokesLastResetDateProvider);

      expect(storedDate, today);

      container.dispose();
    });
  });
}
