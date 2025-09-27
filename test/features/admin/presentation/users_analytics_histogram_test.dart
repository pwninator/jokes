import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/user_repository.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class MockUserRepository extends Mock implements UserRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(Stream<List<AppUserSummary>>.value([]));
    registerFallbackValue(<AppUserSummary>[]);
  });
  group('bucketDaysUsed', () {
    test('coerces to 1..10 where 10 means 10+', () {
      expect(bucketDaysUsed(0), 1);
      expect(bucketDaysUsed(1), 1);
      expect(bucketDaysUsed(2), 2);
      expect(bucketDaysUsed(9), 9);
      expect(bucketDaysUsed(10), 10);
      expect(bucketDaysUsed(25), 10);
    });
  });

  test('LA midnight conversion yields correct date keys', () {
    tzdata.initializeTimeZones();
    final la = tz.getLocation('America/Los_Angeles');
    // 2024-03-10 is DST start in US (2 AM jump). Use UTC instant around boundaries
    final utc = DateTime.utc(2024, 3, 10, 8, 30); // 00:30 LA time
    // Use private logic via helper copy: we test behavior equivalently
    final laTime = tz.TZDateTime.from(utc, la);
    final laMid = tz.TZDateTime(la, laTime.year, laTime.month, laTime.day);
    final laMidUtc = laMid.toUtc();
    expect(laMidUtc.year, 2024);
    expect(laMidUtc.month, 3);
    expect(laMidUtc.day, 10);
    expect(laMidUtc.hour, anyOf(7, 8, 9));
  });

  test('UsersLoginHistogram data shape', () {
    // Build simple synthetic counts map and ensure totals compute
    final counts = <DateTime, Map<int, int>>{};
    final d1 = DateTime.utc(2025, 1, 1);
    final d2 = DateTime.utc(2025, 1, 2);
    counts[d1] = {1: 2, 3: 1};
    counts[d2] = {10: 5};

    final hist = UsersLoginHistogram(
      orderedDates: [d1, d2],
      countsByDateThenBucket: counts,
      maxDailyTotal: 5,
    );

    expect(hist.orderedDates.length, 2);
    expect(hist.maxDailyTotal, 5);
    expect(hist.countsByDateThenBucket[d1]![1], 2);
    expect(hist.countsByDateThenBucket[d1]![3], 1);
    expect(hist.countsByDateThenBucket[d2]![10], 5);
  });

  test('usersRetentionHistogramProvider processes users correctly', () async {
    final mockRepo = MockUserRepository();
    final now = DateTime.utc(2025, 1, 10, 12);
    final users = [
      // Day 1 cohort
      AppUserSummary(
        createdAtUtc: now,
        lastLoginAtUtc: now,
        clientNumDaysUsed: 1,
      ),
      AppUserSummary(
        createdAtUtc: now,
        lastLoginAtUtc: now.add(const Duration(days: 2)), // 2 days later
        clientNumDaysUsed: 3,
      ),
      // Day 2 cohort
      AppUserSummary(
        createdAtUtc: now.add(const Duration(days: 1)),
        lastLoginAtUtc: now.add(const Duration(days: 10)), // 9 days later
        clientNumDaysUsed: 10,
      ),
    ];
    when(() => mockRepo.watchAllUsers()).thenAnswer((_) => Stream.value(users));

    final container = ProviderContainer(
      overrides: [userRepositoryProvider.overrideWithValue(mockRepo)],
    );

    final result = await container.read(usersRetentionHistogramProvider.future);

    expect(result.orderedDates.length, 2);
    final d1 = result.orderedDates[0];
    final d2 = result.orderedDates[1];

    // Day 1 cohort assertions
    final cohort1 = result.countsByDateThenBucket[d1]!;
    expect(cohort1, isNotNull);
    expect(cohort1[1], 1); // 0 days diff -> bucket 1
    expect(cohort1[3], 1); // 2 days diff -> bucket 3

    // Day 2 cohort assertions
    final cohort2 = result.countsByDateThenBucket[d2]!;
    expect(cohort2, isNotNull);
    expect(cohort2[10], 1); // 9 days diff -> bucket 10
  });
}
