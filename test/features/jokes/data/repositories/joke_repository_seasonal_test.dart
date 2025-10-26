// ignore_for_file: subtype_of_sealed_class
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}

class MockCollectionReference extends Mock
    implements CollectionReference<Map<String, dynamic>> {}

class MockQuery extends Mock implements Query<Map<String, dynamic>> {}

class MockQuerySnapshot extends Mock
    implements QuerySnapshot<Map<String, dynamic>> {}

class MockQueryDocumentSnapshot extends Mock
    implements QueryDocumentSnapshot<Map<String, dynamic>> {}

class MockPerformanceService extends Mock implements PerformanceService {}

void main() {
  group('JokeRepository.getSeasonalJokePage', () {
    late JokeRepository repository;
    late MockFirebaseFirestore mockFirestore;
    late MockCollectionReference mockCollectionReference;
    late MockQuery mockQuery;
    late MockQuerySnapshot mockQuerySnapshot;
    late MockPerformanceService mockPerformanceService;

    MockQueryDocumentSnapshot createDoc(String id, Map<String, dynamic> data) {
      final d = MockQueryDocumentSnapshot();
      when(() => d.id).thenReturn(id);
      when(() => d.data()).thenReturn(data);
      return d;
    }

    setUp(() {
      mockFirestore = MockFirebaseFirestore();
      mockPerformanceService = MockPerformanceService();
      mockCollectionReference = MockCollectionReference();
      mockQuery = MockQuery();
      mockQuerySnapshot = MockQuerySnapshot();

      repository = JokeRepository(
        firestore: mockFirestore,
        perf: mockPerformanceService,
      );

      when(
        () => mockFirestore.collection('jokes'),
      ).thenReturn(mockCollectionReference);

      // where('state', whereIn: ...)
      when(
        () => mockCollectionReference.where(
          'state',
          whereIn: any(named: 'whereIn'),
        ),
      ).thenReturn(mockQuery);

      // chain: seasonal filter
      when(
        () => mockQuery.where('seasonal', isEqualTo: any(named: 'isEqualTo')),
      ).thenReturn(mockQuery);

      // chain: popularity filter
      when(
        () => mockQuery.where(
          'popularity_score',
          isGreaterThan: any(named: 'isGreaterThan'),
        ),
      ).thenReturn(mockQuery);

      // chain: order by popularity
      when(
        () => mockQuery.orderBy('popularity_score', descending: true),
      ).thenReturn(mockQuery);

      // chain: tie-breaker order by ID
      when(
        () => mockQuery.orderBy(FieldPath.documentId, descending: true),
      ).thenReturn(mockQuery);

      // chain: startAfter
      when(() => mockQuery.startAfter(any())).thenReturn(mockQuery);

      // chain: limit
      when(() => mockQuery.limit(any())).thenReturn(mockQuery);
    });

    test('returns empty when no docs', () async {
      when(() => mockQuery.get()).thenAnswer((_) async => mockQuerySnapshot);
      when(
        () => mockQuerySnapshot.docs,
      ).thenReturn(<QueryDocumentSnapshot<Map<String, dynamic>>>[]);

      final page = await repository.getFilteredJokePage(
        filters: [
          JokeFilter.whereInValues(JokeField.state, [
            JokeState.published.value,
            JokeState.daily.value,
          ]),
          JokeFilter.greaterThan(JokeField.popularityScore, 0.0),
          JokeFilter.equals(JokeField.seasonal, 'Halloween'),
        ],
        orderByField: JokeField.popularityScore,
        orderDirection: OrderDirection.descending,
        limit: 10,
      );
      expect(page.ids, isEmpty);
      expect(page.cursor, isNull);
      expect(page.hasMore, isFalse);

      verify(
        () => mockCollectionReference.where(
          'state',
          whereIn: any(named: 'whereIn'),
        ),
      ).called(1);
      verify(
        () => mockQuery.where('seasonal', isEqualTo: 'Halloween'),
      ).called(1);
      verify(
        () => mockQuery.orderBy('popularity_score', descending: true),
      ).called(1);
      verify(() => mockQuery.limit(10)).called(1);
    });

    test('returns ids and cursor when docs present', () async {
      final docs = [
        createDoc('a', {'popularity_score': 0.7}),
        createDoc('b', {'popularity_score': 0.6}),
      ];
      when(() => mockQuery.get()).thenAnswer((_) async => mockQuerySnapshot);
      when(() => mockQuerySnapshot.docs).thenReturn(docs);

      final page = await repository.getFilteredJokePage(
        filters: [
          JokeFilter.whereInValues(JokeField.state, [
            JokeState.published.value,
            JokeState.daily.value,
          ]),
          JokeFilter.greaterThan(JokeField.popularityScore, 0.0),
          JokeFilter.equals(JokeField.seasonal, 'Halloween'),
        ],
        orderByField: JokeField.popularityScore,
        orderDirection: OrderDirection.descending,
        limit: 2,
      );

      expect(page.ids, ['a', 'b']);
      expect(page.cursor, isNotNull);
      expect(page.hasMore, isTrue); // full page implies maybe more

      // Next page using cursor should call startAfter
      final next = await repository.getFilteredJokePage(
        filters: [
          JokeFilter.whereInValues(JokeField.state, [
            JokeState.published.value,
            JokeState.daily.value,
          ]),
          JokeFilter.greaterThan(JokeField.popularityScore, 0.0),
          JokeFilter.equals(JokeField.seasonal, 'Halloween'),
        ],
        orderByField: JokeField.popularityScore,
        orderDirection: OrderDirection.descending,
        limit: 2,
        cursor: page.cursor,
      );
      // With our current mocks, docs are still the same (not material here)
      expect(next.ids, ['a', 'b']);
    });
  });
}
