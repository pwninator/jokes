import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/firebase_mocks.dart';

void main() {
  Widget createTestWidget({
    required Widget child,
    List<Override> additionalOverrides = const [],
  }) {
    return ProviderScope(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: additionalOverrides,
      ),
      child: MaterialApp(
        theme: lightTheme,
        home: Scaffold(body: child),
      ),
    );
  }

  group('JokeTextCard admin/non-admin action buttons', () {
    testWidgets('non-admin shows only regenerate images icon button', (
      tester,
    ) async {
      const joke = Joke(
        id: 'na1',
        setupText: 'Setup',
        punchlineText: 'Punch',
        setupImageUrl: null,
        punchlineImageUrl: null,
      );

      // Render via JokeCard to reflect real usage
      const widget = JokeCard(joke: joke, jokeContext: 'test');

      await tester.pumpWidget(createTestWidget(child: widget));

      // Ensure text card is being used
      expect(find.byType(JokeTextCard), findsOneWidget);

      // Only the regenerate button should exist
      expect(find.byKey(const Key('regenerate-images-button')), findsOneWidget);
      expect(find.byKey(const Key('delete-joke-button')), findsNothing);
      expect(find.byKey(const Key('edit-joke-button')), findsNothing);
    });

    testWidgets('admin shows delete, edit, and regenerate icon buttons', (
      tester,
    ) async {
      const joke = Joke(
        id: 'ad1',
        setupText: 'Setup',
        punchlineText: 'Punch',
        setupImageUrl: null,
        punchlineImageUrl: null,
      );

      const widget = JokeCard(
        joke: joke,
        jokeContext: 'test',
        isAdminMode: true,
      );

      await tester.pumpWidget(createTestWidget(child: widget));

      // Ensure text card is being used
      expect(find.byType(JokeTextCard), findsOneWidget);

      // All three admin buttons should exist
      expect(find.byKey(const Key('delete-joke-button')), findsOneWidget);
      expect(find.byKey(const Key('edit-joke-button')), findsOneWidget);
      expect(find.byKey(const Key('regenerate-images-button')), findsOneWidget);
    });
  });
}
