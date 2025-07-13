import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

final jokeAdminThumbsServiceProvider = Provider<JokeAdminThumbsService>((ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  return JokeAdminThumbsService(jokeRepository: jokeRepository);
});

/// Service for managing admin thumbs (thumbs up/down) functionality
/// Uses Firestore admin_rating field with fallback to legacy num_thumbs_up/num_thumbs_down fields
/// Handles mutual exclusivity (thumbs up and down are mutually exclusive)
/// No SharedPreferences tracking or analytics logging
class JokeAdminThumbsService {
  final JokeRepository? _jokeRepository;

  JokeAdminThumbsService({JokeRepository? jokeRepository})
    : _jokeRepository = jokeRepository;

  /// Get the current admin rating for a joke
  /// Returns null if no rating is set
  Future<JokeAdminRating?> getAdminRating(String jokeId) async {
    if (_jokeRepository == null) return null;

    try {
      final joke = await _jokeRepository.getJokeByIdStream(jokeId).first;
      if (joke == null) return null;

      // First try to read from the new admin_rating field
      if (joke.adminRating != null) {
        return joke.adminRating;
      }

      // Fallback to legacy fields if admin_rating is not set
      if (joke.numThumbsUp > 0 && joke.numThumbsDown == 0) {
        return JokeAdminRating.approved;
      } else if (joke.numThumbsDown > 0 && joke.numThumbsUp == 0) {
        return JokeAdminRating.rejected;
      }

      return null; // No rating set
    } catch (e) {
      // Handle any errors gracefully
      return null;
    }
  }

  /// Check if a joke has thumbs up rating
  Future<bool> hasThumbsUp(String jokeId) async {
    final rating = await getAdminRating(jokeId);
    return rating == JokeAdminRating.approved;
  }

  /// Check if a joke has thumbs down rating
  Future<bool> hasThumbsDown(String jokeId) async {
    final rating = await getAdminRating(jokeId);
    return rating == JokeAdminRating.rejected;
  }

  /// Set thumbs up rating (removes thumbs down if present)
  Future<void> setThumbsUp(String jokeId) async {
    if (_jokeRepository == null) return;

    try {
      await _jokeRepository.setAdminRating(jokeId, JokeAdminRating.approved);
    } catch (e) {
      // Handle errors gracefully
    }
  }

  /// Set thumbs down rating (removes thumbs up if present)
  Future<void> setThumbsDown(String jokeId) async {
    if (_jokeRepository == null) return;

    try {
      await _jokeRepository.setAdminRating(jokeId, JokeAdminRating.rejected);
    } catch (e) {
      // Handle errors gracefully
    }
  }

  /// Clear all thumbs ratings (removes both thumbs up and down)
  Future<void> clearThumbs(String jokeId) async {
    if (_jokeRepository == null) return;

    try {
      await _jokeRepository.setAdminRating(jokeId, null);
    } catch (e) {
      // Handle errors gracefully
    }
  }

  /// Toggle thumbs up rating
  /// If already thumbs up, clears the rating
  /// If thumbs down or no rating, sets thumbs up
  Future<void> toggleThumbsUp(String jokeId) async {
    final currentRating = await getAdminRating(jokeId);

    if (currentRating == JokeAdminRating.approved) {
      await clearThumbs(jokeId);
    } else {
      await setThumbsUp(jokeId);
    }
  }

  /// Toggle thumbs down rating
  /// If already thumbs down, clears the rating
  /// If thumbs up or no rating, sets thumbs down
  Future<void> toggleThumbsDown(String jokeId) async {
    final currentRating = await getAdminRating(jokeId);

    if (currentRating == JokeAdminRating.rejected) {
      await clearThumbs(jokeId);
    } else {
      await setThumbsDown(jokeId);
    }
  }
}
