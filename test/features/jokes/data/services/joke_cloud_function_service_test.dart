import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Generate mocks
@GenerateMocks([FirebaseFunctions, HttpsCallable, HttpsCallableResult])
import 'joke_cloud_function_service_test.mocks.dart';

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

      // Create service with mocked functions
      service = JokeCloudFunctionService(functions: mockFunctions);
    });

    group('populateJoke', () {
      test('should return success when cloud function succeeds', () async {
        // arrange
        const jokeId = 'test-joke-id';
        const mockResponseData = {'updated_joke': 'data'};
        const expectedData = {'success': true, 'data': mockResponseData};

        when(mockResult.data).thenReturn(mockResponseData);
        when(
          mockCallable.call({'joke_id': jokeId}),
        ).thenAnswer((_) async => mockResult);
        when(
          mockFunctions.httpsCallable(
            'populate_joke',
            options: anyNamed('options'),
          ),
        ).thenReturn(mockCallable);

        // act
        final result = await service.populateJoke(jokeId);

        // assert
        expect(result, equals(expectedData));
        verify(mockFunctions.httpsCallable(
          'populate_joke',
          options: anyNamed('options'),
        )).called(1);
        verify(mockCallable.call({'joke_id': jokeId})).called(1);
      });

      test(
        'should return error when FirebaseFunctionsException is thrown',
        () async {
          // arrange
          const jokeId = 'test-joke-id';
          final exception = FirebaseFunctionsException(
            code: 'test-error',
            message: 'Test error message',
          );

          when(
            mockFunctions.httpsCallable(
              'populate_joke',
              options: anyNamed('options'),
            ),
          ).thenReturn(mockCallable);
          when(mockCallable.call({'joke_id': jokeId})).thenThrow(exception);

          // act
          final result = await service.populateJoke(jokeId);

          // assert
          expect(result, isNotNull);
          expect(result!['success'], isFalse);
          expect(
            result['error'],
            contains('Function error: Test error message'),
          );
        },
      );

      test(
        'should return error with generic message when unexpected error occurs',
        () async {
          // arrange
          const jokeId = 'test-joke-id';

          when(
            mockFunctions.httpsCallable(
              'populate_joke',
              options: anyNamed('options'),
            ),
          ).thenReturn(mockCallable);
          when(
            mockCallable.call({'joke_id': jokeId}),
          ).thenThrow(Exception('Generic error'));

          // act
          final result = await service.populateJoke(jokeId);

          // assert
          expect(result, isNotNull);
          expect(result!['success'], isFalse);
          expect(result['error'], contains('Unexpected error'));
        },
      );
    });

    group('createJoke', () {
      test('should return true when joke creation succeeds', () async {
        // arrange
        const setupText = 'Test setup';
        const punchlineText = 'Test punchline';
        const responseData = {'success': true, 'joke_id': 'test-id'};

        when(mockResult.data).thenReturn(responseData);
        when(
          mockCallable.call({
            'joke_data': {
              'setup_text': setupText,
              'punchline_text': punchlineText,
              'setup_image_url': null,
              'punchline_image_url': null,
            },
          }),
        ).thenAnswer((_) async => mockResult);
        when(
          mockFunctions.httpsCallable('create-joke'),
        ).thenReturn(mockCallable);

        // act
        final result = await service.createJoke(
          setupText: setupText,
          punchlineText: punchlineText,
        );

        // assert
        expect(result, isTrue);
        verify(mockFunctions.httpsCallable('create-joke')).called(1);
      });
    });

    group('createJokeWithResponse', () {
      test(
        'should return success response when joke creation succeeds',
        () async {
          // arrange
          const setupText = 'Test setup';
          const punchlineText = 'Test punchline';
          const mockResponseData = {'joke_id': 'test-id'};
          const expectedData = {'success': true, 'data': mockResponseData};

          when(mockResult.data).thenReturn(mockResponseData);
          when(
            mockCallable.call({
              'joke_data': {
                'setup_text': setupText,
                'punchline_text': punchlineText,
                'setup_image_url': null,
                'punchline_image_url': null,
              },
            }),
          ).thenAnswer((_) async => mockResult);
          when(
            mockFunctions.httpsCallable('create_joke'),
          ).thenReturn(mockCallable);

          // act
          final result = await service.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
          );

          // assert
          expect(result, equals(expectedData));
          verify(mockFunctions.httpsCallable('create_joke')).called(1);
        },
      );
    });
  });
}
