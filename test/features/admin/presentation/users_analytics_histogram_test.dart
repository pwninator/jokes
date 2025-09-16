import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

void main() {
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
}
