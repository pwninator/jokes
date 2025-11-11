import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entry_renderers.dart';

import '../../../helpers/joke_viewer_test_utils.dart' as viewer_test_utils;

void main() {
  setUpAll(() {
    registerFallbackValue(JokeField.creationTime);
    registerFallbackValue(OrderDirection.ascending);
  });

  group('JokeSlotEntryRenderer', () {
    testWidgets('builds JokeCard with provided config', (tester) async {
      final entry = JokeSlotEntry(joke: JokeWithDate(joke: _joke('alpha')));
      final renderer = JokeSlotEntryRenderer();

      await tester.pumpWidget(
        ProviderScope(
          overrides: viewer_test_utils.buildJokeViewerOverrides(
            analyticsService: viewer_test_utils.NoopAnalyticsService(),
          ),
          child: MaterialApp(
            home: Consumer(
              builder: (context, ref, _) {
                final config = SlotEntryViewConfig(
                  context: context,
                  ref: ref,
                  index: 0,
                  isLandscape: false,
                  jokeContext: 'feed',
                  showSimilarSearchButton: true,
                  jokeConfig: JokeEntryViewConfig(
                    formattedDate: '1/1/2024',
                    jokesToPreload: const [],
                    carouselController: JokeImageCarouselController(),
                    onImageStateChanged: (_) {},
                    dataSource: 'local',
                  ),
                );
                return renderer.build(entry: entry, config: config);
              },
            ),
          ),
        ),
      );

      expect(find.byType(JokeCard), findsOneWidget);
    });
  });

  group('EndOfFeedSlotEntryRenderer', () {
    testWidgets('renders end-of-feed card text', (tester) async {
      final entry = EndOfFeedSlotEntry(jokeContext: 'feed', totalJokes: 5);
      final renderer = EndOfFeedSlotEntryRenderer();

      await tester.pumpWidget(
        ProviderScope(
          overrides: viewer_test_utils.buildJokeViewerOverrides(
            analyticsService: viewer_test_utils.NoopAnalyticsService(),
          ),
          child: MaterialApp(
            home: Consumer(
              builder: (context, ref, _) {
                final config = SlotEntryViewConfig(
                  context: context,
                  ref: ref,
                  index: 1,
                  isLandscape: false,
                  jokeContext: 'feed',
                  showSimilarSearchButton: false,
                );
                return renderer.build(entry: entry, config: config);
              },
            ),
          ),
        ),
      );

      expect(find.text("You're all caught up!"), findsOneWidget);
    });
  });
}

Joke _joke(String id) =>
    Joke(id: id, setupText: 'setup $id', punchlineText: 'punchline $id');
