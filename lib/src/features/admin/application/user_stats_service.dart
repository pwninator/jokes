import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';

class UsersJokesHistogram {
  // Map of days used to a map of joke view buckets to user count
  final Map<int, Map<int, int>> countsByDaysUsed;
  final List<int> orderedDaysUsed;
  final int maxUsersInADaysUsedBucket;

  const UsersJokesHistogram({
    required this.countsByDaysUsed,
    required this.orderedDaysUsed,
    required this.maxUsersInADaysUsedBucket,
  });
}

// 0, 1, 2-5, 6-10, 11-20, 21-30, 31-40, 41-50, 51-70, 71-100, 101+
final jokeViewBuckets = [0, 1, 5, 10, 20, 30, 40, 50, 70, 100];

int getJokeViewBucket(int jokesViewed) {
  if (jokesViewed <= 0) return 0;
  if (jokesViewed == 1) return 1;
  if (jokesViewed <= 5) return 5;
  if (jokesViewed <= 10) return 10;
  if (jokesViewed <= 20) return 20;
  if (jokesViewed <= 30) return 30;
  if (jokesViewed <= 40) return 40;
  if (jokesViewed <= 50) return 50;
  if (jokesViewed <= 70) return 70;
  if (jokesViewed <= 100) return 100;
  return 101;
}

final usersJokesHistogramProvider = StreamProvider<UsersJokesHistogram>((ref) {
  return ref.watch(allUsersProvider.stream).map((users) {
    final now = DateTime.now().toUtc();
    final yesterday = now.subtract(const Duration(days: 1));
    final dayBeforeYesterday = DateTime(
      yesterday.year,
      yesterday.month,
      yesterday.day,
    );

    final filteredUsers = users.where((u) {
      return u.lastLoginAtUtc.isBefore(dayBeforeYesterday);
    }).toList();

    if (filteredUsers.isEmpty) {
      return const UsersJokesHistogram(
        countsByDaysUsed: {},
        orderedDaysUsed: [],
        maxUsersInADaysUsedBucket: 0,
      );
    }

    final Map<int, Map<int, int>> counts = {};
    for (final user in filteredUsers) {
      final daysUsed = user.clientNumDaysUsed;
      final jokeBucket = getJokeViewBucket(user.numJokesViewed);
      final dayMap = counts.putIfAbsent(daysUsed, () => {});
      dayMap[jokeBucket] = (dayMap[jokeBucket] ?? 0) + 1;
    }

    final orderedDaysUsed = counts.keys.toList()..sort();
    int maxUsers = 0;
    for (final day in orderedDaysUsed) {
      final total = counts[day]!.values.fold(0, (a, b) => a + b);
      if (total > maxUsers) {
        maxUsers = total;
      }
    }

    return UsersJokesHistogram(
      countsByDaysUsed: counts,
      orderedDaysUsed: orderedDaysUsed,
      maxUsersInADaysUsedBucket: maxUsers,
    );
  });
});
