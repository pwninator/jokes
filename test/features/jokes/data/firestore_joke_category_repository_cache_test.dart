// Add tests for FirestoreJokeCategoryRepository.getCachedCategoryJokes

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_category_repository.dart';

void main() {
  group('FirestoreJokeCategoryRepository.getCachedCategoryJokes', () {
    late FirebaseFirestore fs;
    late FirestoreJokeCategoryRepository repo;

    setUp(() {
      fs = FakeFirebaseFirestore();
      repo = FirestoreJokeCategoryRepository(firestore: fs);
    });

    test('returns empty when cache doc missing', () async {
      final result = await repo.getCachedCategoryJokes('animals');
      expect(result, isEmpty);
    });

    test('returns empty when cache has no jokes field', () async {
      await fs
          .collection('joke_categories')
          .doc('animals')
          .collection('category_jokes')
          .doc('cache')
          .set({'other': 1});

      final result = await repo.getCachedCategoryJokes('animals');
      expect(result, isEmpty);
    });

    test('parses jokes list and filters invalid entries', () async {
      await fs
          .collection('joke_categories')
          .doc('animals')
          .collection('category_jokes')
          .doc('cache')
          .set({
            'jokes': [
              {
                'joke_id': 'j1',
                'setup': 'Why did the chicken cross the road?',
                'punchline': 'To get to the other side!',
                'setup_image_url': 's1',
                'punchline_image_url': 'p1',
              },
              {'joke_id': ''}, // invalid: blank id
              'not-a-map', // invalid type
              {
                'joke_id': 'j2',
                'setup': 'What do you call a fake noodle?',
                'punchline': 'An impasta!',
                // image fields optional
              },
            ],
          });

      final result = await repo.getCachedCategoryJokes('animals');
      expect(result.length, 2);
      expect(result.first.jokeId, 'j1');
      expect(result.first.setupText, 'Why did the chicken cross the road?');
      expect(result.first.punchlineText, 'To get to the other side!');
      expect(result.first.setupImageUrl, 's1');
      expect(result.first.punchlineImageUrl, 'p1');
      expect(result.last.jokeId, 'j2');
      expect(result.last.setupText, 'What do you call a fake noodle?');
      expect(result.last.punchlineText, 'An impasta!');
      expect(result.last.setupImageUrl, isNull);
      expect(result.last.punchlineImageUrl, isNull);
    });

    test('handles prefixed firestore id', () async {
      // When a JokeCategory has id starting with prefix, repository strips it.
      await fs
          .collection('joke_categories')
          .doc('sports')
          .collection('category_jokes')
          .doc('cache')
          .set({
            'jokes': [
              {'joke_id': 'kobe'},
            ],
          });

      // Pass category id with prefix
      final result = await repo.getCachedCategoryJokes('firestore:sports');
      expect(result.length, 1);
      expect(result.first.jokeId, 'kobe');
    });
  });
}
