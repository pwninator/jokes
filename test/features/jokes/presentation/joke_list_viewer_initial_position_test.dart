import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

import '../../../helpers/joke_viewer_test_utils.dart';

class MockJokeListDataSource extends Mock implements JokeListDataSource {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  setUpAll(() {
    registerFallbackValue(JokeViewerMode.reveal);
    registerFallbackValue(Brightness.light);
    registerFallbackValue(JokeField.state);
    registerFallbackValue(
      JokeFilter(field: JokeField.state, isEqualTo: 'test'),
    );
    registerFallbackValue(OrderDirection.ascending);
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 0, docId: 'cursor'),
    );
  });

  group('JokeListViewer initial position', () {
    late MockJokeListDataSource mockDataSource;
    late MockAnalyticsService mockAnalyticsService;
    late Provider<AsyncValue<List<JokeWithDate>>> itemsProvider;
    late Provider<bool> isDataPendingProvider;

    setUp(() {
      mockDataSource = MockJokeListDataSource();
      mockAnalyticsService = MockAnalyticsService();

      when(() => mockDataSource.updateViewingIndex(any())).thenAnswer((_) {});
      when(
        () => mockAnalyticsService.logJokeNavigation(
          any(),
          any(),
          method: any(named: 'method'),
          jokeContext: any(named: 'jokeContext'),
          jokeViewerMode: any(named: 'jokeViewerMode'),
          brightness: any(named: 'brightness'),
          screenOrientation: any(named: 'screenOrientation'),
        ),
      ).thenAnswer((_) {});
      when(
        () => mockAnalyticsService.logErrorJokesLoad(
          source: any(named: 'source'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) {});

      itemsProvider = Provider(
        (ref) => const AsyncValue<List<JokeWithDate>>.data([]),
      );
      isDataPendingProvider = Provider((ref) => false);

      when(() => mockDataSource.items).thenAnswer((_) => itemsProvider);
      when(
        () => mockDataSource.isDataPending,
      ).thenAnswer((_) => isDataPendingProvider);
    });

    void setLoadedJokes(List<JokeWithDate> jokes) {
      itemsProvider = Provider((ref) => AsyncValue.data(jokes));
    }

    void setIsDataPending(bool value) {
      isDataPendingProvider = Provider((ref) => value);
    }

    testWidgets(
      'jumps to provided initial joke id and updates viewing providers',
      (tester) async {
        // Arrange
        final jokes = List.generate(
          3,
          (index) => JokeWithDate(
            joke: Joke(
              id: 'joke_$index',
              setupText: 'Setup $index',
              punchlineText: 'Punchline $index',
              setupImageUrl: 'https://example.com/setup$index.png',
              punchlineImageUrl: 'https://example.com/punchline$index.png',
            ),
          ),
        );

        setLoadedJokes(jokes);
        setIsDataPending(false);

        // Act
        await tester.pumpWidget(
          ProviderScope(
            overrides: buildJokeViewerOverrides(
              analyticsService: mockAnalyticsService,
            ),
            child: MaterialApp(
              home: Scaffold(
                body: JokeListViewer(
                  viewerId: 'viewer',
                  jokeContext: 'ctx',
                  dataSource: mockDataSource,
                  initialJokeId: 'joke_1',
                ),
              ),
            ),
          ),
        );

        await tester.pump();
        await tester.pump();

        // Assert
        final pageView = tester.widget<PageView>(
          find.byKey(const Key('joke_viewer_page_view')),
        );
        expect(pageView.controller?.page, closeTo(1, 0.01));

        final container = ProviderScope.containerOf(
          tester.element(find.byType(JokeListViewer)),
        );
        expect(container.read(jokeViewerPageIndexProvider('viewer')), 1);
        verify(() => mockDataSource.updateViewingIndex(1)).called(2);
        await tester.pump(const Duration(seconds: 2));
      },
    );

    testWidgets(
      'defers jump until the target joke id becomes available in the data',
      (tester) async {
        // Arrange
        final initialJokes = [
          JokeWithDate(
            joke: Joke(
              id: 'joke_0',
              setupText: 'Setup 0',
              punchlineText: 'Punchline 0',
              setupImageUrl: 'https://example.com/setup0.png',
              punchlineImageUrl: 'https://example.com/punchline0.png',
            ),
          ),
        ];

        final updatedJokes = [
          ...initialJokes,
          JokeWithDate(
            joke: Joke(
              id: 'joke_1',
              setupText: 'Setup 1',
              punchlineText: 'Punchline 1',
              setupImageUrl: 'https://example.com/setup1.png',
              punchlineImageUrl: 'https://example.com/punchline1.png',
            ),
          ),
          JokeWithDate(
            joke: Joke(
              id: 'joke_2',
              setupText: 'Setup 2',
              punchlineText: 'Punchline 2',
              setupImageUrl: 'https://example.com/setup2.png',
              punchlineImageUrl: 'https://example.com/punchline2.png',
            ),
          ),
        ];

        setLoadedJokes(initialJokes);
        setIsDataPending(false);

        await tester.pumpWidget(
          ProviderScope(
            overrides: buildJokeViewerOverrides(
              analyticsService: mockAnalyticsService,
            ),
            child: MaterialApp(
              home: Scaffold(
                body: JokeListViewer(
                  key: const Key('viewer'),
                  viewerId: 'viewer',
                  jokeContext: 'ctx',
                  dataSource: mockDataSource,
                  initialJokeId: 'joke_2',
                ),
              ),
            ),
          ),
        );

        await tester.pump();
        await tester.pump();

        var pageView = tester.widget<PageView>(
          find.byKey(const Key('joke_viewer_page_view')),
        );
        expect(pageView.controller?.page, closeTo(0, 0.01));
        verifyNever(() => mockDataSource.updateViewingIndex(any()));

        setLoadedJokes(updatedJokes);
        await tester.pump(const Duration(seconds: 2));

        await tester.pumpWidget(
          ProviderScope(
            overrides: buildJokeViewerOverrides(
              analyticsService: mockAnalyticsService,
            ),
            child: MaterialApp(
              home: Scaffold(
                body: JokeListViewer(
                  key: const Key('viewer'),
                  viewerId: 'viewer',
                  jokeContext: 'ctx',
                  dataSource: mockDataSource,
                  initialJokeId: 'joke_2',
                ),
              ),
            ),
          ),
        );

        await tester.pump();
        await tester.pump();

        pageView = tester.widget<PageView>(
          find.byKey(const Key('joke_viewer_page_view')),
        );
        expect(pageView.controller?.page, closeTo(2, 0.01));
        verify(() => mockDataSource.updateViewingIndex(2)).called(2);
        await tester.pump(const Duration(seconds: 2));
      },
    );

    testWidgets('invokes onJokeChange when navigation occurs', (tester) async {
      // Arrange
      final jokes = List.generate(
        3,
        (index) => JokeWithDate(
          joke: Joke(
            id: 'joke_$index',
            setupText: 'Setup $index',
            punchlineText: 'Punchline $index',
            setupImageUrl: 'https://example.com/setup$index.png',
            punchlineImageUrl: 'https://example.com/punchline$index.png',
          ),
        ),
      );
      final changedIds = <String>[];

      setLoadedJokes(jokes);

      await tester.pumpWidget(
        ProviderScope(
          overrides: buildJokeViewerOverrides(
            analyticsService: mockAnalyticsService,
          ),
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                viewerId: 'viewer',
                jokeContext: 'ctx',
                dataSource: mockDataSource,
                initialJokeId: 'joke_1',
                onJokeChange: changedIds.add,
              ),
            ),
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      if (changedIds.isNotEmpty) {
        expect(changedIds.first, 'joke_1');
      }

      await tester.fling(
        find.byKey(const Key('joke_viewer_page_view')),
        const Offset(0, -600),
        1000,
      );
      await tester.pumpAndSettle();

      expect(changedIds.contains('joke_2'), isTrue);
      await tester.pump(const Duration(seconds: 2));
    });
  });
}
