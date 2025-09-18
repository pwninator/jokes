import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

void main() {
  testWidgets('BOTH_ADAPTIVE is horizontal in wide constraints', (
    tester,
  ) async {
    // Wide constraints should choose Row
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 800,
              height: 400,
              child: JokeImageCarousel(
                joke: Joke(
                  id: '1',
                  setupText: 's',
                  punchlineText: 'p',
                  setupImageUrl: 'a',
                  punchlineImageUrl: 'b',
                ),
                jokeContext: 'test',
                mode: JokeCarouselMode.BOTH_ADAPTIVE,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();
    // Row is expected inside Card->Stack->GestureDetector->... AspectRatio child
    expect(find.byType(Row), findsWidgets);
  });

  testWidgets('BOTH_ADAPTIVE is vertical in tall constraints', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 400,
              height: 800,
              child: JokeImageCarousel(
                joke: Joke(
                  id: '2',
                  setupText: 's',
                  punchlineText: 'p',
                  setupImageUrl: 'a',
                  punchlineImageUrl: 'b',
                ),
                jokeContext: 'test',
                mode: JokeCarouselMode.BOTH_ADAPTIVE,
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byType(Column), findsWidgets);
  });
}
