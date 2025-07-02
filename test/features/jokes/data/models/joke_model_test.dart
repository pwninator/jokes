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
      expect(
        tJokeModel.punchlineText,
        'Because he was outstanding in his field!',
      );
      expect(tJokeModel.setupImageUrl, null);
      expect(tJokeModel.punchlineImageUrl, null);
      expect(tJokeModel.setupImageDescription, null);
      expect(tJokeModel.punchlineImageDescription, null);
      expect(tJokeModel.generationMetadata, null);
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
        'setup_image_description': null,
        'punchline_image_description': null,
        'generation_metadata': null,
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
        'setup_image_description': null,
        'punchline_image_description': null,
        'generation_metadata': null,
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
      expect(result.generationMetadata, null);
    });

    test(
      'copyWith should return the same model if no parameters are provided',
      () {
        // act
        final result = tJokeModel.copyWith();
        // assert
        expect(result, tJokeModel);
      },
    );

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
      expect(
        result['punchline_image_url'],
        'https://example.com/punchline.jpg',
      );
      expect(jokeWithImages.setupImageUrl, 'https://example.com/setup.jpg');
      expect(
        jokeWithImages.punchlineImageUrl,
        'https://example.com/punchline.jpg',
      );
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

    test('should handle image description fields correctly', () {
      // arrange
      const jokeWithImageDescriptions = Joke(
        id: '1',
        setupText: 'Why did the scarecrow win an award?',
        punchlineText: 'Because he was outstanding in his field!',
        setupImageDescription: 'A scarecrow standing in a field',
        punchlineImageDescription: 'The scarecrow receiving an award',
      );

      // act
      final result = jokeWithImageDescriptions.toMap();

      // assert
      expect(
        result['setup_image_description'],
        'A scarecrow standing in a field',
      );
      expect(
        result['punchline_image_description'],
        'The scarecrow receiving an award',
      );
      expect(
        jokeWithImageDescriptions.setupImageDescription,
        'A scarecrow standing in a field',
      );
      expect(
        jokeWithImageDescriptions.punchlineImageDescription,
        'The scarecrow receiving an award',
      );
    });

    test('should create joke from map with image descriptions', () {
      // arrange
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'setup_image_description': 'A scarecrow standing in a field',
        'punchline_image_description': 'The scarecrow receiving an award',
      };

      // act
      final result = Joke.fromMap(jsonMap, '1');

      // assert
      expect(result.setupImageDescription, 'A scarecrow standing in a field');
      expect(
        result.punchlineImageDescription,
        'The scarecrow receiving an award',
      );
    });

    test('should handle partial image descriptions', () {
      // arrange
      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'setup_image_description': 'A scarecrow standing in a field',
        // punchline_image_description is null
      };

      // act
      final result = Joke.fromMap(jsonMap, '1');

      // assert
      expect(result.setupImageDescription, 'A scarecrow standing in a field');
      expect(result.punchlineImageDescription, null);
    });

    test('should handle copyWith with image descriptions', () {
      // act
      final result = tJokeModel.copyWith(
        setupImageDescription: 'Updated setup description',
        punchlineImageDescription: 'Updated punchline description',
      );

      // assert
      expect(result.setupImageDescription, 'Updated setup description');
      expect(result.punchlineImageDescription, 'Updated punchline description');
      expect(result.id, tJokeModel.id);
      expect(result.setupText, tJokeModel.setupText);
      expect(result.punchlineText, tJokeModel.punchlineText);
    });

    test('should compare jokes with image descriptions correctly', () {
      // arrange
      const joke1 = Joke(
        id: '1',
        setupText: 'test',
        punchlineText: 'test',
        setupImageDescription: 'desc1',
        punchlineImageDescription: 'desc2',
      );
      const joke2 = Joke(
        id: '1',
        setupText: 'test',
        punchlineText: 'test',
        setupImageDescription: 'desc1',
        punchlineImageDescription: 'desc2',
      );
      const joke3 = Joke(
        id: '1',
        setupText: 'test',
        punchlineText: 'test',
        setupImageDescription: 'different',
        punchlineImageDescription: 'desc2',
      );

      // assert
      expect(joke1, joke2); // Same descriptions
      expect(joke1, isNot(joke3)); // Different descriptions
      expect(joke1.hashCode, joke2.hashCode);
      expect(joke1.hashCode, isNot(joke3.hashCode));
    });

    test('should handle generation metadata correctly', () {
      // arrange
      final testMetadata = {
        'model': 'gpt-4',
        'timestamp': '2024-01-01T00:00:00Z',
        'parameters': {'temperature': 0.7, 'max_tokens': 150},
      };

      final jokeWithMetadata = Joke(
        id: '1',
        setupText: 'Why did the scarecrow win an award?',
        punchlineText: 'Because he was outstanding in his field!',
        generationMetadata: testMetadata,
      );

      // act
      final result = jokeWithMetadata.toMap();

      // assert
      expect(result['generation_metadata'], testMetadata);
      expect(jokeWithMetadata.generationMetadata, testMetadata);
    });

    test('should create joke from map with generation metadata', () {
      // arrange
      final testMetadata = {
        'model': 'gpt-4',
        'timestamp': '2024-01-01T00:00:00Z',
      };

      final Map<String, dynamic> jsonMap = {
        'setup_text': 'Why did the scarecrow win an award?',
        'punchline_text': 'Because he was outstanding in his field!',
        'generation_metadata': testMetadata,
      };

      // act
      final result = Joke.fromMap(jsonMap, '1');

      // assert
      expect(result.generationMetadata, testMetadata);
    });

    test('should handle copyWith with generation metadata', () {
      // arrange
      final testMetadata = {
        'model': 'gpt-4',
        'timestamp': '2024-01-01T00:00:00Z',
      };

      // act
      final result = tJokeModel.copyWith(generationMetadata: testMetadata);

      // assert
      expect(result.generationMetadata, testMetadata);
      expect(result.id, tJokeModel.id);
      expect(result.setupText, tJokeModel.setupText);
      expect(result.punchlineText, tJokeModel.punchlineText);
    });

    test('should compare jokes with generation metadata correctly', () {
      // arrange
      const metadata1 = {'model': 'gpt-4'};
      const metadata2 = {'model': 'gpt-4'};
      const metadata3 = {'model': 'gpt-3.5'};

      final joke1 = tJokeModel.copyWith(generationMetadata: metadata1);
      final joke2 = tJokeModel.copyWith(generationMetadata: metadata2);
      final joke3 = tJokeModel.copyWith(generationMetadata: metadata3);

      // assert
      expect(joke1, joke2); // Same metadata content
      expect(joke1, isNot(joke3)); // Different metadata content
      expect(joke1.hashCode, joke2.hashCode);
      expect(joke1.hashCode, isNot(joke3.hashCode));
    });
  });
}
