import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/user_repository.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';
import 'package:snickerdoodle/src/features/admin/application/user_stats_service.dart';

class MockUserRepository extends Mock implements UserRepository {}

void main() {
  group('usersJokesHistogramProvider', () {
    late MockUserRepository mockUserRepository;

    setUp(() {
      mockUserRepository = MockUserRepository();
    });

    test('filters users and creates histogram', () async {
      final now = DateTime.now().toUtc();
      final users = [
        // Should be included
        AppUserSummary(
          lastLoginAtUtc: now.subtract(const Duration(days: 2)),
          clientNumDaysUsed: 5,
          numJokesViewed: 15,
        ),
        // Should be excluded (too recent)
        AppUserSummary(
          lastLoginAtUtc: now,
          clientNumDaysUsed: 10,
          numJokesViewed: 25,
        ),
        // Should be included
        AppUserSummary(
          lastLoginAtUtc: now.subtract(const Duration(days: 10)),
          clientNumDaysUsed: 5,
          numJokesViewed: 8,
        ),
      ];

      when(
        () => mockUserRepository.watchAllUsers(),
      ).thenAnswer((_) => Stream.value(users));

      final container = ProviderContainer(
        overrides: [
          userRepositoryProvider.overrideWithValue(mockUserRepository),
        ],
      );

      final histogram = await container.read(
        usersJokesHistogramProvider.future,
      );

      expect(histogram.orderedDaysUsed, [5]);
      expect(histogram.countsByDaysUsed.length, 1);
      expect(histogram.countsByDaysUsed[5]!.length, 2);
      expect(histogram.countsByDaysUsed[5]![20], 1); // 15 jokes -> bucket 20
      expect(histogram.countsByDaysUsed[5]![10], 1); // 8 jokes -> bucket 10
      expect(histogram.maxUsersPerDay, 2);
    });
  });
}
