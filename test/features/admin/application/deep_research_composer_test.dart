import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/application/deep_research_composer.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

void main() {
  group('composeDeepResearchPrompt', () {
    const template =
        'Topic: {topic}\n{positive_examples}\n---\n{negative_examples}';

    Joke buildJoke({
      required String id,
      required String setup,
      required String punchline,
      required JokeState state,
    }) {
      return Joke(
        id: id,
        setupText: setup,
        punchlineText: punchline,
        adminRating: JokeAdminRating.unreviewed,
        state: state,
      );
    }

    test(
      'includes positives and negatives with headers and trims whitespace',
      () {
        final jokes = [
          buildJoke(
            id: '1',
            setup: '  Setup A  ',
            punchline: ' Punchline A ',
            state: JokeState.approved,
          ),
          buildJoke(
            id: '2',
            setup: 'Setup B',
            punchline: 'Punchline B',
            state: JokeState.published,
          ),
          buildJoke(
            id: '3',
            setup: 'Setup C',
            punchline: 'Punchline C',
            state: JokeState.rejected,
          ),
        ];

        final result = composeDeepResearchPrompt(
          jokes: jokes,
          template: template,
          topic: 'penguins',
        );
        expect(result, contains('Topic: penguins'));
        expect(result, contains('Here are some examples of good jokes'));
        expect(result, contains('Here are some examples of bad jokes'));
        expect(result, contains('Setup A Punchline A'));
        expect(result, contains('Setup B Punchline B'));
        expect(result, contains('Setup C Punchline C'));
      },
    );

    test('omits header if section empty', () {
      final jokes = [
        buildJoke(
          id: '1',
          setup: 'X',
          punchline: 'Y',
          state: JokeState.rejected,
        ),
      ];

      final result = composeDeepResearchPrompt(
        jokes: jokes,
        template: template,
        topic: 'penguins',
      );
      expect(result.contains('Here are some examples of good jokes'), isFalse);
      expect(result.contains('Here are some examples of bad jokes'), isTrue);
    });

    test('filters out jokes with empty parts', () {
      final jokes = [
        buildJoke(
          id: '1',
          setup: '',
          punchline: 'Y',
          state: JokeState.approved,
        ),
        buildJoke(
          id: '2',
          setup: 'X',
          punchline: '',
          state: JokeState.rejected,
        ),
      ];

      final result = composeDeepResearchPrompt(
        jokes: jokes,
        template: template,
        topic: 'penguins',
      );
      expect(result.contains('Here are some examples of good jokes'), isFalse);
      expect(result.contains('Here are some examples of bad jokes'), isFalse);
    });
  });
}
