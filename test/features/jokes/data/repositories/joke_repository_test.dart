// ignore_for_file: subtype_of_sealed_class
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

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
    late JokeRepository adminRepository;
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
      repository = JokeRepository(mockFirestore, false); // Non-admin
      adminRepository = JokeRepository(mockFirestore, true); // Admin

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
        when(() => mockDocumentReference.delete()).thenAnswer((_) async => {});
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

    group('getJokeByIdStream', () {
      setUp(() {
        // Set up document reference behavior
        when(
          () => mockCollectionReference.doc(any()),
        ).thenReturn(mockDocumentReference);
      });

      test('should return stream of joke when document exists', () async {
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
        when(
          () => mockDocumentReference.snapshots(),
        ).thenAnswer((_) => Stream.value(mockDocSnapshot));

        final jokeStream = repository.getJokeByIdStream(jokeId);
        final result = await jokeStream.first;

        expect(result, isNotNull);
        expect(result!.id, jokeId);
        expect(result.setupText, 'Test setup');
        expect(result.punchlineText, 'Test punchline');

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.snapshots()).called(1);
      });

      test(
        'should return stream of null when document does not exist',
        () async {
          const jokeId = 'non-existent-joke-id';

          final mockDocSnapshot = MockDocumentSnapshot();
          when(() => mockDocSnapshot.exists).thenReturn(false);
          when(
            () => mockDocumentReference.snapshots(),
          ).thenAnswer((_) => Stream.value(mockDocSnapshot));

          final jokeStream = repository.getJokeByIdStream(jokeId);
          final result = await jokeStream.first;

          expect(result, isNull);

          verify(() => mockFirestore.collection('jokes')).called(1);
          verify(() => mockCollectionReference.doc(jokeId)).called(1);
          verify(() => mockDocumentReference.snapshots()).called(1);
        },
      );

      test('should emit error when Firebase operation fails', () async {
        const jokeId = 'test-joke-id';

        when(() => mockDocumentReference.snapshots()).thenAnswer(
          (_) => Stream.error(
            FirebaseException(plugin: 'firestore', message: 'Get failed'),
          ),
        );

        final jokeStream = repository.getJokeByIdStream(jokeId);

        expect(jokeStream, emitsError(isA<FirebaseException>()));

        verify(() => mockFirestore.collection('jokes')).called(1);
        verify(() => mockCollectionReference.doc(jokeId)).called(1);
        verify(() => mockDocumentReference.snapshots()).called(1);
      });
    });

    group('getJokesByIds', () {
      late MockQuery mockWhereQuery;

      setUp(() {
        mockWhereQuery = MockQuery();
        when(
          () => mockCollectionReference.where(
            any(),
            whereIn: any(named: 'whereIn'),
          ),
        ).thenReturn(mockWhereQuery);
        when(
          () => mockWhereQuery.get(),
        ).thenAnswer((_) async => mockQuerySnapshot);
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
        verify(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds,
          ),
        ).called(1);
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
        when(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds.take(10).toList(),
          ),
        ).thenReturn(firstBatchQuery);
        when(
          () => firstBatchQuery.get(),
        ).thenAnswer((_) async => firstBatchSnapshot);

        // Second batch (5 items)
        when(() => secondBatchSnapshot.docs).thenReturn(secondBatchDocs);
        final secondBatchQuery = MockQuery();
        when(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds.skip(10).take(5).toList(),
          ),
        ).thenReturn(secondBatchQuery);
        when(
          () => secondBatchQuery.get(),
        ).thenAnswer((_) async => secondBatchSnapshot);

        final result = await repository.getJokesByIds(jokeIds);

        expect(result, hasLength(15));

        // Verify both batches were called
        verify(() => mockFirestore.collection('jokes')).called(2);
        verify(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds.take(10).toList(),
          ),
        ).called(1);
        verify(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds.skip(10).take(5).toList(),
          ),
        ).called(1);
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
        verify(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds,
          ),
        ).called(1);
        verify(() => mockWhereQuery.get()).called(1);
      });
    });

    // removed getFilteredJokeIds tests (method deleted in repository)

    group('admin reaction operations', () {
      late MockDocumentSnapshot mockDocSnapshot;

      setUp(() {
        when(
          () => mockCollectionReference.doc(any()),
        ).thenReturn(mockDocumentReference);
        when(
          () => mockDocumentReference.get(),
        ).thenAnswer((_) async => mockDocSnapshot);
        when(
          () => mockDocumentReference.update(any()),
        ).thenAnswer((_) async => {});
      });

      test(
        'admin updateReactionAndPopularity should not update Firestore and print debug message',
        () async {
          const jokeId = 'test-joke-id';
          mockDocSnapshot = MockDocumentSnapshot();
          when(
            () => mockDocSnapshot.data(),
          ).thenReturn({'num_saves': 5, 'num_shares': 3});

          await adminRepository.updateReactionAndPopularity(
            jokeId,
            JokeReactionType.save,
            1,
          );

          // Should not update Firestore
          verifyNever(() => mockDocumentReference.update(any()));
          // Should not read document data
          verifyNever(() => mockDocumentReference.get());
        },
      );

      test(
        'admin updateReactionAndPopularity with negative increment should not update Firestore and print debug message',
        () async {
          const jokeId = 'test-joke-id';
          mockDocSnapshot = MockDocumentSnapshot();
          when(
            () => mockDocSnapshot.data(),
          ).thenReturn({'num_saves': 5, 'num_shares': 3});

          await adminRepository.updateReactionAndPopularity(
            jokeId,
            JokeReactionType.save,
            -1,
          );

          // Should not update Firestore
          verifyNever(() => mockDocumentReference.update(any()));
          // Should not read document data
          verifyNever(() => mockDocumentReference.get());
        },
      );
    });

    group('reaction operations', () {
      late MockDocumentSnapshot mockDocSnapshot;

      setUp(() {
        when(
          () => mockCollectionReference.doc(any()),
        ).thenReturn(mockDocumentReference);
        when(
          () => mockDocumentReference.get(),
        ).thenAnswer((_) async => mockDocSnapshot);
        when(
          () => mockDocumentReference.update(any()),
        ).thenAnswer((_) async => {});
      });

      group('updateReactionAndPopularity', () {
        test(
          'should increment save reaction and update popularity score',
          () async {
            const jokeId = 'test-joke-id';
            mockDocSnapshot = MockDocumentSnapshot();
            when(
              () => mockDocSnapshot.data(),
            ).thenReturn({'num_saves': 5, 'num_shares': 3});

            await repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.save,
              1,
            );

            // popularity_score = (5+1) + (3 * 5) = 21
            verify(
              () => mockDocumentReference.update({
                'num_saves': FieldValue.increment(1),
                'popularity_score': 21,
              }),
            ).called(1);
          },
        );

        test(
          'should increment share reaction and update popularity score',
          () async {
            const jokeId = 'test-joke-id';
            mockDocSnapshot = MockDocumentSnapshot();
            when(
              () => mockDocSnapshot.data(),
            ).thenReturn({'num_saves': 2, 'num_shares': 1});

            await repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.share,
              1,
            );

            // popularity_score = 2 + ((1+1) * 5) = 12
            verify(
              () => mockDocumentReference.update({
                'num_shares': FieldValue.increment(1),
                'popularity_score': 12,
              }),
            ).called(1);
          },
        );

        test('should handle missing reaction counts gracefully', () async {
          const jokeId = 'test-joke-id';
          mockDocSnapshot = MockDocumentSnapshot();
          when(() => mockDocSnapshot.data()).thenReturn({
            'setup_text': 'Test joke',
            // Missing num_saves and num_shares
          });

          await repository.updateReactionAndPopularity(
            jokeId,
            JokeReactionType.save,
            1,
          );

          // popularity_score = (0+1) + (0 * 5) = 1
          verify(
            () => mockDocumentReference.update({
              'num_saves': FieldValue.increment(1),
              'popularity_score': 1,
            }),
          ).called(1);
        });

        test('should throw exception when joke not found', () async {
          const jokeId = 'non-existent-joke-id';
          mockDocSnapshot = MockDocumentSnapshot();
          when(() => mockDocSnapshot.data()).thenReturn(<String, dynamic>{});

          expect(
            () => repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.save,
              1,
            ),
            throwsA(isA<Exception>()),
          );

          verifyNever(() => mockDocumentReference.update(any()));
        });

        test(
          'should handle other reaction types without affecting popularity score',
          () async {
            const jokeId = 'test-joke-id';
            mockDocSnapshot = MockDocumentSnapshot();
            when(
              () => mockDocSnapshot.data(),
            ).thenReturn({'num_saves': 1, 'num_shares': 1});

            // Test with a reaction type that doesn't affect saves or shares
            await repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.thumbsUp,
              1,
            );

            // popularity_score should remain the same: 1 + (1 * 5) = 6
            verify(
              () => mockDocumentReference.update({
                'num_thumbs_up': FieldValue.increment(1),
                'popularity_score': 6,
              }),
            ).called(1);
          },
        );

        test(
          'should decrement save reaction and update popularity score',
          () async {
            const jokeId = 'test-joke-id';
            mockDocSnapshot = MockDocumentSnapshot();
            when(
              () => mockDocSnapshot.data(),
            ).thenReturn({'num_saves': 5, 'num_shares': 3});

            await repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.save,
              -1,
            );

            // popularity_score = (5-1) + (3 * 5) = 19
            verify(
              () => mockDocumentReference.update({
                'num_saves': FieldValue.increment(-1),
                'popularity_score': 19,
              }),
            ).called(1);
          },
        );

        test(
          'should decrement share reaction and update popularity score',
          () async {
            const jokeId = 'test-joke-id';
            mockDocSnapshot = MockDocumentSnapshot();
            when(
              () => mockDocSnapshot.data(),
            ).thenReturn({'num_saves': 2, 'num_shares': 1});

            await repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.share,
              -1,
            );

            // popularity_score = 2 + (0 * 5) = 2
            verify(
              () => mockDocumentReference.update({
                'num_shares': FieldValue.increment(-1),
                'popularity_score': 2,
              }),
            ).called(1);
          },
        );

        test('should prevent negative reaction counts', () async {
          const jokeId = 'test-joke-id';
          mockDocSnapshot = MockDocumentSnapshot();
          when(
            () => mockDocSnapshot.data(),
          ).thenReturn({'num_saves': 0, 'num_shares': 0});

          await repository.updateReactionAndPopularity(
            jokeId,
            JokeReactionType.save,
            -1,
          );

          // popularity_score = 0 + (0 * 5) = 0 (shouldn't go negative)
          verify(
            () => mockDocumentReference.update({
              'num_saves': FieldValue.increment(-1),
              'popularity_score': 0,
            }),
          ).called(1);
        });

        test('should throw exception when joke not found', () async {
          const jokeId = 'non-existent-joke-id';
          mockDocSnapshot = MockDocumentSnapshot();
          when(() => mockDocSnapshot.data()).thenReturn(<String, dynamic>{});

          expect(
            () => repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.save,
              -1,
            ),
            throwsA(isA<Exception>()),
          );

          verifyNever(() => mockDocumentReference.update(any()));
        });

        test(
          'should handle other reaction types without affecting popularity score',
          () async {
            const jokeId = 'test-joke-id';
            mockDocSnapshot = MockDocumentSnapshot();
            when(
              () => mockDocSnapshot.data(),
            ).thenReturn({'num_saves': 1, 'num_shares': 1});

            // Test with a reaction type that doesn't affect saves or shares
            await repository.updateReactionAndPopularity(
              jokeId,
              JokeReactionType.thumbsUp,
              -1,
            );

            // popularity_score should remain the same: 1 + (1 * 5) = 6
            verify(
              () => mockDocumentReference.update({
                'num_thumbs_up': FieldValue.increment(-1),
                'popularity_score': 6,
              }),
            ).called(1);
          },
        );
      });
    });
  });
}
