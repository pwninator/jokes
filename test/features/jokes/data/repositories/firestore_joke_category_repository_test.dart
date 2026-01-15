import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_category_repository.dart';

class _NoopPerformanceService implements PerformanceService {
  @override
  void dropNamedTrace({required TraceName name, String? key}) {}

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {}

  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {}

  @override
  void stopNamedTrace({required TraceName name, String? key}) {}
}

void main() {
  group('FirestoreJokeCategoryRepository', () {
    late FakeFirebaseFirestore firestore;
    late FirestoreJokeCategoryRepository repository;
    late PerformanceService perf;

    setUp(() {
      firestore = FakeFirebaseFirestore();
      perf = _NoopPerformanceService();
      repository = FirestoreJokeCategoryRepository(
        firestore: firestore,
        perf: perf,
      );
    });

    test('upsertCategory strips firestore prefix when writing', () async {
      final category = JokeCategory(
        id: '${JokeCategory.firestorePrefix}cats',
        displayName: 'Cats',
        jokeDescriptionQuery: 'cats',
        imageDescription: 'Images of cats',
        state: JokeCategoryState.approved,
        type: CategoryType.firestore,
      );

      await repository.upsertCategory(category);

      final doc = await firestore
          .collection('joke_categories')
          .doc('cats')
          .get();
      expect(doc.exists, isTrue);
      expect(doc.data()?['display_name'], 'Cats');
      expect(doc.data()?['state'], JokeCategoryState.approved.value);
    });

    test('watchCategory handles prefixed ids', () async {
      await firestore.collection('joke_categories').doc('dogs').set({
        'display_name': 'Dogs',
        'joke_description_query': 'dogs',
        'image_description': 'Images of dogs',
        'image_url': 'https://example.com/dog.png',
        'state': JokeCategoryState.proposed.value,
      });

      final category = await repository
          .watchCategory('${JokeCategory.firestorePrefix}dogs')
          .first;

      expect(category, isNotNull);
      expect(category!.id, '${JokeCategory.firestorePrefix}dogs');
      expect(category.displayName, 'Dogs');
      expect(category.imageUrl, 'https://example.com/dog.png');
    });

    test('deleteCategory removes prefixed documents', () async {
      await firestore.collection('joke_categories').doc('delete-me').set({
        'display_name': 'Delete Me',
        'state': JokeCategoryState.rejected.value,
      });

      await repository.deleteCategory(
        '${JokeCategory.firestorePrefix}delete-me',
      );

      final doc = await firestore
          .collection('joke_categories')
          .doc('delete-me')
          .get();
      expect(doc.exists, isFalse);
    });

    test('watchCategoryImages reads using stripped prefix', () async {
      await firestore.collection('joke_categories').doc('imgs').set({
        'display_name': 'Images',
        'state': JokeCategoryState.proposed.value,
        'all_image_urls': [
          'https://example.com/one.png',
          'https://example.com/two.png',
        ],
      });

      final images = await repository
          .watchCategoryImages('${JokeCategory.firestorePrefix}imgs')
          .first;

      expect(images, [
        'https://example.com/one.png',
        'https://example.com/two.png',
      ]);
    });

    test('addImageToCategory strips prefix before writing', () async {
      await firestore.collection('joke_categories').doc('add-image').set({
        'display_name': 'Add Image',
        'state': JokeCategoryState.proposed.value,
        'all_image_urls': [],
      });

      await repository.addImageToCategory(
        '${JokeCategory.firestorePrefix}add-image',
        'https://example.com/new.png',
      );

      final doc = await firestore
          .collection('joke_categories')
          .doc('add-image')
          .get();
      expect(doc.data()?['all_image_urls'], ['https://example.com/new.png']);
    });

    test('deleteImageFromCategory strips prefix before updating', () async {
      await firestore.collection('joke_categories').doc('remove-image').set({
        'display_name': 'Remove Image',
        'state': JokeCategoryState.proposed.value,
        'all_image_urls': [
          'https://example.com/keep.png',
          'https://example.com/remove.png',
        ],
      });

      await repository.deleteImageFromCategory(
        '${JokeCategory.firestorePrefix}remove-image',
        'https://example.com/remove.png',
      );

      final doc = await firestore
          .collection('joke_categories')
          .doc('remove-image')
          .get();
      expect(doc.data()?['all_image_urls'], ['https://example.com/keep.png']);
    });

    test('getCachedCategoryJokes returns empty when cache doc missing',
        () async {
      final result = await repository.getCachedCategoryJokes('animals');
      expect(result, isEmpty);
    });

    test('getCachedCategoryJokes returns empty when cache has no jokes field',
        () async {
      await firestore
          .collection('joke_categories')
          .doc('animals')
          .collection('category_jokes')
          .doc('cache')
          .set({'other': 1});

      final result = await repository.getCachedCategoryJokes('animals');
      expect(result, isEmpty);
    });

    test('getCachedCategoryJokes parses jokes list and filters invalid entries',
        () async {
      await firestore
          .collection('joke_categories')
          .doc('animals')
          .collection('category_jokes')
          .doc('cache')
          .set({
        'jokes': [
          {
            'key': 'j1',
            'setup_text': 'Why did the chicken cross the road?',
            'punchline_text': 'To get to the other side!',
            'setup_image_url': 's1',
            'punchline_image_url': 'p1',
          },
          {'key': ''}, // invalid: blank id
          'not-a-map', // invalid type
          {
            'key': 'j2',
            'setup_text': 'What do you call a fake noodle?',
            'punchline_text': 'An impasta!',
            // image fields optional
          },
        ],
      });

      final result = await repository.getCachedCategoryJokes('animals');
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

    test('getCachedCategoryJokes handles prefixed firestore id', () async {
      // When a JokeCategory has id starting with prefix, repository strips it.
      await firestore
          .collection('joke_categories')
          .doc('sports')
          .collection('category_jokes')
          .doc('cache')
          .set({
        'jokes': [
          {'key': 'kobe'},
        ],
      });

      // Pass category id with prefix
      final result =
          await repository.getCachedCategoryJokes('firestore:sports');
      expect(result.length, 1);
      expect(result.first.jokeId, 'kobe');
    });
  });
}
