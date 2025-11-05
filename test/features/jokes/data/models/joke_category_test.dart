import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

void main() {
  group('JokeCategory seasonal', () {
    test('creates firestore category with valid seasonalValue', () {
      final c = JokeCategory(
        id: 's1',
        displayName: 'Halloween',
        type: CategoryType.firestore,
        seasonalValue: 'Halloween',
      );
      expect(c.type, CategoryType.firestore);
      expect(c.seasonalValue, 'Halloween');
    });

    test('creates popular category without seasonalValue', () {
      final c = JokeCategory(
        id: 'p1',
        displayName: 'Popular',
        type: CategoryType.popular,
      );
      expect(c.type, CategoryType.popular);
      expect(c.seasonalValue, isNull);
    });

    test('creates firestore category with non-empty query', () {
      final c = JokeCategory(
        id: 'q1',
        displayName: 'Search Cats',
        type: CategoryType.firestore,
        jokeDescriptionQuery: 'cats',
      );
      expect(c.type, CategoryType.firestore);
      expect(c.jokeDescriptionQuery, 'cats');
    });

    test('creates firestore category with seasonal value', () {
      final c = JokeCategory(
        id: 's2',
        displayName: 'Halloween',
        type: CategoryType.firestore,
        seasonalValue: 'Halloween',
      );
      expect(c.type, CategoryType.firestore);
      expect(c.seasonalValue, 'Halloween');
      expect(c.jokeDescriptionQuery, isNull);
    });

    test(
      'creates firestore category with seasonal value and query (query ignored)',
      () {
        final c = JokeCategory(
          id: 's3',
          displayName: 'Halloween',
          type: CategoryType.firestore,
          seasonalValue: 'Halloween',
          jokeDescriptionQuery: 'should be ignored',
        );
        expect(c.type, CategoryType.firestore);
        expect(c.seasonalValue, 'Halloween');
        expect(c.jokeDescriptionQuery, 'should be ignored');
      },
    );
  });

  group('JokeCategory firestore helpers', () {
    test('firestoreDocumentId strips prefix', () {
      final category = JokeCategory(
        id: '${JokeCategory.firestorePrefix}abc',
        displayName: 'Firestore Cat',
        type: CategoryType.firestore,
        jokeDescriptionQuery: 'cats',
      );

      expect(category.isFirestoreCategory, isTrue);
      expect(category.firestoreDocumentId, 'abc');
    });

    test('firestore helpers leave non-prefixed ids unchanged', () {
      final category = JokeCategory(
        id: 'programmatic:popular',
        displayName: 'Popular',
        type: CategoryType.popular,
      );

      expect(category.isFirestoreCategory, isFalse);
      expect(category.firestoreDocumentId, 'programmatic:popular');
    });

    test('fromMap returns search category when query provided', () {
      final map = {
        'display_name': 'Cats',
        'joke_description_query': 'cats',
        'state': 'APPROVED',
      };

      final category = JokeCategory.fromMap(map, 'cats');

      expect(category.type, CategoryType.firestore);
      expect(category.jokeDescriptionQuery, 'cats');
      expect(category.seasonalValue, isNull);
    });

    test('fromMap returns firestore category when seasonal name provided', () {
      final map = {
        'display_name': 'Halloween',
        'seasonal_name': 'Halloween',
        'state': 'APPROVED',
        'joke_description_query': 'should be ignored',
      };

      final category = JokeCategory.fromMap(map, 'halloween');

      expect(category.type, CategoryType.firestore);
      expect(category.seasonalValue, 'Halloween');
      expect(category.jokeDescriptionQuery, isNull);
    });
  });
}
