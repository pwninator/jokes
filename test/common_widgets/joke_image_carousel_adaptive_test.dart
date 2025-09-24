import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/core_mocks.dart';

class _NoopImageService extends ImageService {
  @override
  String? getProcessedJokeImageUrl(String? imageUrl) => null;

  @override
  bool isValidImageUrl(String? url) => true;

  @override
  Future<String?> precacheJokeImage(String? imageUrl) async => null;

  @override
  Future<({String? setupUrl, String? punchlineUrl})> precacheJokeImages(
    Joke joke,
  ) async => (setupUrl: null, punchlineUrl: null);

  @override
  Future<void> precacheMultipleJokeImages(List<Joke> jokes) async {}
}

void main() {
  testWidgets('BOTH_ADAPTIVE is horizontal in wide constraints', (
    tester,
  ) async {
    // Wide constraints should choose Row
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          ...CoreMocks.getCoreProviderOverrides(),
          // Ensure no network/plugin calls by making image URLs resolve to null
          imageServiceProvider.overrideWithValue(_NoopImageService()),
        ],
        child: const MaterialApp(
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
                mode: JokeCarouselMode.bothAdaptive,
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
      ProviderScope(
        overrides: [
          ...CoreMocks.getCoreProviderOverrides(),
          imageServiceProvider.overrideWithValue(_NoopImageService()),
        ],
        child: const MaterialApp(
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
                mode: JokeCarouselMode.bothAdaptive,
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
