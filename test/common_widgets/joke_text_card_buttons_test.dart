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

  group('JokeTextCard', () {
    const textJoke = Joke(
      id: 'ad1',
      setupText: 'Setup',
      punchlineText: 'Punch',
      setupImageUrl: null,
      punchlineImageUrl: null,
    );

    testWidgets('shows or hides admin buttons based on isAdminMode flag', (
      tester,
    ) async {
      // --- Test 1: Non-admin mode should NOT show admin buttons ---
      await tester.pumpWidget(createTestWidget(
        child: const JokeCard(
          joke: textJoke,
          jokeContext: 'test',
          isAdminMode: false, // Explicitly false
        ),
      ));

      // Ensure we're testing the right widget
      expect(find.byType(JokeTextCard), findsOneWidget);

      // Verify no admin buttons are present
      expect(find.byKey(const Key('delete-joke-button')), findsNothing,
          reason: 'Delete button should not be visible in non-admin mode');
      expect(find.byKey(const Key('edit-joke-button')), findsNothing,
          reason: 'Edit button should not be visible in non-admin mode');
      expect(find.byKey(const Key('populate-joke-button')), findsNothing,
          reason: 'Populate button should not be visible in non-admin mode');

      // --- Test 2: Admin mode SHOULD show admin buttons ---
      await tester.pumpWidget(createTestWidget(
        child: const JokeCard(
          joke: textJoke,
          jokeContext: 'test',
          isAdminMode: true,
        ),
      ));

      // All three admin buttons should now be visible
      expect(find.byKey(const Key('delete-joke-button')), findsOneWidget,
          reason: 'Delete button should be visible in admin mode');
      expect(find.byKey(const Key('edit-joke-button')), findsOneWidget,
          reason: 'Edit button should be visible in admin mode');
      expect(find.byKey(const Key('populate-joke-button')), findsOneWidget,
          reason: 'Populate button should be visible in admin mode');
    });
  });
}