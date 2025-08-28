import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Mock classes using mocktail
class MockFirebaseFunctions extends Mock implements FirebaseFunctions {}

class MockHttpsCallable extends Mock implements HttpsCallable {}

class MockHttpsCallableResult extends Mock implements HttpsCallableResult {}

void main() {
  group('JokeCloudFunctionService', () {
    late JokeCloudFunctionService service;
    late MockFirebaseFunctions mockFunctions;
    late MockHttpsCallable mockCallable;
    late MockHttpsCallableResult mockResult;

    setUp(() {
      mockFunctions = MockFirebaseFunctions();
      mockCallable = MockHttpsCallable();
      mockResult = MockHttpsCallableResult();
      service = JokeCloudFunctionService(functions: mockFunctions);
    });

    group('populateJoke', () {
      test('should return success when cloud function succeeds', () async {
        const jokeId = 'test-joke-id';
        final mockResponseData = {'updated_joke': 'data'};

        when(
          () => mockFunctions.httpsCallable(
            'populate_joke',
            options: any(named: 'options'),
          ),
        ).thenReturn(mockCallable);
        when(() => mockResult.data).thenReturn(mockResponseData);
        when(
          () => mockCallable.call(any()),
        ).thenAnswer((_) async => mockResult);

        final result = await service.populateJoke(jokeId);

        expect(result, equals({'success': true, 'data': mockResponseData}));
        verify(
          () => mockFunctions.httpsCallable(
            'populate_joke',
            options: any(named: 'options'),
          ),
        ).called(1);
        verify(() => mockCallable.call(any())).called(1);
      });

      test('should return error when cloud function fails', () async {
        const jokeId = 'test-joke-id';
        final exception = FirebaseFunctionsException(
          code: 'internal',
          message: 'Internal error',
        );

        when(
          () => mockFunctions.httpsCallable(
            'populate_joke',
            options: any(named: 'options'),
          ),
        ).thenReturn(mockCallable);
        when(() => mockCallable.call(any())).thenThrow(exception);

        final result = await service.populateJoke(jokeId);

        expect(result!['success'], isFalse);
        expect(result['error'], contains('Function error: Internal error'));
      });
    });

    group('createJokeWithResponse', () {
      test(
        'should return success response when cloud function succeeds',
        () async {
          const setupText = 'Test setup';
          const punchlineText = 'Test punchline';
          final mockResponseData = {'jokeId': 'created-joke-id'};

          when(
            () => mockFunctions.httpsCallable('create_joke'),
          ).thenReturn(mockCallable);
          when(() => mockResult.data).thenReturn(mockResponseData);
          when(
            () => mockCallable.call({
              'joke_data': {
                'setup_text': setupText,
                'punchline_text': punchlineText,
                'setup_image_url': null,
                'punchline_image_url': null,
              },
            }),
          ).thenAnswer((_) async => mockResult);

          final result = await service.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
          );

          expect(result, equals({'success': true, 'data': mockResponseData}));
          verify(() => mockFunctions.httpsCallable('create_joke')).called(1);
        },
      );
    });

    group('updateJoke', () {
      test('should return success when cloud function succeeds', () async {
        const jokeId = 'test-joke-id';
        const setupText = 'Updated setup';
        const punchlineText = 'Updated punchline';
        final mockResponseData = {
          'success': true,
          'message': 'Joke updated successfully',
        };

        when(
          () => mockFunctions.httpsCallable('update_joke'),
        ).thenReturn(mockCallable);
        when(() => mockResult.data).thenReturn(mockResponseData);
        when(
          () => mockCallable.call({
            'joke_id': jokeId,
            'joke_data': {
              'setup_text': setupText,
              'punchline_text': punchlineText,
              'setup_image_url': null,
              'punchline_image_url': null,
            },
          }),
        ).thenAnswer((_) async => mockResult);

        final result = await service.updateJoke(
          jokeId: jokeId,
          setupText: setupText,
          punchlineText: punchlineText,
        );

        expect(result, equals({'success': true, 'data': mockResponseData}));
      });
    });

    group('critiqueJokes', () {
      test('should return success when cloud function succeeds', () async {
        const instructions = 'Test critique instructions';
        final responseData = {'generated_jokes': []};

        when(
          () => mockFunctions.httpsCallable(
            'critique_jokes',
            options: any(named: 'options'),
          ),
        ).thenReturn(mockCallable);
        when(() => mockResult.data).thenReturn(responseData);
        when(
          () => mockCallable.call({'instructions': instructions}),
        ).thenAnswer((_) async => mockResult);

        final result = await service.critiqueJokes(instructions: instructions);

        expect(result, equals({'success': true, 'data': responseData}));
        verify(
          () => mockFunctions.httpsCallable(
            'critique_jokes',
            options: any(named: 'options'),
          ),
        ).called(1);
        verify(
          () => mockCallable.call({'instructions': instructions}),
        ).called(1);
      });
    });

    group('searchJokes', () {
      test('parses list of objects with joke_id and vector_distance', () async {
        const q = 'cat';

        when(
          () => mockFunctions.httpsCallable('search_jokes'),
        ).thenReturn(mockCallable);
        when(() => mockResult.data).thenReturn([
          {'joke_id': 'a', 'vector_distance': 0.11},
          {'joke_id': 'b', 'vector_distance': 0.23},
        ]);
        when(
          () => mockCallable.call({'search_query': q}),
        ).thenAnswer((_) async => mockResult);

        final ids = await service.searchJokes(searchQuery: q);
        expect(ids, ['a', 'b']);
        verify(() => mockFunctions.httpsCallable('search_jokes')).called(1);
        verify(() => mockCallable.call({'search_query': q})).called(1);
      });

      test('parses {jokes: [...]} shape', () async {
        const q = 'dog';

        when(
          () => mockFunctions.httpsCallable('search_jokes'),
        ).thenReturn(mockCallable);
        when(() => mockResult.data).thenReturn({
          'jokes': [
            {'joke_id': 'x', 'vector_distance': 0.3},
            {'joke_id': 'y', 'vector_distance': 0.4},
          ],
        });
        when(
          () => mockCallable.call({'search_query': q}),
        ).thenAnswer((_) async => mockResult);

        final ids = await service.searchJokes(searchQuery: q);
        expect(ids, ['x', 'y']);
      });

      test('supports max_results param', () async {
        const q = 'dog';

        when(
          () => mockFunctions.httpsCallable('search_jokes'),
        ).thenReturn(mockCallable);
        when(() => mockResult.data).thenReturn([
          {'joke_id': 'x', 'vector_distance': 0.1},
        ]);
        when(
          () => mockCallable.call({'search_query': q, 'max_results': 5}),
        ).thenAnswer((_) async => mockResult);

        final ids = await service.searchJokes(searchQuery: q, maxResults: 5);
        expect(ids, ['x']);
      });

      test('handles exceptions and returns empty list', () async {
        const q = 'error';

        when(
          () => mockFunctions.httpsCallable('search_jokes'),
        ).thenReturn(mockCallable);
        when(
          () => mockCallable.call({'search_query': q}),
        ).thenThrow(Exception('boom'));

        final ids = await service.searchJokes(searchQuery: q);
        expect(ids, isEmpty);
      });
    });
  });
}
