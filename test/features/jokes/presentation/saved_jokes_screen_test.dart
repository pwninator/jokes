import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/saved_jokes_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class _MockPerf extends Mock implements PerformanceService {}

// Test repository that properly handles streams
class _TestInteractionsRepo extends JokeInteractionsRepository {
  _TestInteractionsRepo({required super.db, required PerformanceService perf})
      : super(performanceService: perf);

  final _controllers = <String, StreamController<JokeInteraction?>>{};

  @override
  Stream<JokeInteraction?> watchJokeInteraction(String jokeId) {
    // Reuse existing controller for this jokeId or create a new one
    if (!_controllers.containsKey(jokeId)) {
      final controller = StreamController<JokeInteraction?>.broadcast();
      _controllers[jokeId] = controller;
      // Add initial value
      controller.add(null);
    }
    return _controllers[jokeId]!.stream;
  }

  void dispose() {
    for (final controller in _controllers.values) {
      controller.close();
    }
    _controllers.clear();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockJokeRepository mockRepository;
  late MockJokeReactionsService mockReactionsService;

  setUp(() {
    mockRepository = MockJokeRepository();
    mockReactionsService = MockJokeReactionsService();

    when(
      () => mockReactionsService.getAllUserReactions(),
    ).thenAnswer((_) async => {});
  });

  ProviderContainer createContainer({List<Override> overrides = const []}) {
    return ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          jokeRepositoryProvider.overrideWithValue(mockRepository),
          jokeReactionsServiceProvider.overrideWithValue(mockReactionsService),
          // Override jokeInteractionsRepository to return working streams
          jokeInteractionsRepositoryProvider.overrideWith((ref) {
            return _TestInteractionsRepo(
              db: AppDatabase.inMemory(),
              perf: _MockPerf(),
            );
          }),
          // Override categoryInteractionsRepository
          categoryInteractionsRepositoryProvider.overrideWith((ref) {
            return CategoryInteractionsRepository(
              db: AppDatabase.inMemory(),
              performanceService: _MockPerf(),
            );
          }),
          ...overrides,
        ],
      ),
    );
  }

  Joke buildTestJoke(String id) {
    return Joke(
      id: id,
      setupText: 'Setup $id',
      punchlineText: 'Punchline $id',
      setupImageUrl: 'https://example.com/setup_$id.jpg',
      punchlineImageUrl: 'https://example.com/punch_$id.jpg',
    );
  }

  Future<void> pumpSavedJokesScreen(
    WidgetTester tester,
    ProviderContainer container,
  ) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SavedJokesScreen()),
      ),
    );
    await tester.pump();
  }

  Future<void> pumpUntil(
    WidgetTester tester,
    bool Function() condition, {
    int maxTicks = 30,
    Duration step = const Duration(milliseconds: 50),
  }) async {
    for (var i = 0; i < maxTicks; i++) {
      await tester.pump(step);
      if (condition()) {
        return;
      }
    }
  }

  testWidgets('renders saved joke count when jokes exist', (tester) async {
    when(
      () => mockReactionsService.getSavedJokeIds(),
    ).thenAnswer((_) async => ['1', '2']);
    when(() => mockRepository.getJokesByIds(any())).thenAnswer((
      invocation,
    ) async {
      final ids = invocation.positionalArguments.first as List<String>;
      return ids.map(buildTestJoke).toList();
    });

    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSavedJokesScreen(tester, container);
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('saved_jokes_screen-results-count'))
          .evaluate()
          .isNotEmpty,
    );

    expect(
      find.byKey(const Key('saved_jokes_screen-results-count')),
      findsOneWidget,
    );
    expect(find.text('2 saved jokes'), findsOneWidget);
  });

  testWidgets('does not render count when no jokes are saved', (tester) async {
    when(
      () => mockReactionsService.getSavedJokeIds(),
    ).thenAnswer((_) async => <String>[]);
    when(
      () => mockRepository.getJokesByIds(any()),
    ).thenAnswer((_) async => <Joke>[]);

    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSavedJokesScreen(tester, container);
    await pumpUntil(tester, () => tester.binding.hasScheduledFrame == false);

    expect(
      find.byKey(const Key('saved_jokes_screen-results-count')),
      findsNothing,
    );
  });
}
