import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/application/user_stats_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/user_jokes_chart.dart';

class MockUsersJokesHistogram extends Mock implements UsersJokesHistogram {}

void main() {
  group('UserJokesChart', () {
    late UsersJokesHistogram mockHistogram;

    setUp(() {
      mockHistogram = MockUsersJokesHistogram();
      when(() => mockHistogram.orderedDaysUsed).thenReturn([5, 10]);
      when(() => mockHistogram.countsByDaysUsed).thenReturn({
        5: {10: 1, 20: 2},
        10: {5: 3, 50: 1},
      });
      when(() => mockHistogram.maxUsersInADaysUsedBucket).thenReturn(4);
    });

    testWidgets('renders chart correctly with data', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            usersJokesHistogramProvider.overrideWith(
              (ref) => Stream.value(mockHistogram),
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: UserJokesChart())),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(UserJokesChart), findsOneWidget);
      expect(
        find.text('User Activity: Jokes Viewed vs. Days Used'),
        findsOneWidget,
      );
      expect(find.byType(JokesLegend), findsOneWidget);
    });

    testWidgets('shows loading indicator', (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            usersJokesHistogramProvider.overrideWith(
              (ref) => const Stream.empty(),
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: UserJokesChart())),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows error message', (WidgetTester tester) async {
      final error = Exception('Failed to load');
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            usersJokesHistogramProvider.overrideWith(
              (ref) => Stream.error(error),
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: UserJokesChart())),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Error: $error'), findsOneWidget);
    });
  });
}
