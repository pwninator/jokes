import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/user_repository.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_screen.dart';

class _MockUserRepository extends Mock implements UserRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(<AppUserSummary>[]);
  });

  testWidgets('renders chart and legend with mocked data', (tester) async {
    final mockRepo = _MockUserRepository();
    // Provide small dataset across 3 days with varied buckets
    final nowUtc = DateTime.utc(2025, 1, 10, 12);
    final users = <AppUserSummary>[
      AppUserSummary(lastLoginAtUtc: nowUtc, clientNumDaysUsed: 1),
      AppUserSummary(lastLoginAtUtc: nowUtc, clientNumDaysUsed: 2),
      AppUserSummary(
        lastLoginAtUtc: nowUtc.subtract(const Duration(days: 1)),
        clientNumDaysUsed: 10,
      ),
      AppUserSummary(
        lastLoginAtUtc: nowUtc.subtract(const Duration(days: 2)),
        clientNumDaysUsed: 5,
      ),
    ];
    when(() => mockRepo.watchAllUsers()).thenAnswer((_) => Stream.value(users));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [userRepositoryProvider.overrideWithValue(mockRepo)],
        child: MaterialApp(
          theme: lightTheme,
          darkTheme: darkTheme,
          home: const UsersAnalyticsScreen(),
        ),
      ),
    );

    // initial loading
    await tester.pump();

    // Expect chart present
    expect(find.byType(BarChart), findsNWidgets(3));

    // Expect titles
    expect(find.text('New Users per Day'), findsOneWidget);
    expect(find.text('User Retention by Cohort (Absolute)'), findsOneWidget);
    expect(find.text('User Retention by Cohort (Percentage)'), findsOneWidget);

    // Expect legend chips present (10 chips)
    for (final label in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10+']) {
      expect(find.text(label), findsWidgets);
    }
  });
}
