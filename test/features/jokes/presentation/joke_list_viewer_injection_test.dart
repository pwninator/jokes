import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_slots.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

import '../../../helpers/joke_viewer_test_utils.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

Joke buildJoke(String id) {
  return Joke(
    id: id,
    setupText: 'setup $id',
    punchlineText: 'punchline $id',
    setupImageUrl: 'setup-$id.png',
    punchlineImageUrl: 'punchline-$id.png',
  );
}

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

  testWidgets('renders injected cards from strategies', (tester) async {
    final jokes = <JokeWithDate>[
      JokeWithDate(joke: buildJoke('j1')),
      JokeWithDate(joke: buildJoke('j2')),
    ];

    final strategy = _FixedStrategy(
      InjectedSlotDescriptor(
        id: 'promo',
        jokesBefore: 1,
        builder: (_, data) => Text('Injected card ${data.realJokesBefore}'),
      ),
    );

    final sequence = JokeListSlotSequence(jokes: jokes, strategies: [strategy]);
    final injectedSlot = sequence.slotAt(1) as InjectedSlot;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(builder: (context) => injectedSlot.build(context)),
        ),
      ),
    );

    expect(find.text('Injected card 1'), findsOneWidget);
  });

  testWidgets('advancing to injected slot keeps it visible', (tester) async {
    final jokes = <JokeWithDate>[
      JokeWithDate(joke: buildJoke('j1')),
      JokeWithDate(joke: buildJoke('j2')),
    ];

    final previewSequence = JokeListSlotSequence(
      jokes: jokes,
      strategies: const [EndOfFeedInjectedCardStrategy()],
      hasMore: false,
      isLoading: false,
    );
    expect(previewSequence.slotCount, equals(3));
    expect(previewSequence.slotAt(2), isA<InjectedSlot>());

    final analytics = MockAnalyticsService();
    when(
      () => analytics.logJokeNavigation(
        any(),
        any(),
        method: any(named: 'method'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
        brightness: any(named: 'brightness'),
        screenOrientation: any(named: 'screenOrientation'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => analytics.logErrorJokesLoad(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [...buildJokeViewerOverrides(analyticsService: analytics)],
        child: MaterialApp(
          home: JokeListViewer(
            jokeContext: 'test',
            viewerId: 'viewer',
            jokesAsyncValue: AsyncValue<List<JokeWithDate>>.data(jokes),
            injectionStrategies: const [EndOfFeedInjectedCardStrategy()],
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();
    final ctaFinder = find.byKey(const Key('joke_list_viewer-cta-button'));
    await tester.tap(ctaFinder);
    await tester.pumpAndSettle();
    await tester.tap(ctaFinder);
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 400));

    final pageViewFinder = find.byKey(const Key('joke_viewer_page_view'));
    final pageView = tester.widget<PageView>(pageViewFinder);
    expect(pageView.controller?.page, closeTo(2, 0.01));
    expect(
      find.byKey(const ValueKey('page-injected-end_of_feed')),
      findsOneWidget,
    );
    expect(
      find.textContaining('Fresh illustrated jokes drop tomorrow'),
      findsOneWidget,
    );
  });
}

class _FixedStrategy extends JokeListInjectionStrategy {
  _FixedStrategy(this._descriptor);

  final InjectedSlotDescriptor _descriptor;

  @override
  Iterable<InjectedSlotDescriptor> build({
    required List<JokeWithDate> jokes,
    required bool hasMore,
    required bool isLoading,
  }) => <InjectedSlotDescriptor>[_descriptor];
}
