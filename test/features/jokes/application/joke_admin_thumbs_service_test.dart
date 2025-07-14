import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_admin_thumbs_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

// Fake classes for fallback values
class FakeJoke extends Fake implements Joke {}

void main() {
  group('JokeAdminThumbsService Tests', () {
    late JokeAdminThumbsService service;
    late MockJokeRepository mockRepository;

    setUp(() {
      mockRepository = MockJokeRepository();

      // Register fallbacks for mocktail
      registerFallbackValue(JokeAdminRating.approved);
      registerFallbackValue(FakeJoke());

      service = JokeAdminThumbsService(jokeRepository: mockRepository);

      // Mock setAdminRating method
      when(
        () => mockRepository.setAdminRating(any(), any()),
      ).thenAnswer((_) async {});
    });

    group('getAdminRating', () {
      test('should return admin rating when available', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.approved,
          numThumbsUp: 1,
          numThumbsDown: 0,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.getAdminRating('joke1');

        expect(result, equals(JokeAdminRating.approved));
      });

      test(
        'should fallback to legacy thumbs up when admin rating is null',
        () async {
          final joke = Joke(
            id: 'joke1',
            setupText: 'Setup',
            punchlineText: 'Punchline',
            adminRating: null,
            numThumbsUp: 1,
            numThumbsDown: 0,
          );

          when(
            () => mockRepository.getJokeByIdStream('joke1'),
          ).thenAnswer((_) => Stream.value(joke));

          final result = await service.getAdminRating('joke1');

          expect(result, equals(JokeAdminRating.approved));
        },
      );

      test(
        'should fallback to legacy thumbs down when admin rating is null',
        () async {
          final joke = Joke(
            id: 'joke1',
            setupText: 'Setup',
            punchlineText: 'Punchline',
            adminRating: null,
            numThumbsUp: 0,
            numThumbsDown: 1,
          );

          when(
            () => mockRepository.getJokeByIdStream('joke1'),
          ).thenAnswer((_) => Stream.value(joke));

          final result = await service.getAdminRating('joke1');

          expect(result, equals(JokeAdminRating.rejected));
        },
      );

      test('should return null when no rating is set', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: null,
          numThumbsUp: 0,
          numThumbsDown: 0,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.getAdminRating('joke1');

        expect(result, isNull);
      });

      test('should return null when joke is not found', () async {
        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(null));

        final result = await service.getAdminRating('joke1');

        expect(result, isNull);
      });

      test('should return null when repository throws error', () async {
        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenThrow(Exception('Repository error'));

        final result = await service.getAdminRating('joke1');

        expect(result, isNull);
      });

      test('should return null when repository is null', () async {
        final serviceWithoutRepo = JokeAdminThumbsService(jokeRepository: null);

        final result = await serviceWithoutRepo.getAdminRating('joke1');

        expect(result, isNull);
      });

      test('should prefer admin rating over legacy fields', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.rejected,
          numThumbsUp: 1, // Legacy field suggests approved
          numThumbsDown: 0,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.getAdminRating('joke1');

        expect(result, equals(JokeAdminRating.rejected));
      });

      test('should handle ambiguous legacy fields by returning null', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: null,
          numThumbsUp: 1,
          numThumbsDown: 1, // Both set - ambiguous
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.getAdminRating('joke1');

        expect(result, isNull);
      });
    });

    group('hasThumbsUp', () {
      test('should return true when joke has thumbs up', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.approved,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.hasThumbsUp('joke1');

        expect(result, isTrue);
      });

      test('should return false when joke has thumbs down', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.rejected,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.hasThumbsUp('joke1');

        expect(result, isFalse);
      });

      test('should return false when joke has no rating', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: null,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.hasThumbsUp('joke1');

        expect(result, isFalse);
      });
    });

    group('hasThumbsDown', () {
      test('should return true when joke has thumbs down', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.rejected,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.hasThumbsDown('joke1');

        expect(result, isTrue);
      });

      test('should return false when joke has thumbs up', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.approved,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.hasThumbsDown('joke1');

        expect(result, isFalse);
      });

      test('should return false when joke has no rating', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: null,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        final result = await service.hasThumbsDown('joke1');

        expect(result, isFalse);
      });
    });

    group('setThumbsUp', () {
      test('should set thumbs up rating', () async {
        await service.setThumbsUp('joke1');

        verify(
          () =>
              mockRepository.setAdminRating('joke1', JokeAdminRating.approved),
        ).called(1);
      });

      test('should handle repository error gracefully', () async {
        when(
          () => mockRepository.setAdminRating(any(), any()),
        ).thenThrow(Exception('Repository error'));

        // Should not throw
        await service.setThumbsUp('joke1');
      });

      test('should do nothing when repository is null', () async {
        final serviceWithoutRepo = JokeAdminThumbsService(jokeRepository: null);

        // Should not throw
        await serviceWithoutRepo.setThumbsUp('joke1');
      });
    });

    group('setThumbsDown', () {
      test('should set thumbs down rating', () async {
        await service.setThumbsDown('joke1');

        verify(
          () =>
              mockRepository.setAdminRating('joke1', JokeAdminRating.rejected),
        ).called(1);
      });

      test('should handle repository error gracefully', () async {
        when(
          () => mockRepository.setAdminRating(any(), any()),
        ).thenThrow(Exception('Repository error'));

        // Should not throw
        await service.setThumbsDown('joke1');
      });

      test('should do nothing when repository is null', () async {
        final serviceWithoutRepo = JokeAdminThumbsService(jokeRepository: null);

        // Should not throw
        await serviceWithoutRepo.setThumbsDown('joke1');
      });
    });

    group('clearThumbs', () {
      test('should clear thumbs rating', () async {
        await service.clearThumbs('joke1');

        verify(() => mockRepository.setAdminRating('joke1', null)).called(1);
      });

      test('should handle repository error gracefully', () async {
        when(
          () => mockRepository.setAdminRating(any(), any()),
        ).thenThrow(Exception('Repository error'));

        // Should not throw
        await service.clearThumbs('joke1');
      });

      test('should do nothing when repository is null', () async {
        final serviceWithoutRepo = JokeAdminThumbsService(jokeRepository: null);

        // Should not throw
        await serviceWithoutRepo.clearThumbs('joke1');
      });
    });

    group('toggleThumbsUp', () {
      test('should set thumbs up when no rating exists', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: null,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        await service.toggleThumbsUp('joke1');

        verify(
          () =>
              mockRepository.setAdminRating('joke1', JokeAdminRating.approved),
        ).called(1);
      });

      test('should set thumbs up when thumbs down exists', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.rejected,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        await service.toggleThumbsUp('joke1');

        verify(
          () =>
              mockRepository.setAdminRating('joke1', JokeAdminRating.approved),
        ).called(1);
      });

      test('should clear thumbs when thumbs up already exists', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.approved,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        await service.toggleThumbsUp('joke1');

        verify(() => mockRepository.setAdminRating('joke1', null)).called(1);
      });
    });

    group('toggleThumbsDown', () {
      test('should set thumbs down when no rating exists', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: null,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        await service.toggleThumbsDown('joke1');

        verify(
          () =>
              mockRepository.setAdminRating('joke1', JokeAdminRating.rejected),
        ).called(1);
      });

      test('should set thumbs down when thumbs up exists', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.approved,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        await service.toggleThumbsDown('joke1');

        verify(
          () =>
              mockRepository.setAdminRating('joke1', JokeAdminRating.rejected),
        ).called(1);
      });

      test('should clear thumbs when thumbs down already exists', () async {
        final joke = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.rejected,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(joke));

        await service.toggleThumbsDown('joke1');

        verify(() => mockRepository.setAdminRating('joke1', null)).called(1);
      });
    });

    group('mutual exclusivity', () {
      test('should be mutually exclusive - only one can be true', () async {
        final jokeApproved = Joke(
          id: 'joke1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.approved,
        );

        final jokeRejected = Joke(
          id: 'joke2',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          adminRating: JokeAdminRating.rejected,
        );

        when(
          () => mockRepository.getJokeByIdStream('joke1'),
        ).thenAnswer((_) => Stream.value(jokeApproved));
        when(
          () => mockRepository.getJokeByIdStream('joke2'),
        ).thenAnswer((_) => Stream.value(jokeRejected));

        expect(await service.hasThumbsUp('joke1'), isTrue);
        expect(await service.hasThumbsDown('joke1'), isFalse);

        expect(await service.hasThumbsUp('joke2'), isFalse);
        expect(await service.hasThumbsDown('joke2'), isTrue);
      });
    });
  });
}
 