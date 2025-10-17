import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart'
    show AppTab;
import 'package:snickerdoodle/src/core/services/app_review_service.dart'
    show ReviewRequestSource;
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/daily_jokes_screen.dart';

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/core_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

class _FakeBuildContext extends Fake implements BuildContext {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    AnalyticsMocks.registerFallbackValues();
    registerFallbackValue(ReviewRequestSource.jokeSaved);
    registerFallbackValue(JokeReactionType.save);
    registerFallbackValue(_FakeBuildContext());
    registerFallbackValue(AppTab.dailyJokes);
  });

  late MockJokeScheduleRepository mockScheduleRepository;
  late MockAppUsageService mockAppUsageService;
  late MockJokeReactionsService mockJokeReactionsService;
  late MockReviewPromptCoordinator mockReviewPromptCoordinator;
  late MockJokeInteractionsRepository mockJokeInteractionsRepository;
  late MockCategoryInteractionsRepository mockCategoryInteractionsRepository;

  setUp(() {
    FirebaseMocks.reset();
    CoreMocks.reset();
    AnalyticsMocks.reset();

    mockScheduleRepository = MockJokeScheduleRepository();
    mockAppUsageService = MockAppUsageService();
    mockJokeReactionsService = MockJokeReactionsService();
    mockReviewPromptCoordinator = MockReviewPromptCoordinator();
    mockJokeInteractionsRepository = MockJokeInteractionsRepository();
    mockCategoryInteractionsRepository = MockCategoryInteractionsRepository();

    when(
      () => mockAppUsageService.logJokeViewed(any<String>()),
    ).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumSavedJokes(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumSharedJokes(),
    ).thenAnswer((_) async => 0);
    when(() => mockAppUsageService.getNumDaysUsed()).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.incrementSavedJokesCount(),
    ).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.decrementSavedJokesCount(),
    ).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.incrementSharedJokesCount(),
    ).thenAnswer((_) async {});

    when(
      () => mockJokeReactionsService.toggleUserReaction(
        any<String>(),
        any<JokeReactionType>(),
        context: any(named: 'context'),
      ),
    ).thenAnswer((_) async => true);

    when(
      () => mockReviewPromptCoordinator.maybePromptForReview(
        source: any(named: 'source'),
        context: any(named: 'context'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockJokeInteractionsRepository.watchJokeInteraction(any()),
    ).thenAnswer((_) => Stream<JokeInteraction?>.value(null));

    when(
      () => mockCategoryInteractionsRepository.setViewed(any()),
    ).thenAnswer((_) async => true);
  });

  JokeScheduleBatch _createBatch() {
    final now = DateTime.now();
    final month = DateTime(now.year, now.month);
    final joke = Joke(
      id: 'joke-1',
      setupText: 'Setup line',
      punchlineText: 'Punchline line',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    return JokeScheduleBatch(
      id: JokeScheduleBatch.createBatchId(
        JokeConstants.defaultJokeScheduleId,
        month.year,
        month.month,
      ),
      scheduleId: JokeConstants.defaultJokeScheduleId,
      year: month.year,
      month: month.month,
      jokes: {'01': joke},
    );
  }

  ProviderContainer _createContainer(JokeScheduleBatch batch) {
    final overrides = FirebaseMocks.getFirebaseProviderOverrides(
      additionalOverrides: [
        analyticsServiceProvider.overrideWithValue(
          AnalyticsMocks.mockAnalyticsService,
        ),
        imageServiceProvider.overrideWithValue(CoreMocks.mockImageService),
        dailyJokeSubscriptionServiceProvider.overrideWithValue(
          CoreMocks.mockSubscriptionService,
        ),
        notificationServiceProvider.overrideWithValue(
          CoreMocks.mockNotificationService,
        ),
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        jokeScheduleRepositoryProvider.overrideWithValue(
          mockScheduleRepository,
        ),
        jokeReactionsServiceProvider.overrideWithValue(
          mockJokeReactionsService,
        ),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
        reviewPromptCoordinatorProvider.overrideWithValue(
          mockReviewPromptCoordinator,
        ),
        scheduleBatchesProvider.overrideWith(
          (_) => Stream<List<JokeScheduleBatch>>.value(<JokeScheduleBatch>[]),
        ),
      ],
    );

    return ProviderContainer(overrides: overrides);
  }

  GoRouter _createRouter() {
    return GoRouter(
      initialLocation: AppRoutes.jokes,
      routes: [
        GoRoute(
          path: AppRoutes.jokes,
          name: RouteNames.jokes,
          builder: (_, __) => const DailyJokesScreen(),
        ),
        GoRoute(
          path: '/other',
          name: 'other',
          builder: (_, __) =>
              const Scaffold(body: Center(child: Text('Other'))),
        ),
      ],
    );
  }

  Widget _buildApp(ProviderContainer container, GoRouter router) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    );
  }

  group('DailyJokesScreen', () {
    testWidgets('triggers stale checks while visible and on resume', (
      tester,
    ) async {
      final batch = _createBatch();

      when(
        () => mockScheduleRepository.getBatchForMonth(any(), any(), any()),
      ).thenAnswer((invocation) async {
        final int year = invocation.positionalArguments[1] as int;
        final int month = invocation.positionalArguments[2] as int;
        if (year == batch.year && month == batch.month) {
          return batch;
        }
        return null;
      });

      final container = _createContainer(batch);
      addTearDown(container.dispose);

      final router = _createRouter();
      addTearDown(router.dispose);

      await tester.pumpWidget(_buildApp(container, router));

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      container.read(currentRouteProvider.notifier).state = '/initial';
      await tester.pump();
      container.read(currentRouteProvider.notifier).state = AppRoutes.jokes;
      await tester.pump();

      expect(container.read(dailyJokesCheckNowProvider), 1);

      await tester.pump(const Duration(minutes: 1));
      expect(container.read(dailyJokesCheckNowProvider), 2);

      final state =
          tester.state(find.byType(DailyJokesScreen)) as State<StatefulWidget>;

      (state as dynamic).didChangeAppLifecycleState(AppLifecycleState.paused);
      await tester.pump(const Duration(minutes: 1));
      expect(container.read(dailyJokesCheckNowProvider), 2);

      (state as dynamic).didChangeAppLifecycleState(AppLifecycleState.resumed);
      await tester.pump();
      expect(container.read(dailyJokesCheckNowProvider), 3);

      await tester.pump(const Duration(minutes: 1));
      expect(container.read(dailyJokesCheckNowProvider), 4);
    });

    testWidgets('pauses timer when screen is off the active route', (
      tester,
    ) async {
      final batch = _createBatch();

      when(
        () => mockScheduleRepository.getBatchForMonth(any(), any(), any()),
      ).thenAnswer((invocation) async {
        final int year = invocation.positionalArguments[1] as int;
        final int month = invocation.positionalArguments[2] as int;
        if (year == batch.year && month == batch.month) {
          return batch;
        }
        return null;
      });

      final container = _createContainer(batch);
      addTearDown(container.dispose);

      final router = _createRouter();
      addTearDown(router.dispose);

      await tester.pumpWidget(_buildApp(container, router));

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      container.read(currentRouteProvider.notifier).state = '/initial';
      await tester.pump();
      container.read(currentRouteProvider.notifier).state = AppRoutes.jokes;
      await tester.pump();

      final baseline = container.read(dailyJokesCheckNowProvider);

      container.read(currentRouteProvider.notifier).state = AppRoutes.saved;
      await tester.pump();
      await tester.pump(const Duration(minutes: 2));

      expect(container.read(dailyJokesCheckNowProvider), baseline);

      container.read(currentRouteProvider.notifier).state = AppRoutes.jokes;
      await tester.pump();

      expect(container.read(dailyJokesCheckNowProvider), baseline + 1);
    });
  });
}
