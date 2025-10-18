import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class _MockPerf extends Mock implements PerformanceService {}

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

  ProviderContainer createContainer({List<Override> overrides = const []}) {
    return ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          // Ensure SettingsService is available for widgets that read it
          settingsServiceProvider.overrideWithValue(
            FirebaseMocks.mockSettingsService,
          ),
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

  Future<void> pumpSearch(
    WidgetTester tester,
    ProviderContainer container,
  ) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SearchScreen()),
      ),
    );
    await tester.pump();
  }

  Future<void> pumpUntil(
    WidgetTester tester,
    bool Function() condition, {
    int maxTicks = 20,
    Duration step = const Duration(milliseconds: 50),
  }) async {
    for (var i = 0; i < maxTicks; i++) {
      await tester.pump(step);
      if (condition()) {
        return;
      }
    }
  }

  testWidgets('focuses the search field on load', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final fieldFinder = find.byKey(const Key('search_screen-search-field'));
    final textField = tester.widget<TextField>(fieldFinder);
    expect(textField.focusNode?.hasFocus, isTrue);
  });

  testWidgets('opening the screen clears any existing query', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    final notifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = notifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}legacy',
      label: SearchLabel.category,
    );

    await pumpSearch(tester, container);

    final cleared = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(cleared.query, '');
    expect(cleared.label, JokeConstants.userSearchLabel);
    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
  });

  testWidgets('submitting <2 chars shows banner and preserves query', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'a');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(
      tester,
      () =>
          find.text('Please enter a longer search query').evaluate().isNotEmpty,
    );

    expect(find.text('Please enter a longer search query'), findsOneWidget);
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.query, '');
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('renders single-result count', (tester) async {
    final mockRepo = MockJokeRepository();
    when(() => mockRepo.getJokesByIds(any())).thenAnswer((inv) async {
      final ids = (inv.positionalArguments[0] as List<String>);
      return ids
          .map(
            (id) => Joke(
              id: id,
              setupText: 'setup-$id',
              punchlineText: 'punch-$id',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          )
          .toList();
    });

    final container = createContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => const [JokeSearchResult(id: '1', vectorDistance: 0.0)],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 's',
              punchlineText: 'p',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'cats');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(tester, () => find.text('1 result').evaluate().isNotEmpty);

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);
  });

  testWidgets('renders pluralised result count', (tester) async {
    final mockRepo = MockJokeRepository();
    when(() => mockRepo.getJokesByIds(any())).thenAnswer((inv) async {
      final ids = (inv.positionalArguments[0] as List<String>);
      return ids
          .map(
            (id) => Joke(
              id: id,
              setupText: 'setup-$id',
              punchlineText: 'punch-$id',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          )
          .toList();
    });

    final container = createContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => [
            const JokeSearchResult(id: '1', vectorDistance: 0.1),
            const JokeSearchResult(id: '2', vectorDistance: 0.2),
          ],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 'a',
              punchlineText: 'b',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
        jokeStreamByIdProvider('2').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '2',
              setupText: 'c',
              punchlineText: 'd',
              setupImageUrl: 'c',
              punchlineImageUrl: 'd',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'robots');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(tester, () => find.text('2 results').evaluate().isNotEmpty);

    expect(find.text('2 results'), findsOneWidget);
  });

  testWidgets('shows placeholder when no query has been submitted', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
    expect(find.byKey(const Key('search-results-count')), findsNothing);
  });

  testWidgets('clear button resets provider and restores placeholder', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'space cows');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '${JokeConstants.searchQueryPrefix}space cows',
    );

    final clearBtn = find.byKey(const Key('search_screen-clear-button'));
    expect(clearBtn, findsOneWidget);

    await tester.tap(clearBtn);
    await tester.pump();

    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );
    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
  });

  testWidgets('manual typing sets search label to none', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'manual search');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(
      searchQuery.query,
      '${JokeConstants.searchQueryPrefix}manual search',
    );
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('prefilled similar search preserves query and shows count', (
    tester,
  ) async {
    final mockRepo = MockJokeRepository();
    when(() => mockRepo.getJokesByIds(any())).thenAnswer((inv) async {
      final ids = (inv.positionalArguments[0] as List<String>);
      return ids
          .map(
            (id) => Joke(
              id: id,
              setupText: 'setup-$id',
              punchlineText: 'punch-$id',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          )
          .toList();
    });

    final container = createContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => const [JokeSearchResult(id: '1', vectorDistance: 0.0)],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 'setup',
              punchlineText: 'punch',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    // Programmatically set a Similar Search before opening screen
    final notifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = notifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}cats and dogs',
      label: SearchLabel.similarJokes,
    );

    await pumpSearch(tester, container);
    await pumpUntil(
      tester,
      () => find.byKey(const Key('search-results-count')).evaluate().isNotEmpty,
    );

    // Text field shows the effective query (without prefix)
    final fieldFinder = find.byKey(const Key('search_screen-search-field'));
    final textField = tester.widget<TextField>(fieldFinder);
    expect(textField.controller?.text, 'cats and dogs');

    // Results count appears (since query preserved and provider returns 1)
    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);

    // Label remains similarJokes
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.label, SearchLabel.similarJokes);
  });
}
