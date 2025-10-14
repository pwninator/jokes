import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/save_joke_button.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

import '../test_helpers/analytics_mocks.dart';
import '../test_helpers/core_mocks.dart';

class _MockPerf extends Mock implements PerformanceService {}

class _StreamInteractionsRepo extends JokeInteractionsRepository {
  _StreamInteractionsRepo({required this.stream, required super.db, required PerformanceService perf})
      : super(performanceService: perf);

  final Stream<bool> stream;

  @override
  Stream<JokeInteraction?> watchJokeInteraction(String jokeId) {
    return stream.map((saved) {
      if (!saved) return null;
      final now = DateTime.now();
      return JokeInteraction(
        jokeId: jokeId,
        viewedTimestamp: null,
        savedTimestamp: now,
        sharedTimestamp: null,
        lastUpdateTimestamp: now,
      );
    });
  }
}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class _FakeBuildContext extends Fake implements BuildContext {}

void main() {
  setUpAll(() {
    registerFallbackValue(_FakeBuildContext());
    registerAnalyticsFallbackValues();
  });

  group('SaveJokeButton', () {
    late MockJokeReactionsService mockService;
    late MockAppUsageService mockUsage;
    late StreamController<bool> controller;

    const jokeId = 'j-123';
    const jokeContext = 'test-ctx';

    Widget createUnderTest(List<Override> extra) {
      return ProviderScope(
        overrides: [
          // Provide analytics and core overrides to avoid null behavior
          ...CoreMocks.getCoreProviderOverrides(
            additionalOverrides: AnalyticsMocks.getAnalyticsProviderOverrides(),
          ),
          // Override reactions service used by onTap
          jokeReactionsServiceProvider.overrideWithValue(mockService),
          // Provide app usage service used after toggle
          appUsageServiceProvider.overrideWithValue(mockUsage),
          // Provide a controlled stream for saved state via repository
          jokeInteractionsRepositoryProvider.overrideWith((ref) {
            return _StreamInteractionsRepo(
              stream: controller.stream,
              db: AppDatabase.inMemory(),
              perf: _MockPerf(),
            );
          }),
          ...extra,
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: const Scaffold(
            body: Center(
              child: SaveJokeButton(
                jokeId: jokeId,
                jokeContext: jokeContext,
                size: 24,
              ),
            ),
          ),
        ),
      );
    }

    setUp(() {
      mockService = MockJokeReactionsService();
      mockUsage = MockAppUsageService();
      controller = StreamController<bool>.broadcast();

      when(() => mockUsage.getNumSavedJokes()).thenAnswer((_) async => 0);
      when(
        () => mockService.toggleUserReaction(
          any(),
          any(),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => true);
    });

    tearDown(() async {
      await controller.close();
    });

    testWidgets('shows loading while stream has not emitted', (tester) async {
      await tester.pumpWidget(createUnderTest(const []));

      // No event yet -> loading indicator
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('renders border icon when not saved', (tester) async {
      await tester.pumpWidget(createUnderTest(const []));

      controller.add(false);
      await tester.pump();

      expect(find.byIcon(Icons.favorite_border), findsOneWidget);
    });

    testWidgets('renders filled red icon when saved', (tester) async {
      await tester.pumpWidget(createUnderTest(const []));

      controller.add(true);
      await tester.pump();

      final icon = tester.widget<Icon>(find.byIcon(Icons.favorite));
      final context = tester.element(find.byIcon(Icons.favorite));
      final expectedColor = Theme.of(context).colorScheme.error;
      expect(icon.color, expectedColor);
    });

    testWidgets('tap calls toggleUserReaction', (tester) async {
      await tester.pumpWidget(createUnderTest(const []));

      controller.add(false);
      await tester.pump();

      await tester.tap(find.byKey(const Key('save_joke_button-$jokeId')));
      await tester.pump();

      verify(
        () => mockService.toggleUserReaction(
          jokeId,
          JokeReactionType.save,
          context: any(named: 'context'),
        ),
      ).called(1);
    });

    testWidgets('handles stream error gracefully', (tester) async {
      await tester.pumpWidget(createUnderTest(const []));

      controller.addError(Exception('stream failed'));
      await tester.pump();

      // Fallback icon should render without crash
      expect(find.byIcon(Icons.favorite_border), findsOneWidget);
    });
  });
}


