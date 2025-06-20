import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

void main() {
  group('Joke Model', () {
    const tJokeModel = Joke(
      id: '1',
      setupText: 'Why did the scarecrow win an award?',
      punchlineText: 'Because he was outstanding in his field!',
    );

    // This map should reflect the output of toMap(), which uses snake_case for Firestore.
    const tJokeMap = {
      'setup_text': 'Why did the scarecrow win an award?',
      'punchline_text': 'Because he was outstanding in his field!',
      'image_url': null,
    };

    test('should be a subclass of Joke entity', () {
      // This test might be more relevant if you have an abstract Joke entity.
      // For now, it's just a class, so this test is trivial.
      expect(tJokeModel, isA<Joke>());
    });

    test('fromMap should return a valid model', () {
      // arrange
      // This map should reflect what Firestore sends, which is snake_case.
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
      };
      // act
      final result = Joke.fromMap(jsonMap, '1');
      // assert
      expect(result, tJokeModel);
    });

    test('toMap should return a JSON map containing the proper data', () {
      // act
      final result = tJokeModel.toMap();
      // assert
      expect(result, tJokeMap);
    });

    test('copyWith should return a new model with updated data', () {
      // act
      final result = tJokeModel.copyWith(punchlineText: 'He was just too good.');
      // assert
      expect(result.id, '1');
      expect(result.setupText, 'Why did the scarecrow win an award?');
      expect(result.punchlineText, 'He was just too good.');
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

    test('should handle imageUrl field correctly', () {
      // arrange
      const jokeWithImage = Joke(
        id: '1',
        setupText: 'Why did the scarecrow win an award?',
        punchlineText: 'Because he was outstanding in his field!',
        imageUrl: 'https://example.com/image.jpg',
      );

      // act
      final result = jokeWithImage.toMap();

      // assert
      expect(result['image_url'], 'https://example.com/image.jpg');
      expect(jokeWithImage.imageUrl, 'https://example.com/image.jpg');
    });

    test('should create joke from map with imageUrl', () {
      // arrange
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'image_url': 'https://example.com/image.jpg',
      };

      // act
      final result = Joke.fromMap(jsonMap, '1');

      // assert
      expect(result.imageUrl, 'https://example.com/image.jpg');
    });
  });
}
