import 'package:flutter/foundation.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

/// Abstract interface for joke sharing service
/// This allows for easy mocking in tests and future strategy implementations
abstract class JokeShareService {
  /// Share a joke using the default sharing method (images + text)
  Future<bool> shareJoke(Joke joke, {required String jokeContext});
}

/// Implementation of joke sharing service using share_plus
class JokeShareServiceImpl implements JokeShareService {
  final ImageService _imageService;
  final JokeReactionsService _jokeReactionsService;

  JokeShareServiceImpl({
    required ImageService imageService,
    required JokeReactionsService jokeReactionsService,
  }) : _imageService = imageService,
       _jokeReactionsService = jokeReactionsService;

  @override
  Future<bool> shareJoke(Joke joke, {required String jokeContext}) async {
    // For now, use the images sharing method as default
    // This can be expanded to use different strategies based on joke content
    final shareSuccessful = await _shareJokeImages(
      joke,
      jokeContext: jokeContext,
    );

    // Only perform follow-up actions if user actually shared
    if (shareSuccessful) {
      await _jokeReactionsService.addUserReaction(
        joke.id,
        JokeReactionType.share,
        jokeContext: jokeContext,
      );
    }

    return shareSuccessful;
  }

  Future<bool> _shareJokeImages(
    Joke joke, {
    required String jokeContext,
  }) async {
    bool shareSuccessful = false;
    try {
      // Check if joke has images
      final hasSetupImage =
          joke.setupImageUrl != null && joke.setupImageUrl!.isNotEmpty;
      final hasPunchlineImage =
          joke.punchlineImageUrl != null && joke.punchlineImageUrl!.isNotEmpty;

      if (!hasSetupImage || !hasPunchlineImage) {
        throw Exception('Joke has no images for sharing');
      }

      // Get processed URLs and ensure images are cached
      final urls = await _imageService.precacheJokeImages(joke);
      final List<XFile> files = [];

      // Only share images if both are available
      if (urls.setupUrl != null && urls.punchlineUrl != null) {
        final setupFile = await _getCachedFileFromUrl(urls.setupUrl!);
        final punchlineFile = await _getCachedFileFromUrl(urls.punchlineUrl!);
        if (setupFile != null && punchlineFile != null) {
          files.add(setupFile);
          files.add(punchlineFile);
        }
      }

      if (files.isEmpty) {
        throw Exception('No images could be downloaded for sharing');
      }

      final result = await SharePlus.instance.share(
        ShareParams(subject: 'Check out this joke!', files: files),
      );

      // Check if user actually shared (not dismissed)
      shareSuccessful = result.status == ShareResultStatus.success;
    } catch (e) {
      debugPrint('Error sharing joke images: $e');
      shareSuccessful = false;
    }

    return shareSuccessful;
  }

  /// Get cached file from URL using DefaultCacheManager
  Future<XFile?> _getCachedFileFromUrl(String processedUrl) async {
    try {
      final imageFile = await DefaultCacheManager().getSingleFile(processedUrl);
      return XFile(imageFile.path);
    } catch (e) {
      debugPrint('Error getting cached file from URL: $e');
      return null;
    }
  }
}
