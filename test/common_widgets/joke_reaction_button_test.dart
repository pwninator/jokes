import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/common_widgets/joke_reaction_button.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

void main() {
  group('JokeReactionType Integration Tests', () {
    test('all reaction types have required properties', () {
      for (final reactionType in JokeReactionType.values) {
        expect(reactionType.firestoreField, isNotNull);
        expect(reactionType.firestoreField, isNotEmpty);

        expect(reactionType.activeIcon, isNotNull);
        expect(reactionType.inactiveIcon, isNotNull);
        expect(reactionType.activeColor, isNotNull);

        expect(reactionType.prefsKey, isNotNull);
        expect(reactionType.prefsKey, isNotEmpty);

        expect(reactionType.label, isNotNull);
        expect(reactionType.label, isNotEmpty);

        // Icons should be different between active and inactive
        expect(
          reactionType.activeIcon,
          isNot(equals(reactionType.inactiveIcon)),
        );
      }
    });

    test('reaction types have unique firestore fields', () {
      final fields =
          JokeReactionType.values.map((e) => e.firestoreField).toSet();
      expect(fields.length, equals(JokeReactionType.values.length));
    });

    test('reaction types have unique preferences keys', () {
      final keys = JokeReactionType.values.map((e) => e.prefsKey).toSet();
      expect(keys.length, equals(JokeReactionType.values.length));
    });
  });

  group('Convenience Widget Tests', () {
    const testJokeId = 'test_joke_id';

    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    testWidgets('SaveJokeButton creates JokeReactionButton with save type', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(body: SaveJokeButton(jokeId: testJokeId)),
          ),
        ),
      );

      // Verify that a JokeReactionButton was created
      expect(find.byType(JokeReactionButton), findsOneWidget);

      // Get the widget and verify its properties
      final buttonWidget = tester.widget<JokeReactionButton>(
        find.byType(JokeReactionButton),
      );
      expect(buttonWidget.jokeId, equals(testJokeId));
      expect(buttonWidget.reactionType, equals(JokeReactionType.save));
      expect(buttonWidget.size, equals(24.0)); // default size
    });

    testWidgets('ShareJokeButton creates JokeReactionButton with share type', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(body: ShareJokeButton(jokeId: testJokeId)),
          ),
        ),
      );

      expect(find.byType(JokeReactionButton), findsOneWidget);

      final buttonWidget = tester.widget<JokeReactionButton>(
        find.byType(JokeReactionButton),
      );
      expect(buttonWidget.jokeId, equals(testJokeId));
      expect(buttonWidget.reactionType, equals(JokeReactionType.share));
    });

    testWidgets(
      'ThumbsUpJokeButton creates JokeReactionButton with thumbsUp type',
      (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            child: MaterialApp(
              home: Scaffold(body: ThumbsUpJokeButton(jokeId: testJokeId)),
            ),
          ),
        );

        expect(find.byType(JokeReactionButton), findsOneWidget);

        final buttonWidget = tester.widget<JokeReactionButton>(
          find.byType(JokeReactionButton),
        );
        expect(buttonWidget.jokeId, equals(testJokeId));
        expect(buttonWidget.reactionType, equals(JokeReactionType.thumbsUp));
      },
    );

    testWidgets(
      'ThumbsDownJokeButton creates JokeReactionButton with thumbsDown type',
      (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            child: MaterialApp(
              home: Scaffold(body: ThumbsDownJokeButton(jokeId: testJokeId)),
            ),
          ),
        );

        expect(find.byType(JokeReactionButton), findsOneWidget);

        final buttonWidget = tester.widget<JokeReactionButton>(
          find.byType(JokeReactionButton),
        );
        expect(buttonWidget.jokeId, equals(testJokeId));
        expect(buttonWidget.reactionType, equals(JokeReactionType.thumbsDown));
      },
    );

    testWidgets('convenience widgets pass through custom parameters', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: SaveJokeButton(jokeId: testJokeId, size: 32.0),
            ),
          ),
        ),
      );

      final buttonWidget = tester.widget<JokeReactionButton>(
        find.byType(JokeReactionButton),
      );
      expect(buttonWidget.size, equals(32.0));
    });
  });
}
