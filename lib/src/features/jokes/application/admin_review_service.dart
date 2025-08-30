import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

/// AdminReviewService (replaces JokeAdminThumbsService)
final adminReviewServiceProvider = Provider<AdminReviewService>((ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  return AdminReviewService(jokeRepository: jokeRepository);
});

/// Central service for admin rating logic (no legacy num_thumbs_* usage)
class AdminReviewService {
  final JokeRepository _jokeRepository;

  AdminReviewService({required JokeRepository jokeRepository})
    : _jokeRepository = jokeRepository;

  Future<Joke?> _getJoke(String jokeId) async {
    return _jokeRepository.getJokeByIdStream(jokeId).first;
  }

  /// Get current admin rating, treat null as UNREVIEWED
  Future<JokeAdminRating> getAdminRating(String jokeId) async {
    final joke = await _getJoke(jokeId);
    return joke?.adminRating ?? JokeAdminRating.unreviewed;
  }

  /// Whether admin rating can be changed given the joke's state
  bool canChangeRating(Joke? joke) {
    final state = joke?.state;
    if (state == null) return false;
    return state.canMutateAdminRating;
  }

  Future<void> toggleApprove(String jokeId) async {
    final joke = await _getJoke(jokeId);
    if (!canChangeRating(joke)) return;
    final current = joke!.adminRating ?? JokeAdminRating.unreviewed;
    final next = current == JokeAdminRating.approved
        ? JokeAdminRating.unreviewed
        : JokeAdminRating.approved;
    await _jokeRepository.setAdminRatingAndState(jokeId, next);
  }

  Future<void> toggleReject(String jokeId) async {
    final joke = await _getJoke(jokeId);
    if (!canChangeRating(joke)) return;
    final current = joke!.adminRating ?? JokeAdminRating.unreviewed;
    final next = current == JokeAdminRating.rejected
        ? JokeAdminRating.unreviewed
        : JokeAdminRating.rejected;
    await _jokeRepository.setAdminRatingAndState(jokeId, next);
  }
}
