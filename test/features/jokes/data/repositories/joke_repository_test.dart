import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

// Mock classes using mocktail
class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}

class MockCollectionReference extends Mock
    implements CollectionReference<Map<String, dynamic>> {}

class MockQuery extends Mock implements Query<Map<String, dynamic>> {}

class MockQuerySnapshot extends Mock
    implements QuerySnapshot<Map<String, dynamic>> {}

class MockDocumentSnapshot extends Mock
    implements QueryDocumentSnapshot<Map<String, dynamic>> {}

void main() {
  group('JokeRepository', () {
    late JokeRepository repository;
    late MockFirebaseFirestore mockFirestore;
    late MockCollectionReference mockCollectionReference;
    late MockQuery mockQuery;
    late MockQuerySnapshot mockQuerySnapshot;

    setUp(() {
      mockFirestore = MockFirebaseFirestore();
      mockCollectionReference = MockCollectionReference();
      mockQuery = MockQuery();
      mockQuerySnapshot = MockQuerySnapshot();
      repository = JokeRepository(mockFirestore);

      // Set up the default behavior for the collection and query chain
      when(
        () => mockFirestore.collection(any()),
      ).thenReturn(mockCollectionReference);
      when(
        () => mockCollectionReference.orderBy(
          any(),
          descending: any(named: 'descending'),
        ),
      ).thenReturn(mockQuery);
      when(
        () => mockQuery.snapshots(),
      ).thenAnswer((_) => Stream.value(mockQuerySnapshot));
    });

    group('getJokes', () {
      test(
        'should return stream of jokes when collection is not empty',
        () async {
          // Create mock documents
          final mockDoc1 = MockDocumentSnapshot();
          final mockDoc2 = MockDocumentSnapshot();

          final joke1Data = {
            'setup_text': 'Setup 1',
            'punchline_text': 'Punchline 1',
            'setup_image_url': 'https://example.com/setup1.jpg',
            'punchline_image_url': 'https://example.com/punchline1.jpg',
          };

          final joke2Data = {
            'setup_text': 'Setup 2',
            'punchline_text': 'Punchline 2',
            'setup_image_url': 'https://example.com/setup2.jpg',
            'punchline_image_url': 'https://example.com/punchline2.jpg',
          };

          when(() => mockDoc1.data()).thenReturn(joke1Data);
          when(() => mockDoc1.id).thenReturn('1');
          when(() => mockDoc2.data()).thenReturn(joke2Data);
          when(() => mockDoc2.id).thenReturn('2');

          when(() => mockQuerySnapshot.docs).thenReturn([mockDoc1, mockDoc2]);

          final jokesStream = repository.getJokes();
          final jokes = await jokesStream.first;

          expect(jokes, hasLength(2));
          expect(jokes[0].id, '1');
          expect(jokes[0].setupText, 'Setup 1');
          expect(jokes[1].id, '2');
          expect(jokes[1].setupText, 'Setup 2');

          verify(() => mockFirestore.collection('jokes')).called(1);
          verify(
            () => mockCollectionReference.orderBy(
              'creation_time',
              descending: true,
            ),
          ).called(1);
          verify(() => mockQuery.snapshots()).called(1);
        },
      );

      test('should return empty stream when collection is empty', () async {
        when(() => mockQuerySnapshot.docs).thenReturn([]); // Empty list of docs

        final jokesStream = repository.getJokes();
        final jokes = await jokesStream.first;

        expect(jokes, isEmpty);
        verify(
          () => mockCollectionReference.orderBy(
            'creation_time',
            descending: true,
          ),
        ).called(1);
        verify(() => mockQuery.snapshots()).called(1);
      });

      test('should handle FirebaseException', () async {
        when(() => mockQuery.snapshots()).thenAnswer(
          (_) => Stream.error(
            FirebaseException(plugin: 'firestore', message: 'Test error'),
          ),
        );

        final jokesStream = repository.getJokes();

        expect(jokesStream, emitsError(isA<FirebaseException>()));
        verify(
          () => mockCollectionReference.orderBy(
            'creation_time',
            descending: true,
          ),
        ).called(1);
        verify(() => mockQuery.snapshots()).called(1);
      });
    });
  });
}
