import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

void main() {
  group('JokeCategory seasonal', () {
    test('creates seasonal category with valid seasonalValue', () {
      final c = JokeCategory(
        id: 's1',
        displayName: 'Halloween',
        type: CategoryType.seasonal,
        seasonalValue: 'Halloween',
      );
      expect(c.type, CategoryType.seasonal);
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

    test('creates search category with non-empty query', () {
      final c = JokeCategory(
        id: 'q1',
        displayName: 'Search Cats',
        type: CategoryType.search,
        jokeDescriptionQuery: 'cats',
      );
      expect(c.type, CategoryType.search);
      expect(c.jokeDescriptionQuery, 'cats');
    });

    test('throws when seasonal with empty seasonalValue', () {
      expect(
        () => JokeCategory(
          id: 's2',
          displayName: 'Bad seasonal',
          type: CategoryType.seasonal,
          seasonalValue: '',
        ),
        throwsA(isA<AssertionError>()),
      );
    });

    test('throws when seasonal with search query provided', () {
      expect(
        () => JokeCategory(
          id: 's3',
          displayName: 'Bad seasonal',
          type: CategoryType.seasonal,
          seasonalValue: 'Halloween',
          jokeDescriptionQuery: 'should not be set',
        ),
        throwsA(isA<AssertionError>()),
      );
    });

    test('throws when search without non-empty query', () {
      expect(
        () => JokeCategory(
          id: 'q2',
          displayName: 'Bad search',
          type: CategoryType.search,
          jokeDescriptionQuery: '',
        ),
        throwsA(isA<AssertionError>()),
      );
    });
  });

  group('JokeCategory firestore helpers', () {
    test('firestoreDocumentId strips prefix', () {
      final category = JokeCategory(
        id: '${JokeCategory.firestorePrefix}abc',
        displayName: 'Firestore Cat',
        type: CategoryType.search,
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
  });
}
