import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/admin_review_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  setUpAll(() {
    // Required by mocktail when using any() with non-primitive types
    registerFallbackValue(JokeAdminRating.unreviewed);
  });
  group('AdminReviewService', () {
    late AdminReviewService service;
    late MockJokeRepository mockRepository;

    setUp(() {
      mockRepository = MockJokeRepository();
      service = AdminReviewService(jokeRepository: mockRepository);
    });

    test(
      'getAdminRating returns UNREVIEWED when admin_rating is null',
      () async {
        final joke = Joke(
          id: 'j1',
          setupText: 's',
          punchlineText: 'p',
          adminRating: null,
          state: JokeState.unreviewed,
        );

        when(
          () => mockRepository.getJokeByIdStream('j1'),
        ).thenAnswer((_) => Stream.value(joke));

        final rating = await service.getAdminRating('j1');
        expect(rating, JokeAdminRating.unreviewed);
      },
    );

    test('toggleApprove sets rating APPROVED when state is mutable', () async {
      final joke = Joke(
        id: 'j1',
        setupText: 's',
        punchlineText: 'p',
        adminRating: JokeAdminRating.unreviewed,
        state: JokeState.unreviewed,
      );

      when(
        () => mockRepository.getJokeByIdStream('j1'),
      ).thenAnswer((_) => Stream.value(joke));
      when(
        () => mockRepository.setAdminRatingAndState(any(), any()),
      ).thenAnswer((_) async {});

      await service.toggleApprove('j1');

      verify(
        () => mockRepository.setAdminRatingAndState(
          'j1',
          JokeAdminRating.approved,
        ),
      ).called(1);
    });

    test('toggleReject sets rating REJECTED when state is mutable', () async {
      final joke = Joke(
        id: 'j1',
        setupText: 's',
        punchlineText: 'p',
        adminRating: JokeAdminRating.unreviewed,
        state: JokeState.approved, // still mutable
      );

      when(
        () => mockRepository.getJokeByIdStream('j1'),
      ).thenAnswer((_) => Stream.value(joke));
      when(
        () => mockRepository.setAdminRatingAndState(any(), any()),
      ).thenAnswer((_) async {});

      await service.toggleReject('j1');

      verify(
        () => mockRepository.setAdminRatingAndState(
          'j1',
          JokeAdminRating.rejected,
        ),
      ).called(1);
    });

    test('toggle no-ops when state is non-mutable (draft)', () async {
      final joke = Joke(
        id: 'j1',
        setupText: 's',
        punchlineText: 'p',
        adminRating: JokeAdminRating.unreviewed,
        state: JokeState.draft,
      );

      when(
        () => mockRepository.getJokeByIdStream('j1'),
      ).thenAnswer((_) => Stream.value(joke));

      await service.toggleApprove('j1');
      await service.toggleReject('j1');

      verifyNever(() => mockRepository.setAdminRatingAndState(any(), any()));
    });
  });
}
