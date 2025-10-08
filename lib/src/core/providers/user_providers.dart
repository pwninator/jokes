import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/core/data/repositories/user_repository.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// Repository provider
final userRepositoryProvider = Provider<UserRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return FirestoreUserRepository(firestore: firestore);
});

/// Shared provider to fetch all users once
final allUsersProvider = StreamProvider<List<AppUserSummary>>((ref) {
  return ref.watch(userRepositoryProvider).watchAllUsers();
});

/// Bucket for 1..10 where 10 == 10+
int bucketDaysUsed(int value) {
  if (value <= 1) return 1;
  if (value >= 10) return 10;
  return value;
}

/// Histogram data model for chart
class UsersLoginHistogram {
  final List<DateTime>
  orderedDates; // LA-local date at 00:00 converted to UTC DateTime for stability
  final Map<DateTime, Map<int, int>> countsByDateThenBucket; // bucket: 1..10
  final int maxDailyTotal;

  const UsersLoginHistogram({
    required this.orderedDates,
    required this.countsByDateThenBucket,
    required this.maxDailyTotal,
  });
}

DateTime _laMidnight(DateTime utcInstant, tz.Location la) {
  // Ensure utcInstant is UTC
  final baseUtc = utcInstant.isUtc ? utcInstant : utcInstant.toUtc();
  final laTime = tz.TZDateTime.from(baseUtc, la);
  final laMid = tz.TZDateTime(la, laTime.year, laTime.month, laTime.day);
  // Store as UTC DateTime to use as map key consistently
  return laMid.toUtc();
}

/// Transformation provider: builds daily histogram across all time in LA timezone
final usersLoginHistogramProvider = StreamProvider<UsersLoginHistogram>((ref) {
  // Initialize timezone database lazily
  tzdata.initializeTimeZones();
  final la = tz.getLocation('America/Los_Angeles');

  return ref.watch(allUsersProvider.stream).map((users) {
    if (users.isEmpty) {
      return const UsersLoginHistogram(
        orderedDates: [],
        countsByDateThenBucket: {},
        maxDailyTotal: 0,
      );
    }

    // Build counts
    final Map<DateTime, Map<int, int>> counts = {};
    DateTime? minDate;
    DateTime? maxDate;

    for (final u in users) {
      final laMidUtc = _laMidnight(u.lastLoginAtUtc, la);
      final bucket = bucketDaysUsed(u.clientNumDaysUsed);
      final dayMap = counts.putIfAbsent(laMidUtc, () => {});
      dayMap[bucket] = (dayMap[bucket] ?? 0) + 1;
      if (minDate == null || laMidUtc.isBefore(minDate)) minDate = laMidUtc;
      if (maxDate == null || laMidUtc.isAfter(maxDate)) maxDate = laMidUtc;
    }

    // Fill domain from min to max inclusive, step 1 day, preserving LA-midnight UTC hour
    final ordered = <DateTime>[];
    if (minDate != null && maxDate != null) {
      var cursor = minDate; // already LA midnight converted to UTC
      final end = maxDate; // same representation
      while (!cursor.isAfter(end)) {
        ordered.add(cursor);
        counts.putIfAbsent(cursor, () => {});
        cursor = cursor.add(const Duration(days: 1));
      }
    }

    // Compute max daily total
    int maxTotal = 0;
    for (final entry in counts.entries) {
      final total = entry.value.values.fold<int>(0, (a, b) => a + b);
      if (total > maxTotal) maxTotal = total;
    }

    // Sort ordered by date asc (already built asc)
    return UsersLoginHistogram(
      orderedDates: ordered,
      countsByDateThenBucket: counts,
      maxDailyTotal: maxTotal,
    );
  });
});
