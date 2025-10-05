import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/firebase_mocks.dart';

void main() {
  group('JokeCard', () {
    Widget createTestWidget(Widget child) {
      return ProviderScope(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(),
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(body: child),
        ),
      );
    }

    testWidgets('renders correct child widget based on image URL validity', (tester) async {
      final textJokeTestCases = {
        'both null': const Joke(id: '1', setupText: 's', punchlineText: 'p', setupImageUrl: null, punchlineImageUrl: null),
        'setup null': const Joke(id: '2', setupText: 's', punchlineText: 'p', setupImageUrl: null, punchlineImageUrl: 'https://a.com/p.jpg'),
        'punchline null': const Joke(id: '3', setupText: 's', punchlineText: 'p', setupImageUrl: 'https://a.com/s.jpg', punchlineImageUrl: null),
        'both empty': const Joke(id: '4', setupText: 's', punchlineText: 'p', setupImageUrl: '', punchlineImageUrl: ''),
        'both whitespace': const Joke(id: '5', setupText: 's', punchlineText: 'p', setupImageUrl: '  ', punchlineImageUrl: '\t'),
      };

      for (final entry in textJokeTestCases.entries) {
        await tester.pumpWidget(createTestWidget(JokeCard(joke: entry.value, jokeContext: 'test')));
        expect(find.byType(JokeTextCard), findsOneWidget, reason: 'should show JokeTextCard when image URLs are ${entry.key}');
        expect(find.byType(JokeImageCarousel), findsNothing);
      }

      // Test case for when both images are valid
      const imageJoke = Joke(
        id: '6',
        setupText: 's',
        punchlineText: 'p',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );
      await tester.pumpWidget(createTestWidget(const JokeCard(joke: imageJoke, jokeContext: 'test')));
      expect(find.byType(JokeImageCarousel), findsOneWidget, reason: 'should show JokeImageCarousel when both image URLs are valid');
      expect(find.byType(JokeTextCard), findsNothing);
    });

    testWidgets('correctly passes all properties to child widgets', (tester) async {
      // --- Test properties for JokeTextCard ---
      const textJoke = Joke(id: 't1', setupText: 's', punchlineText: 'p');
      await tester.pumpWidget(createTestWidget(
        const JokeCard(
          joke: textJoke,
          index: 1,
          isAdminMode: true, // This should be ignored by JokeTextCard but shouldn't break it
          topRightBadgeText: 'TextBadge',
          jokeContext: 'test',
        ),
      ));

      final textCard = tester.widget<JokeTextCard>(find.byType(JokeTextCard));
      expect(textCard.joke, textJoke);
      expect(textCard.index, 1);
      expect(textCard.overlayBadgeText, 'TextBadge');
      expect(find.text('TextBadge'), findsOneWidget);

      // --- Test properties for JokeImageCarousel ---
      const imageJoke = Joke(
        id: 'i1',
        setupText: 's',
        punchlineText: 'p',
        setupImageUrl: 'https://ex/s.jpg',
        punchlineImageUrl: 'https://ex/p.jpg',
      );
      await tester.pumpWidget(createTestWidget(
        const JokeCard(
          joke: imageJoke,
          index: 2,
          isAdminMode: true,
          showNumSaves: true,
          showNumShares: true,
          topRightBadgeText: 'ImageBadge',
          jokeContext: 'test',
        ),
      ));

      final imageCarousel = tester.widget<JokeImageCarousel>(find.byType(JokeImageCarousel));
      expect(imageCarousel.joke, imageJoke);
      expect(imageCarousel.index, 2);
      expect(imageCarousel.isAdminMode, isTrue);
      expect(imageCarousel.showNumSaves, isTrue);
      expect(imageCarousel.showNumShares, isTrue);
      expect(imageCarousel.overlayBadgeText, 'ImageBadge');
      expect(find.text('ImageBadge'), findsOneWidget);
    });
  });
}