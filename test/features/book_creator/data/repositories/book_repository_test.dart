import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

class MockFirebaseFunctions extends Mock implements FirebaseFunctions {}

class MockHttpsCallable extends Mock implements HttpsCallable {}

class MockHttpsCallableResult extends Mock implements HttpsCallableResult {}

class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  late BookRepository bookRepository;
  late MockFirebaseFunctions mockFirebaseFunctions;
  late MockJokeRepository mockJokeRepository;
  late MockHttpsCallable mockSearchCallable;
  late MockHttpsCallable mockCreateBookCallable;

  setUp(() {
    mockFirebaseFunctions = MockFirebaseFunctions();
    mockJokeRepository = MockJokeRepository();
    mockSearchCallable = MockHttpsCallable();
    mockCreateBookCallable = MockHttpsCallable();

    when(
      () => mockFirebaseFunctions.httpsCallable('search_jokes'),
    ).thenReturn(mockSearchCallable);
    when(
      () => mockFirebaseFunctions.httpsCallable('create_book'),
    ).thenReturn(mockCreateBookCallable);

    bookRepository = BookRepository(
      functions: mockFirebaseFunctions,
      jokeRepository: mockJokeRepository,
    );
  });

  group('BookRepository', () {
    group('searchJokes', () {
      test('returns a list of jokes on successful search', () async {
        // Arrange
        final mockResult = MockHttpsCallableResult();
        when(() => mockResult.data).thenReturn({
          'jokes': [
            {'joke_id': '1'},
            {'joke_id': '2'},
          ],
        });
        when(
          () => mockSearchCallable.call(any()),
        ).thenAnswer((_) async => mockResult);
        final expectedJokes = [
          const Joke(id: '1', setupText: 's1', punchlineText: 'p1'),
          const Joke(id: '2', setupText: 's2', punchlineText: 'p2'),
        ];
        when(
          () => mockJokeRepository.getJokesByIds(any()),
        ).thenAnswer((_) async => expectedJokes);

        // Act
        final result = await bookRepository.searchJokes('test');

        // Assert
        expect(result, expectedJokes);
        verify(
          () => mockSearchCallable.call({
            'search_query': 'test',
            'max_results': 20,
            'public_only': true,
            'match_mode': 'TIGHT',
            'label': 'book_creator_search',
          }),
        ).called(1);
        verify(() => mockJokeRepository.getJokesByIds(['1', '2'])).called(1);
      });

      test('returns an empty list when query is empty', () async {
        // Act
        final result = await bookRepository.searchJokes('');

        // Assert
        expect(result, isEmpty);
        verifyNever(() => mockSearchCallable.call(any()));
      });

      test('returns an empty list on FirebaseFunctionsException', () async {
        // Arrange
        when(() => mockSearchCallable.call(any())).thenThrow(
          FirebaseFunctionsException(message: 'error', code: 'internal'),
        );

        // Act
        final result = await bookRepository.searchJokes('test');

        // Assert
        expect(result, isEmpty);
      });
    });

    group('createBook', () {
      test('completes successfully when book is created', () async {
        // Arrange
        when(
          () => mockCreateBookCallable.call(any()),
        ).thenAnswer((_) async => MockHttpsCallableResult());

        // Act & Assert
        expect(bookRepository.createBook('My Book', ['1', '2']), completes);
        verify(
          () => mockCreateBookCallable.call({
            'book_name': 'My Book',
            'joke_ids': ['1', '2'],
          }),
        ).called(1);
      });

      test('throws an exception on FirebaseFunctionsException', () async {
        // Arrange
        when(() => mockCreateBookCallable.call(any())).thenThrow(
          FirebaseFunctionsException(message: 'error', code: 'internal'),
        );

        // Act & Assert
        expect(
          () => bookRepository.createBook('My Book', ['1', '2']),
          throwsA(isA<FirebaseFunctionsException>()),
        );
      });
    });
  });
}
