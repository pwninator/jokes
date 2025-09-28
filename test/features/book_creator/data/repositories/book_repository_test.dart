import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  setUpAll(() {
    registerFallbackValue(MatchMode.tight);
    registerFallbackValue(SearchScope.jokeManagementSearch);
    registerFallbackValue(SearchLabel.none);
  });
  late BookRepository bookRepository;
  late MockJokeRepository mockJokeRepository;
  late MockJokeCloudFunctionService mockJokeCloudFunctionService;

  setUp(() {
    mockJokeRepository = MockJokeRepository();
    mockJokeCloudFunctionService = MockJokeCloudFunctionService();

    bookRepository = BookRepository(
      jokeRepository: mockJokeRepository,
      jokeCloudFunctionService: mockJokeCloudFunctionService,
    );
  });

  group('BookRepository', () {
    group('searchJokes', () {
      test('returns a list of jokes on successful search', () async {
        // Arrange
        final mockSearchResults = [
          const JokeSearchResult(id: '1', vectorDistance: 0.1),
          const JokeSearchResult(id: '2', vectorDistance: 0.2),
        ];
        when(
          () => mockJokeCloudFunctionService.searchJokes(
            searchQuery: any(named: 'searchQuery'),
            maxResults: any(named: 'maxResults'),
            publicOnly: any(named: 'publicOnly'),
            matchMode: any(named: 'matchMode'),
            scope: any(named: 'scope'),
            label: any(named: 'label'),
          ),
        ).thenAnswer((_) async => mockSearchResults);

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
          () => mockJokeCloudFunctionService.searchJokes(
            searchQuery: 'test',
            maxResults: 20,
            publicOnly: false,
            matchMode: MatchMode.loose,
            scope: SearchScope.jokeManagementSearch,
            label: SearchLabel.none,
          ),
        ).called(1);
        verify(() => mockJokeRepository.getJokesByIds(['1', '2'])).called(1);
      });

      test('returns an empty list when query is empty', () async {
        // Act
        final result = await bookRepository.searchJokes('');

        // Assert
        expect(result, isEmpty);
        verifyNever(
          () => mockJokeCloudFunctionService.searchJokes(
            searchQuery: any(named: 'searchQuery'),
            maxResults: any(named: 'maxResults'),
            publicOnly: any(named: 'publicOnly'),
            matchMode: any(named: 'matchMode'),
            scope: any(named: 'scope'),
            label: any(named: 'label'),
          ),
        );
      });

      test('returns an empty list on search service exception', () async {
        // Arrange
        when(
          () => mockJokeCloudFunctionService.searchJokes(
            searchQuery: any(named: 'searchQuery'),
            maxResults: any(named: 'maxResults'),
            publicOnly: any(named: 'publicOnly'),
            matchMode: any(named: 'matchMode'),
            scope: any(named: 'scope'),
            label: any(named: 'label'),
          ),
        ).thenThrow(Exception('Search error'));

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
          () => mockJokeCloudFunctionService.createBook(
            title: any(named: 'title'),
            jokeIds: any(named: 'jokeIds'),
          ),
        ).thenAnswer((_) async => {'success': true, 'data': 'book-created'});

        // Act
        await bookRepository.createBook('My Book', ['1', '2']);

        // Assert
        verify(
          () => mockJokeCloudFunctionService.createBook(
            title: 'My Book',
            jokeIds: ['1', '2'],
          ),
        ).called(1);
      });

      test('throws an exception when createBook returns failure', () async {
        // Arrange
        when(
          () => mockJokeCloudFunctionService.createBook(
            title: any(named: 'title'),
            jokeIds: any(named: 'jokeIds'),
          ),
        ).thenAnswer(
          (_) async => {'success': false, 'error': 'Book creation failed'},
        );

        // Act & Assert
        expect(
          () => bookRepository.createBook('My Book', ['1', '2']),
          throwsA(isA<Exception>()),
        );
      });

      test('throws an exception when createBook returns null', () async {
        // Arrange
        when(
          () => mockJokeCloudFunctionService.createBook(
            title: any(named: 'title'),
            jokeIds: any(named: 'jokeIds'),
          ),
        ).thenAnswer((_) async => null);

        // Act & Assert
        expect(
          () => bookRepository.createBook('My Book', ['1', '2']),
          throwsA(isA<Exception>()),
        );
      });

      test('throws an exception when service throws', () async {
        // Arrange
        when(
          () => mockJokeCloudFunctionService.createBook(
            title: any(named: 'title'),
            jokeIds: any(named: 'jokeIds'),
          ),
        ).thenThrow(Exception('Service error'));

        // Act & Assert
        expect(
          () => bookRepository.createBook('My Book', ['1', '2']),
          throwsA(isA<Exception>()),
        );
      });
    });
  });
}
