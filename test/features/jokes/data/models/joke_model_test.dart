import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

void main() {
  group('Joke Model Tests', () {
    const tJokeModel = Joke(
      id: '1',
      setupText: 'Why did the scarecrow win an award?',
      punchlineText: 'Because he was outstanding in his field!',
    );

    test('should create a valid model', () {
      expect(tJokeModel.id, '1');
      expect(tJokeModel.setupText, 'Why did the scarecrow win an award?');
      expect(tJokeModel.punchlineText, 'Because he was outstanding in his field!');
      expect(tJokeModel.setupImageUrl, null);
      expect(tJokeModel.punchlineImageUrl, null);
    });

    test('should correctly serialize to map', () {
      // act
      final result = tJokeModel.toMap();
      // assert
      final expected = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'setup_image_url': null,
        'punchline_image_url': null,
      };
      expect(result, expected);
    });

    test('should correctly deserialize from map', () {
      // arrange
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'setup_image_url': null,
        'punchline_image_url': null,
      };
      // act
      final result = Joke.fromMap(jsonMap, '1');
      // assert
      expect(result, tJokeModel);
    });

    test('should return a valid model with updated parameters', () {
      // act
      final result = tJokeModel.copyWith(
        setupText: 'Updated setup',
        punchlineText: 'Updated punchline',
      );
      // assert
      expect(result.id, '1');
      expect(result.setupText, 'Updated setup');
      expect(result.punchlineText, 'Updated punchline');
    });

    test('copyWith should return the same model if no parameters are provided', () {
      // act
      final result = tJokeModel.copyWith();
      // assert
      expect(result, tJokeModel);
    });

    test('should implement props for value comparison', () {
      expect(
        tJokeModel,
        const Joke(
          id: '1',
          setupText: 'Why did the scarecrow win an award?',
          punchlineText: 'Because he was outstanding in his field!',
        ),
      );
    });

    test('hashCode should be consistent', () {
      final joke1 = const Joke(id: '1', setupText: 'a', punchlineText: 'b');
      final joke2 = const Joke(id: '1', setupText: 'a', punchlineText: 'b');
      final joke3 = const Joke(id: '2', setupText: 'a', punchlineText: 'b');
      expect(joke1.hashCode, joke2.hashCode);
      expect(joke1.hashCode, isNot(joke3.hashCode));
    });

    test('should handle image URL fields correctly', () {
      // arrange
      const jokeWithImages = Joke(
        id: '1',
        setupText: 'Why did the scarecrow win an award?',
        punchlineText: 'Because he was outstanding in his field!',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      // act
      final result = jokeWithImages.toMap();

      // assert
      expect(result['setup_image_url'], 'https://example.com/setup.jpg');
      expect(result['punchline_image_url'], 'https://example.com/punchline.jpg');
      expect(jokeWithImages.setupImageUrl, 'https://example.com/setup.jpg');
      expect(jokeWithImages.punchlineImageUrl, 'https://example.com/punchline.jpg');
    });

    test('should create joke from map with image URLs', () {
      // arrange
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'setup_image_url': 'https://example.com/setup.jpg',
        'punchline_image_url': 'https://example.com/punchline.jpg',
      };

      // act
      final result = Joke.fromMap(jsonMap, '1');

      // assert
      expect(result.setupImageUrl, 'https://example.com/setup.jpg');
      expect(result.punchlineImageUrl, 'https://example.com/punchline.jpg');
    });

    test('should handle partial image URLs', () {
      // arrange
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'setup_image_url': 'https://example.com/setup.jpg',
        // punchline_image_url is null
      };

      // act
      final result = Joke.fromMap(jsonMap, '1');

      // assert
      expect(result.setupImageUrl, 'https://example.com/setup.jpg');
      expect(result.punchlineImageUrl, null);
    });
  });
}
