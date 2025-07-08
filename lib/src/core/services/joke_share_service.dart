import 'package:flutter/foundation.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

/// Abstract interface for joke sharing service
/// This allows for easy mocking in tests and future strategy implementations
abstract class JokeShareService {
  /// Share a joke using the default sharing method (images + text)
  Future<bool> shareJoke(Joke joke, {required String jokeContext});

  /// Share joke images with text
  Future<bool> shareJokeImages(Joke joke, {required String jokeContext});

  /// Share joke text only
  Future<bool> shareJokeText(Joke joke, {required String jokeContext});
}

/// Implementation of joke sharing service using share_plus
class JokeShareServiceImpl implements JokeShareService {
  final AnalyticsService _analyticsService;
  final ImageService _imageService;

  JokeShareServiceImpl({
    required AnalyticsService analyticsService,
    required ImageService imageService,
  }) : _analyticsService = analyticsService,
       _imageService = imageService;

  @override
  Future<bool> shareJoke(Joke joke, {required String jokeContext}) async {
    // For now, use the images sharing method as default
    // This can be expanded to use different strategies based on joke content
    return await shareJokeImages(joke, jokeContext: jokeContext);
  }

  @override
  Future<bool> shareJokeImages(Joke joke, {required String jokeContext}) async {
    try {
      // Check if joke has images
      final hasSetupImage =
          joke.setupImageUrl != null && joke.setupImageUrl!.isNotEmpty;
      final hasPunchlineImage =
          joke.punchlineImageUrl != null && joke.punchlineImageUrl!.isNotEmpty;

      if (!hasSetupImage || !hasPunchlineImage) {
        // Fall back to text sharing if images are not available
        return await shareJokeText(joke, jokeContext: jokeContext);
      }

      // Get processed URLs and ensure images are cached
      final urls = await CachedJokeImage.precacheJokeImages(
        joke,
        _imageService,
      );
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
        // If no images could be downloaded, fall back to text
        return await shareJokeText(joke, jokeContext: jokeContext);
      }

      final result = await SharePlus.instance.share(
        ShareParams(subject: 'Check out this joke!', files: files),
      );

      // Check if user actually shared (not dismissed)
      final shareSuccessful = result.status == ShareResultStatus.success;

      // Log share attempt
      await _analyticsService.logJokeShared(
        joke.id,
        shareMethod: AnalyticsShareMethod.images,
        shareSuccess: shareSuccessful,
        jokeContext: jokeContext,
      );

      return shareSuccessful;
    } catch (e) {
      debugPrint('Error sharing joke images: $e');

      // Log failed share
      await _analyticsService.logJokeShared(
        joke.id,
        shareMethod: AnalyticsShareMethod.images,
        shareSuccess: false,
        jokeContext: jokeContext,
      );

      // Try fallback to text sharing
      return await shareJokeText(joke, jokeContext: jokeContext);
    }
  }

  @override
  Future<bool> shareJokeText(Joke joke, {required String jokeContext}) async {
    try {
      final shareText = _buildShareText(joke);

      final result = await SharePlus.instance.share(
        ShareParams(text: shareText, subject: 'Check out this joke!'),
      );

      // Check if user actually shared (not dismissed)
      final shareSuccessful = result.status == ShareResultStatus.success;

      // Log share attempt
      await _analyticsService.logJokeShared(
        joke.id,
        shareMethod: AnalyticsShareMethod.text,
        shareSuccess: shareSuccessful,
        jokeContext: jokeContext,
      );

      return shareSuccessful;
    } catch (e) {
      debugPrint('Error sharing joke text: $e');

      // Log failed share
      await _analyticsService.logJokeShared(
        joke.id,
        shareMethod: AnalyticsShareMethod.text,
        shareSuccess: false,
        jokeContext: jokeContext,
      );

      return false;
    }
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

  /// Build the text content for sharing
  String _buildShareText(Joke joke) {
    final buffer = StringBuffer();

    // Add setup text
    if (joke.setupText.isNotEmpty == true) {
      buffer.writeln(joke.setupText);
      buffer.writeln();
    }

    // Add punchline text
    if (joke.punchlineText.isNotEmpty == true) {
      buffer.writeln(joke.punchlineText);
      buffer.writeln();
    }

    // Add app attribution
    buffer.writeln('Shared from Snickerdoodle');

    return buffer.toString().trim();
  }
}
