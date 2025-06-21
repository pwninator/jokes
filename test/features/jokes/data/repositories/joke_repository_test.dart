import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';

// Generate mocks for Firestore classes
@GenerateMocks([
  FirebaseFirestore,
  CollectionReference,
  Query,
  QuerySnapshot,
  QueryDocumentSnapshot,
  DocumentChange,
], customMocks: [
  // Mocking QueryDocumentSnapshot specifically to handle data() and id
  MockSpec<QueryDocumentSnapshot<Map<String, dynamic>>>(
      as: #MockMapQueryDocumentSnapshot), // Removed returnNullOnMissingStub
])
import 'joke_repository_test.mocks.dart'; // Import generated mocks

void main() {
  late JokeRepository repository;
  late MockFirebaseFirestore mockFirestore;
  late MockCollectionReference<Map<String, dynamic>> mockCollectionReference;
  late MockQuery<Map<String, dynamic>> mockQuery;
  late MockQuerySnapshot<Map<String, dynamic>> mockQuerySnapshot;

  setUp(() {
    mockFirestore = MockFirebaseFirestore();
    mockCollectionReference = MockCollectionReference<Map<String, dynamic>>();
    mockQuery = MockQuery<Map<String, dynamic>>();
    mockQuerySnapshot = MockQuerySnapshot<Map<String, dynamic>>();

    // Setup default stub for collection()
    when(mockFirestore.collection(any)).thenReturn(mockCollectionReference);
    // Setup stub for orderBy() to return mockQuery
    when(mockCollectionReference.orderBy(any, descending: anyNamed('descending')))
        .thenReturn(mockQuery);
    // Setup default stub for snapshots() on the ordered query
    when(mockQuery.snapshots()).thenAnswer((_) => Stream.value(mockQuerySnapshot));

    repository = JokeRepository(mockFirestore);
  });

  const tJoke1 = Joke(id: '1', setupText: 'Setup 1', punchlineText: 'Punchline 1');
  final tJoke1Map = {'setup_text': 'Setup 1', 'punchline_text': 'Punchline 1'}; // snake_case keys
  const tJoke2 = Joke(id: '2', setupText: 'Setup 2', punchlineText: 'Punchline 2');
  final tJoke2Map = {'setup_text': 'Setup 2', 'punchline_text': 'Punchline 2'}; // snake_case keys


  MockMapQueryDocumentSnapshot createMockDoc(Map<String, dynamic> data, String id) { // Removed generic type
    final mockDoc = MockMapQueryDocumentSnapshot(); // Removed generic type
    when(mockDoc.data()).thenReturn(data);
    when(mockDoc.id).thenReturn(id);
    return mockDoc;
  }

  group('JokeRepository', () {
    test('should call firestore.collection with "jokes"', () async {
      // arrange
      when(mockQuerySnapshot.docs).thenReturn([]); // Empty list of docs
      // act
      repository.getJokes();
      // assert
      verify(mockFirestore.collection('jokes')).called(1);
      verify(mockCollectionReference.orderBy('creation_time', descending: true)).called(1);
    });

    test('getJokes should return a stream of list of jokes when Firestore returns data', () async {
      // arrange
      final mockDoc1 = createMockDoc(tJoke1Map, '1');
      final mockDoc2 = createMockDoc(tJoke2Map, '2');

      when(mockQuerySnapshot.docs).thenReturn([mockDoc1, mockDoc2]);

      // act
      final resultStream = repository.getJokes();

      // assert
      expect(resultStream, emits([tJoke1, tJoke2]));
      // Verify that orderBy and snapshots() were called
      verify(mockCollectionReference.orderBy('creation_time', descending: true)).called(1);
      verify(mockQuery.snapshots()).called(1);
    });

    test('getJokes should return a stream of an empty list when Firestore returns no data', () async {
      // arrange
      when(mockQuerySnapshot.docs).thenReturn([]);

      // act
      final resultStream = repository.getJokes();

      // assert
      expect(resultStream, emits([]));
      verify(mockCollectionReference.orderBy('creation_time', descending: true)).called(1);
      verify(mockQuery.snapshots()).called(1);
    });

    test('getJokes should map Firestore exceptions to stream error', () {
      // arrange
      when(mockQuery.snapshots()).thenAnswer((_) => Stream.error(FirebaseException(plugin: 'firestore', message: 'Test error')));

      // act
      final resultStream = repository.getJokes();

      // assert
      expect(resultStream, emitsError(isA<FirebaseException>()));
    });
  });
}
