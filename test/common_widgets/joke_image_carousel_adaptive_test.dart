import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

import '../test_helpers/core_mocks.dart';

class _NoopImageService extends ImageService {
  @override
  String? getProcessedJokeImageUrl(String? imageUrl, {int? width}) => null;
  @override
  bool isValidImageUrl(String? url) => true;
  @override
  Future<String?> precacheJokeImage(String? imageUrl, {int? width}) async => null;
  @override
  Future<({String? setupUrl, String? punchlineUrl})> precacheJokeImages(
    Joke joke, {
    int? width,
  }) async =>
      (setupUrl: null, punchlineUrl: null);
  @override
  Future<void> precacheMultipleJokeImages(
    List<Joke> jokes, {
    int? width,
  }) async {}
}

void main() {
  testWidgets('BOTH_ADAPTIVE mode adapts layout to wide and tall constraints', (tester) async {
    const testJoke = Joke(
      id: '1',
      setupText: 's',
      punchlineText: 'p',
      setupImageUrl: 'a',
      punchlineImageUrl: 'b',
    );

    Widget buildTestableWidget(double width, double height) {
      return ProviderScope(
        overrides: [
          ...CoreMocks.getCoreProviderOverrides(),
          imageServiceProvider.overrideWithValue(_NoopImageService()),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: width,
              height: height,
              child: const JokeImageCarousel(
                joke: testJoke,
                jokeContext: 'test',
                mode: JokeViewerMode.bothAdaptive,
              ),
            ),
          ),
        ),
      );
    }

    // --- Test 1: Wide constraints should use a Row ---
    await tester.pumpWidget(buildTestableWidget(800, 400));
    await tester.pumpAndSettle();
    final cardFinder = find.byType(Card);
    expect(cardFinder, findsOneWidget);
    // The adaptive layout is inside the Card, so we scope our search to its descendants.
    expect(
      find.descendant(of: cardFinder, matching: find.byType(Row)),
      findsOneWidget,
      reason: 'A Row should be used for image layout in wide mode',
    );
    expect(
      find.descendant(of: cardFinder, matching: find.byType(Column)),
      findsNothing,
      reason: 'A Column should not be used for image layout in wide mode',
    );

    // --- Test 2: Tall constraints should use a Column ---
    await tester.pumpWidget(buildTestableWidget(400, 800));
    await tester.pumpAndSettle();
    // The card finder is still valid.
    expect(cardFinder, findsOneWidget);
    expect(
      find.descendant(of: cardFinder, matching: find.byType(Column)),
      findsOneWidget,
      reason: 'A Column should be used for image layout in tall mode',
    );
    expect(
      find.descendant(of: cardFinder, matching: find.byType(Row)),
      findsNothing,
      reason: 'A Row should not be used for image layout in tall mode',
    );
  });
}