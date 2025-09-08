// ignore_for_file: subtype_of_sealed_class
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

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

class MockWriteBatch extends Mock implements WriteBatch {}

class MockTimestamp extends Mock implements Timestamp {}

void main() {
  group('JokeRepository', () {
    late JokeRepository repository;
    late JokeRepository adminRepository;
    late JokeRepository debugRepository;
    late MockFirebaseFirestore mockFirestore;
    late MockCollectionReference mockCollectionReference;
    late MockDocumentReference mockDocumentReference;
    late MockQuery mockQuery;
    late MockQuerySnapshot mockQuerySnapshot;
    late MockDocumentSnapshot mockDocSnapshot;
    late MockWriteBatch mockBatch;

    // Test data helpers
    Map<String, dynamic> createJokeData(int index) => {
      'setup_text': 'Setup $index',
      'punchline_text': 'Punchline $index',
      'setup_image_url': 'https://example.com/setup$index.jpg',
      'punchline_image_url': 'https://example.com/punchline$index.jpg',
    };

    MockDocumentSnapshot createMockDoc(String id, Map<String, dynamic> data) {
      final doc = MockDocumentSnapshot();
      when(() => doc.id).thenReturn(id);
      when(() => doc.data()).thenReturn(data);
      when(() => doc.exists).thenReturn(true);
      return doc;
    }

    setUp(() {
      mockFirestore = MockFirebaseFirestore();
      mockCollectionReference = MockCollectionReference();
      mockDocumentReference = MockDocumentReference();
      mockQuery = MockQuery();
      mockQuerySnapshot = MockQuerySnapshot();
      mockDocSnapshot = MockDocumentSnapshot();
      mockBatch = MockWriteBatch();

      repository = JokeRepository(mockFirestore, false, false);
      adminRepository = JokeRepository(mockFirestore, true, false);
      debugRepository = JokeRepository(mockFirestore, false, true);

      // Common Firestore setup
      when(
        () => mockFirestore.collection(any()),
      ).thenReturn(mockCollectionReference);
      when(() => mockFirestore.batch()).thenReturn(mockBatch);
      when(
        () => mockCollectionReference.doc(any()),
      ).thenReturn(mockDocumentReference);
      when(
        () => mockDocumentReference.update(any()),
      ).thenAnswer((_) async => {});
      when(() => mockDocumentReference.delete()).thenAnswer((_) async => {});
      when(
        () => mockDocumentReference.get(),
      ).thenAnswer((_) async => mockDocSnapshot);
      when(() => mockBatch.commit()).thenAnswer((_) async => {});
    });

    group('getJokes', () {
      setUp(() {
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

      test('returns stream of jokes', () async {
        final docs = [
          createMockDoc('1', createJokeData(1)),
          createMockDoc('2', createJokeData(2)),
        ];
        when(() => mockQuerySnapshot.docs).thenReturn(docs);

        final jokes = await repository.getJokes().first;

        expect(jokes, hasLength(2));
        expect(jokes[0].id, '1');
        expect(jokes[0].setupText, 'Setup 1');
        verify(
          () => mockCollectionReference.orderBy(
            'creation_time',
            descending: true,
          ),
        );
      });

      test('returns empty list when no jokes', () async {
        when(() => mockQuerySnapshot.docs).thenReturn([]);

        final jokes = await repository.getJokes().first;

        expect(jokes, isEmpty);
      });

      test('propagates Firebase errors', () async {
        when(() => mockQuery.snapshots()).thenAnswer(
          (_) => Stream.error(
            FirebaseException(plugin: 'firestore', message: 'Error'),
          ),
        );

        expect(repository.getJokes(), emitsError(isA<FirebaseException>()));
      });
    });

    group('updateJoke', () {
      test('updates joke with all fields', () async {
        await repository.updateJoke(
          jokeId: 'joke1',
          setupText: 'New setup',
          punchlineText: 'New punchline',
          setupImageUrl: 'setup.jpg',
          punchlineImageUrl: 'punchline.jpg',
          setupImageDescription: 'Setup desc',
          punchlineImageDescription: 'Punchline desc',
        );

        verify(
          () => mockDocumentReference.update({
            'setup_text': 'New setup',
            'punchline_text': 'New punchline',
            'setup_image_url': 'setup.jpg',
            'punchline_image_url': 'punchline.jpg',
            'setup_image_description': 'Setup desc',
            'punchline_image_description': 'Punchline desc',
          }),
        );
      });

      test('updates joke with required fields only', () async {
        await repository.updateJoke(
          jokeId: 'joke1',
          setupText: 'New setup',
          punchlineText: 'New punchline',
        );

        verify(
          () => mockDocumentReference.update({
            'setup_text': 'New setup',
            'punchline_text': 'New punchline',
          }),
        );
      });

      test('propagates Firebase errors', () async {
        when(
          () => mockDocumentReference.update(any()),
        ).thenThrow(FirebaseException(plugin: 'firestore', message: 'Error'));

        expect(
          () => repository.updateJoke(
            jokeId: 'joke1',
            setupText: 'setup',
            punchlineText: 'punchline',
          ),
          throwsA(isA<FirebaseException>()),
        );
      });
    });

    group('deleteJoke', () {
      test('deletes joke successfully', () async {
        await repository.deleteJoke('joke1');

        verify(() => mockDocumentReference.delete());
      });

      test('propagates Firebase errors', () async {
        when(
          () => mockDocumentReference.delete(),
        ).thenThrow(FirebaseException(plugin: 'firestore', message: 'Error'));

        expect(
          () => repository.deleteJoke('joke1'),
          throwsA(isA<FirebaseException>()),
        );
      });
    });

    group('getJokeByIdStream', () {
      test('returns joke when document exists', () async {
        when(() => mockDocSnapshot.exists).thenReturn(true);
        when(() => mockDocSnapshot.data()).thenReturn(createJokeData(1));
        when(() => mockDocSnapshot.id).thenReturn('joke1');
        when(
          () => mockDocumentReference.snapshots(),
        ).thenAnswer((_) => Stream.value(mockDocSnapshot));

        final joke = await repository.getJokeByIdStream('joke1').first;

        expect(joke, isNotNull);
        expect(joke!.id, 'joke1');
        expect(joke.setupText, 'Setup 1');
      });

      test('returns null when document does not exist', () async {
        when(() => mockDocSnapshot.exists).thenReturn(false);
        when(
          () => mockDocumentReference.snapshots(),
        ).thenAnswer((_) => Stream.value(mockDocSnapshot));

        final joke = await repository.getJokeByIdStream('joke1').first;

        expect(joke, isNull);
      });

      test('propagates Firebase errors', () async {
        when(() => mockDocumentReference.snapshots()).thenAnswer(
          (_) => Stream.error(
            FirebaseException(plugin: 'firestore', message: 'Error'),
          ),
        );

        expect(
          repository.getJokeByIdStream('joke1'),
          emitsError(isA<FirebaseException>()),
        );
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

      test('returns empty list when no IDs provided', () async {
        final result = await repository.getJokesByIds([]);

        expect(result, isEmpty);
        verifyNever(() => mockFirestore.collection('jokes'));
      });

      test('returns jokes for given IDs', () async {
        final docs = [
          createMockDoc('joke1', createJokeData(1)),
          createMockDoc('joke2', createJokeData(2)),
        ];
        when(() => mockQuerySnapshot.docs).thenReturn(docs);

        final result = await repository.getJokesByIds(['joke1', 'joke2']);

        expect(result, hasLength(2));
        expect(result.map((j) => j.id), ['joke1', 'joke2']);
        verify(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: ['joke1', 'joke2'],
          ),
        );
      });

      test('handles batching for more than 10 IDs', () async {
        final jokeIds = List.generate(15, (i) => 'joke$i');

        // Mock separate query snapshots for each batch
        final firstBatchSnapshot = MockQuerySnapshot();
        final secondBatchSnapshot = MockQuerySnapshot();
        final firstBatchQuery = MockQuery();
        final secondBatchQuery = MockQuery();

        final firstBatchDocs = List.generate(
          10,
          (i) => createMockDoc('joke$i', createJokeData(i)),
        );
        final secondBatchDocs = List.generate(
          5,
          (i) => createMockDoc('joke${i + 10}', createJokeData(i + 10)),
        );

        when(() => firstBatchSnapshot.docs).thenReturn(firstBatchDocs);
        when(() => secondBatchSnapshot.docs).thenReturn(secondBatchDocs);
        when(
          () => firstBatchQuery.get(),
        ).thenAnswer((_) async => firstBatchSnapshot);
        when(
          () => secondBatchQuery.get(),
        ).thenAnswer((_) async => secondBatchSnapshot);

        when(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds.take(10).toList(),
          ),
        ).thenReturn(firstBatchQuery);
        when(
          () => mockCollectionReference.where(
            FieldPath.documentId,
            whereIn: jokeIds.skip(10).toList(),
          ),
        ).thenReturn(secondBatchQuery);

        final result = await repository.getJokesByIds(jokeIds);

        expect(result, hasLength(15));
        verify(() => mockFirestore.collection('jokes')).called(2);
      });

      test('propagates Firebase errors', () async {
        when(
          () => mockWhereQuery.get(),
        ).thenThrow(FirebaseException(plugin: 'firestore', message: 'Error'));

        expect(
          () => repository.getJokesByIds(['joke1']),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('getFilteredJokePage', () {
      test('returns paginated joke IDs with cursor', () async {
        // Setup the query chain for this specific test
        when(
          () => mockCollectionReference.where(
            any(),
            whereIn: any(named: 'whereIn'),
          ),
        ).thenReturn(mockQuery);
        when(
          () => mockCollectionReference.orderBy(
            any(),
            descending: any(named: 'descending'),
          ),
        ).thenReturn(mockQuery);
        when(
          () => mockQuery.orderBy(any(), descending: any(named: 'descending')),
        ).thenReturn(mockQuery);
        when(() => mockQuery.limit(any())).thenReturn(mockQuery);
        when(() => mockQuery.get()).thenAnswer((_) async => mockQuerySnapshot);

        final docs = [
          createMockDoc('joke1', {
            'creation_time': Timestamp.now(),
            ...createJokeData(1),
          }),
          createMockDoc('joke2', {
            'creation_time': Timestamp.now(),
            ...createJokeData(2),
          }),
        ];
        when(() => mockQuerySnapshot.docs).thenReturn(docs);

        final page = await repository.getFilteredJokePage(
          states: {JokeState.approved},
          popularOnly: false,
          limit: 10,
        );

        expect(page.ids, ['joke1', 'joke2']);
        expect(page.cursor, isNotNull);
        expect(page.hasMore, false); // Less than limit
      });

      test('handles popular-only filtering', () async {
        // Setup for popular-only path which uses different query chain
        when(
          () => mockCollectionReference.where(
            any(),
            isGreaterThan: any(named: 'isGreaterThan'),
          ),
        ).thenReturn(mockQuery);
        when(
          () => mockQuery.orderBy(any(), descending: any(named: 'descending')),
        ).thenReturn(mockQuery);
        when(() => mockQuery.limit(any())).thenReturn(mockQuery);
        when(() => mockQuery.get()).thenAnswer((_) async => mockQuerySnapshot);
        when(() => mockQuerySnapshot.docs).thenReturn([]);

        final page = await repository.getFilteredJokePage(
          states: {},
          popularOnly: true,
          limit: 10,
        );

        expect(page.ids, isEmpty);
        expect(page.cursor, isNull);
        expect(page.hasMore, false);
        verify(
          () => mockCollectionReference.where(
            'popularity_score',
            isGreaterThan: 0,
          ),
        );
      });

      test('returns empty page when no results', () async {
        when(
          () => mockCollectionReference.orderBy(
            any(),
            descending: any(named: 'descending'),
          ),
        ).thenReturn(mockQuery);
        when(
          () => mockQuery.orderBy(any(), descending: any(named: 'descending')),
        ).thenReturn(mockQuery);
        when(() => mockQuery.limit(any())).thenReturn(mockQuery);
        when(() => mockQuery.get()).thenAnswer((_) async => mockQuerySnapshot);
        when(() => mockQuerySnapshot.docs).thenReturn([]);

        final page = await repository.getFilteredJokePage(
          states: {},
          popularOnly: false,
          limit: 10,
        );

        expect(page.ids, isEmpty);
        expect(page.cursor, isNull);
        expect(page.hasMore, false);
      });
    });

    group('updateReactionAndPopularity', () {
      setUp(() {
        when(
          () => mockDocSnapshot.data(),
        ).thenReturn({'num_saves': 5, 'num_shares': 3});
      });

      group('production mode', () {
        test('increments save reaction and updates popularity score', () async {
          await repository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.save,
            1,
          );

          // popularity_score = (5+1) + (3 * 5) = 21
          verify(
            () => mockDocumentReference.update({
              'num_saves': FieldValue.increment(1),
              'popularity_score': 21,
            }),
          );
        });

        test(
          'increments share reaction and updates popularity score',
          () async {
            await repository.updateReactionAndPopularity(
              'joke1',
              JokeReactionType.share,
              1,
            );

            // popularity_score = 5 + ((3+1) * 5) = 25
            verify(
              () => mockDocumentReference.update({
                'num_shares': FieldValue.increment(1),
                'popularity_score': 25,
              }),
            );
          },
        );

        test('handles missing reaction counts gracefully', () async {
          when(() => mockDocSnapshot.data()).thenReturn({'setup_text': 'joke'});

          await repository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.save,
            1,
          );

          verify(
            () => mockDocumentReference.update({
              'num_saves': FieldValue.increment(1),
              'popularity_score': 1, // (0+1) + (0 * 5)
            }),
          );
        });

        test('handles other reaction types', () async {
          await repository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.thumbsUp,
            1,
          );

          verify(
            () => mockDocumentReference.update({
              'num_thumbs_up': FieldValue.increment(1),
              'popularity_score': 20, // 5 + (3 * 5)
            }),
          );
        });

        test('handles decrements correctly', () async {
          await repository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.save,
            -1,
          );

          verify(
            () => mockDocumentReference.update({
              'num_saves': FieldValue.increment(-1),
              'popularity_score': 19, // (5-1) + (3 * 5)
            }),
          );
        });

        test('throws exception when joke not found', () async {
          when(() => mockDocSnapshot.data()).thenReturn({});

          expect(
            () => repository.updateReactionAndPopularity(
              'joke1',
              JokeReactionType.save,
              1,
            ),
            throwsA(isA<Exception>()),
          );
        });
      });

      group('admin/debug mode suppression', () {
        test('admin mode suppresses writes', () async {
          await adminRepository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.save,
            1,
          );

          verifyNever(() => mockDocumentReference.update(any()));
          verifyNever(() => mockDocumentReference.get());
        });

        test('debug mode suppresses writes', () async {
          await debugRepository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.save,
            1,
          );

          verifyNever(() => mockDocumentReference.update(any()));
          verifyNever(() => mockDocumentReference.get());
        });
      });
    });

    group('setAdminRatingAndState', () {
      test('updates admin rating and state when allowed', () async {
        when(
          () => mockDocSnapshot.data(),
        ).thenReturn({'state': JokeState.unreviewed.value});

        await repository.setAdminRatingAndState(
          'joke1',
          JokeAdminRating.approved,
        );

        verify(
          () => mockDocumentReference.update({
            'admin_rating': JokeAdminRating.approved.value,
            'state': JokeState.approved.value,
          }),
        );
      });

      test(
        'throws error when state does not allow admin rating change',
        () async {
          when(
            () => mockDocSnapshot.data(),
          ).thenReturn({'state': JokeState.published.value});

          expect(
            () => repository.setAdminRatingAndState(
              'joke1',
              JokeAdminRating.approved,
            ),
            throwsA(isA<StateError>()),
          );
        },
      );
    });

    group('batch operations', () {
      test('setJokesPublished updates multiple jokes', () async {
        final jokeMap = {
          'joke1': DateTime(2024, 1, 1),
          'joke2': DateTime(2024, 1, 2),
        };

        await repository.setJokesPublished(jokeMap, false);

        verify(() => mockBatch.commit());
      });

      test('setJokesPublished handles empty map', () async {
        await repository.setJokesPublished({}, false);

        verifyNever(() => mockBatch.commit());
      });

      test('resetJokesToApproved validates states and resets jokes', () async {
        when(() => mockDocSnapshot.exists).thenReturn(true);
        when(
          () => mockDocSnapshot.data(),
        ).thenReturn({'state': JokeState.published.value});

        await repository.resetJokesToApproved([
          'joke1',
          'joke2',
        ], expectedState: JokeState.published);

        verify(() => mockBatch.commit());
      });

      test('resetJokesToApproved throws when validation fails', () async {
        when(() => mockDocSnapshot.exists).thenReturn(true);
        when(
          () => mockDocSnapshot.data(),
        ).thenReturn({'state': JokeState.approved.value});

        expect(
          () => repository.resetJokesToApproved([
            'joke1',
          ], expectedState: JokeState.published),
          throwsA(isA<Exception>()),
        );

        verifyNever(() => mockBatch.commit());
      });
    });
  });
}
