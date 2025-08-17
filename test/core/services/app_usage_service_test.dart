import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';

void main() {
  String todayString() {
    final now = DateTime.now();
    final year = now.year.toString();
    final month = now.month.toString().padLeft(2, '0');
    final day = now.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  group('AppUsageService.logAppUsage', () {
    test(
      'first run initializes dates and increments unique day count',
      () async {
        final prefs = await SharedPreferences.getInstance();
        final service = AppUsageService(prefs: prefs);

        await service.logAppUsage();

        expect(await service.getFirstUsedDate(), todayString());
        expect(await service.getLastUsedDate(), todayString());
        expect(await service.getNumDaysUsed(), 1);
      },
    );

    test('same day run does not increment unique day count', () async {
      final prefs = await SharedPreferences.getInstance();
      final service = AppUsageService(prefs: prefs);

      await service.logAppUsage();
      await service.logAppUsage();

      expect(await service.getNumDaysUsed(), 1);
      expect(await service.getLastUsedDate(), todayString());
    });

    test(
      'new day increments unique day count and updates last_used_date',
      () async {
        final prefs = await SharedPreferences.getInstance();
        final service = AppUsageService(prefs: prefs);

        await service.logAppUsage();
        expect(await service.getNumDaysUsed(), 1);

        // Simulate that the last used date was yesterday
        final yesterday = DateTime.now().subtract(const Duration(days: 1));
        final yesterdayStr =
            '${yesterday.year.toString()}-${yesterday.month.toString().padLeft(2, '0')}-${yesterday.day.toString().padLeft(2, '0')}';
        await prefs.setString('last_used_date', yesterdayStr);

        await service.logAppUsage();

        expect(await service.getNumDaysUsed(), 2);
        expect(await service.getLastUsedDate(), todayString());
      },
    );
  });

  group('AppUsageService.logJokeViewed', () {
    test('increments num_jokes_viewed counter', () async {
      final prefs = await SharedPreferences.getInstance();
      final service = AppUsageService(prefs: prefs);

      expect(await service.getNumJokesViewed(), 0);
      await service.logJokeViewed();
      expect(await service.getNumJokesViewed(), 1);
      await service.logJokeViewed();
      expect(await service.getNumJokesViewed(), 2);
    });
  });

  group('AppUsageService saved/shared counters', () {
    test(
      'incrementSavedJokesCount and decrementSavedJokesCount update counter with floor at 0',
      () async {
        final prefs = await SharedPreferences.getInstance();
        final service = AppUsageService(prefs: prefs);

        expect(await service.getNumSavedJokes(), 0);
        await service.incrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 1);
        await service.incrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 2);
        await service.decrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 1);
        await service.decrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 0);
        // floor at 0
        await service.decrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 0);
      },
    );

    test('incrementSharedJokesCount updates counter', () async {
      final prefs = await SharedPreferences.getInstance();
      final service = AppUsageService(prefs: prefs);

      expect(await service.getNumSharedJokes(), 0);
      await service.incrementSharedJokesCount();
      expect(await service.getNumSharedJokes(), 1);
      await service.incrementSharedJokesCount();
      expect(await service.getNumSharedJokes(), 2);
    });
  });
}
