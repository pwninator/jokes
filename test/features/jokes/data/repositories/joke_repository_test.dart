import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

// Mock classes using mocktail
class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}

class MockCollectionReference extends Mock
    implements CollectionReference<Map<String, dynamic>> {}

class MockDocumentReference extends Mock
    implements DocumentReference<Map<String, dynamic>> {}

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
    late MockDocumentReference mockDocumentReference;
    late MockQuery mockQuery;
    late MockQuerySnapshot mockQuerySnapshot;

    setUp(() {
      mockFirestore = MockFirebaseFirestore();
      mockCollectionReference = MockCollectionReference();
      mockDocumentReference = MockDocumentReference();
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

    group('updateJoke', () {
      setUp(() {
        // Set up document reference behavior
        when(
          () => mockCollectionReference.doc(any()),
        ).thenReturn(mockDocumentReference);
        when(
          () => mockDocumentReference.update(any()),
        ).thenAnswer((_) async => {});
      });

      test('should update joke with all fields', () async {
        const jokeId = 'test-joke-id';
        const setupText = 'Updated setup';
        const punchlineText = 'Updated punchline';
        const setupImageUrl = 'https://example.com/setup.jpg';
        const punchlineImageUrl = 'https://example.com/punchline.jpg';
        const setupImageDescription = 'Updated setup description';
        const punchlineImageDescription = 'Updated punchline description';

        await repository.updateJoke(
          jokeId: jokeId,
          setupText: setupText,
          punchlineText: punchlineText,
          setupImageUrl: setupImageUrl,
          punchlineImageUrl: punchlineImageUrl,
          setupImageDescription: setupImageDescription,
          punchlineImageDescription: punchlineImageDescription,
        );

        final expectedUpdateData = {
          'setup_text': setupText,
          'punchline_text': punchlineText,
          'setup_image_url': setupImageUrl,
          'punchline_image_url': punchlineImageUrl,
          'setup_image_description': setupImageDescription,
          'punchline_image_description': punchlineImageDescription,
        };

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(
          () => mockDocumentReference.update(expectedUpdateData),
        ).called(1);
      });

      test('should update joke with only required fields', () async {
        const jokeId = 'test-joke-id';
        const setupText = 'Updated setup';
        const punchlineText = 'Updated punchline';

        await repository.updateJoke(
          jokeId: jokeId,
          setupText: setupText,
          punchlineText: punchlineText,
        );

        final expectedUpdateData = {
          'setup_text': setupText,
          'punchline_text': punchlineText,
        };

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(
          () => mockDocumentReference.update(expectedUpdateData),
        ).called(1);
      });

      test('should update joke with partial optional fields', () async {
        const jokeId = 'test-joke-id';
        const setupText = 'Updated setup';
        const punchlineText = 'Updated punchline';
        const setupImageDescription = 'Only setup description';

        await repository.updateJoke(
          jokeId: jokeId,
          setupText: setupText,
          punchlineText: punchlineText,
          setupImageDescription: setupImageDescription,
        );

        final expectedUpdateData = {
          'setup_text': setupText,
          'punchline_text': punchlineText,
          'setup_image_description': setupImageDescription,
        };

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(
          () => mockDocumentReference.update(expectedUpdateData),
        ).called(1);
      });

      test('should propagate FirebaseException when update fails', () async {
        const jokeId = 'test-joke-id';
        const setupText = 'Updated setup';
        const punchlineText = 'Updated punchline';

        when(() => mockDocumentReference.update(any())).thenThrow(
          FirebaseException(plugin: 'firestore', message: 'Update failed'),
        );

        expect(
          () => repository.updateJoke(
            jokeId: jokeId,
            setupText: setupText,
            punchlineText: punchlineText,
          ),
          throwsA(isA<FirebaseException>()),
        );

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.update(any())).called(1);
      });
    });

    group('deleteJoke', () {
      setUp(() {
        // Set up document reference behavior
        when(
          () => mockCollectionReference.doc(any()),
        ).thenReturn(mockDocumentReference);
        when(
          () => mockDocumentReference.delete(),
        ).thenAnswer((_) async => {});
      });

      test('should delete joke successfully', () async {
        const jokeId = 'test-joke-id';

        await repository.deleteJoke(jokeId);

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.delete()).called(1);
      });

      test('should propagate FirebaseException when delete fails', () async {
        const jokeId = 'test-joke-id';

        when(() => mockDocumentReference.delete()).thenThrow(
          FirebaseException(plugin: 'firestore', message: 'Delete failed'),
        );

        expect(
          () => repository.deleteJoke(jokeId),
          throwsA(isA<FirebaseException>()),
        );

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.delete()).called(1);
      });
    });

    group('getJokeById', () {
      setUp(() {
        // Set up document reference behavior
        when(
          () => mockCollectionReference.doc(any()),
        ).thenReturn(mockDocumentReference);
      });

      test('should return joke when document exists', () async {
        const jokeId = 'test-joke-id';
        final jokeData = {
          'setup_text': 'Test setup',
          'punchline_text': 'Test punchline',
          'setup_image_url': 'https://example.com/setup.jpg',
          'punchline_image_url': 'https://example.com/punchline.jpg',
        };

        final mockDocSnapshot = MockDocumentSnapshot();
        when(() => mockDocSnapshot.exists).thenReturn(true);
        when(() => mockDocSnapshot.data()).thenReturn(jokeData);
        when(() => mockDocSnapshot.id).thenReturn(jokeId);
        when(() => mockDocumentReference.get()).thenAnswer(
          (_) async => mockDocSnapshot,
        );

        final result = await repository.getJokeById(jokeId);

        expect(result, isNotNull);
        expect(result!.id, jokeId);
        expect(result.setupText, 'Test setup');
        expect(result.punchlineText, 'Test punchline');

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.get()).called(1);
      });

      test('should return null when document does not exist', () async {
        const jokeId = 'non-existent-joke-id';

        final mockDocSnapshot = MockDocumentSnapshot();
        when(() => mockDocSnapshot.exists).thenReturn(false);
        when(() => mockDocumentReference.get()).thenAnswer(
          (_) async => mockDocSnapshot,
        );

        final result = await repository.getJokeById(jokeId);

        expect(result, isNull);

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.get()).called(1);
      });

      test('should throw exception when Firebase operation fails', () async {
        const jokeId = 'test-joke-id';

        when(() => mockDocumentReference.get()).thenThrow(
          FirebaseException(plugin: 'firestore', message: 'Get failed'),
        );

        expect(
          () => repository.getJokeById(jokeId),
          throwsA(isA<Exception>()),
        );

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.get()).called(1);
      });
    });

    group('getJokesByIds', () {
      late MockQuery mockWhereQuery;

      setUp(() {
        mockWhereQuery = MockQuery();
        when(() => mockCollectionReference.where(any(), whereIn: any(named: 'whereIn')))
            .thenReturn(mockWhereQuery);
        when(() => mockWhereQuery.get()).thenAnswer((_) async => mockQuerySnapshot);
      });

      test('should return empty list when jokeIds is empty', () async {
        final result = await repository.getJokesByIds([]);

        expect(result, isEmpty);
        verifyNever(() => mockFirestore.collection('jokes'));
      });

      test('should return jokes when documents exist', () async {
        final jokeIds = ['joke1', 'joke2'];
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
        when(() => mockDoc1.id).thenReturn('joke1');
        when(() => mockDoc2.data()).thenReturn(joke2Data);
        when(() => mockDoc2.id).thenReturn('joke2');

        when(() => mockQuerySnapshot.docs).thenReturn([mockDoc1, mockDoc2]);

        final result = await repository.getJokesByIds(jokeIds);

        expect(result, hasLength(2));
        expect(result[0].id, 'joke1');
        expect(result[0].setupText, 'Setup 1');
        expect(result[1].id, 'joke2');
        expect(result[1].setupText, 'Setup 2');

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.where(FieldPath.documentId, whereIn: jokeIds)).called(1);
        verify(() => mockWhereQuery.get()).called(1);
      });

      test('should handle batches larger than 10 items', () async {
        final jokeIds = List.generate(15, (i) => 'joke$i');
        
        // Create separate mock query snapshots for each batch
        final firstBatchSnapshot = MockQuerySnapshot();
        final secondBatchSnapshot = MockQuerySnapshot();
        
        final firstBatchDocs = List.generate(10, (i) {
          final mockDoc = MockDocumentSnapshot();
          when(() => mockDoc.data()).thenReturn({
            'setup_text': 'Setup $i',
            'punchline_text': 'Punchline $i',
          });
          when(() => mockDoc.id).thenReturn('joke$i');
          return mockDoc;
        });
        
        final secondBatchDocs = List.generate(5, (i) {
          final mockDoc = MockDocumentSnapshot();
          when(() => mockDoc.data()).thenReturn({
            'setup_text': 'Setup ${i + 10}',
            'punchline_text': 'Punchline ${i + 10}',
          });
          when(() => mockDoc.id).thenReturn('joke${i + 10}');
          return mockDoc;
        });

        // First batch (10 items)
        when(() => firstBatchSnapshot.docs).thenReturn(firstBatchDocs);
        final firstBatchQuery = MockQuery();
        when(() => mockCollectionReference.where(FieldPath.documentId, whereIn: jokeIds.take(10).toList()))
            .thenReturn(firstBatchQuery);
        when(() => firstBatchQuery.get()).thenAnswer((_) async => firstBatchSnapshot);

        // Second batch (5 items)
        when(() => secondBatchSnapshot.docs).thenReturn(secondBatchDocs);
        final secondBatchQuery = MockQuery();
        when(() => mockCollectionReference.where(FieldPath.documentId, whereIn: jokeIds.skip(10).take(5).toList()))
            .thenReturn(secondBatchQuery);
        when(() => secondBatchQuery.get()).thenAnswer((_) async => secondBatchSnapshot);

        final result = await repository.getJokesByIds(jokeIds);

        expect(result, hasLength(15));

        // Verify both batches were called
        verify(() => mockFirestore.collection('jokes')).called(2);
        verify(() => mockCollectionReference.where(FieldPath.documentId, whereIn: jokeIds.take(10).toList())).called(1);
        verify(() => mockCollectionReference.where(FieldPath.documentId, whereIn: jokeIds.skip(10).take(5).toList())).called(1);
      });

      test('should throw exception when Firebase operation fails', () async {
        final jokeIds = ['joke1', 'joke2'];

        when(() => mockWhereQuery.get()).thenThrow(
          FirebaseException(plugin: 'firestore', message: 'Batch get failed'),
        );

        expect(
          () => repository.getJokesByIds(jokeIds),
          throwsA(isA<Exception>()),
        );

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.where(FieldPath.documentId, whereIn: jokeIds)).called(1);
        verify(() => mockWhereQuery.get()).called(1);
      });
    });
  });
}
