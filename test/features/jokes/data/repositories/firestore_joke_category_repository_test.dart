import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_category_repository.dart';

void main() {
  group('FirestoreJokeCategoryRepository', () {
    late FakeFirebaseFirestore firestore;
    late FirestoreJokeCategoryRepository repository;

    setUp(() {
      firestore = FakeFirebaseFirestore();
      repository = FirestoreJokeCategoryRepository(firestore: firestore);
    });

    test('upsertCategory strips firestore prefix when writing', () async {
      final category = JokeCategory(
        id: '${JokeCategory.firestorePrefix}cats',
        displayName: 'Cats',
        jokeDescriptionQuery: 'cats',
        imageDescription: 'Images of cats',
        state: JokeCategoryState.approved,
        type: CategoryType.search,
      );

      await repository.upsertCategory(category);

      final doc =
          await firestore.collection('joke_categories').doc('cats').get();
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

      expect(images, ['https://example.com/one.png', 'https://example.com/two.png']);
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
  });
}

