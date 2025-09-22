import 'package:flutter/foundation.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

/// Result of a share operation
class ShareOperationResult {
  final bool success;
  final ShareResultStatus status;
  final String shareDestination;

  const ShareOperationResult(this.success, this.status, this.shareDestination);
}

/// Abstract interface for platform sharing functionality
abstract class PlatformShareService {
  Future<ShareResult> shareFiles(
    List<XFile> files, {
    String? subject,
    String? text,
  });
}

/// Production implementation of platform sharing
class PlatformShareServiceImpl implements PlatformShareService {
  @override
  Future<ShareResult> shareFiles(
    List<XFile> files, {
    String? subject,
    String? text,
  }) async {
    final result = await Share.shareXFiles(
      files,
      subject: subject,
      text: text,
    );
    debugPrint('PlatformShareServiceImpl shareFiles result: $result');
    return result;
  }
}

/// Abstract interface for joke sharing service
/// This allows for easy mocking in tests and future strategy implementations
abstract class JokeShareService {
  /// Share a joke using the default sharing method (images + text)
  Future<bool> shareJoke(
    Joke joke, {
    required String jokeContext,
    String subject = 'Thought this might make you smile 😊',
    String text = 'Freshly baked laughs from snickerdoodlejokes.com 🍪',
  });
}

/// Implementation of joke sharing service using share_plus
class JokeShareServiceImpl implements JokeShareService {
  final ImageService _imageService;
  final AnalyticsService _analyticsService;
  final JokeReactionsService _reactionsService;
  final PlatformShareService _platformShareService;
  final AppUsageService _appUsageService;
  final ReviewPromptCoordinator _reviewPromptCoordinator;

  JokeShareServiceImpl({
    required ImageService imageService,
    required AnalyticsService analyticsService,
    required JokeReactionsService reactionsService,
    required PlatformShareService platformShareService,
    required AppUsageService appUsageService,
    required ReviewPromptCoordinator reviewPromptCoordinator,
  }) : _imageService = imageService,
       _analyticsService = analyticsService,
       _reactionsService = reactionsService,
       _platformShareService = platformShareService,
       _appUsageService = appUsageService,
       _reviewPromptCoordinator = reviewPromptCoordinator;

  @override
  Future<bool> shareJoke(
    Joke joke, {
    required String jokeContext,
    String subject = 'Thought this might make you smile 😊',
    String text = 'Freshly baked laughs from snickerdoodlejokes.com 🍪',
  }) async {
    // For now, use the images sharing method as default
    // Track share initiation
    _analyticsService.logJokeShareInitiated(
      joke.id,
      jokeContext: jokeContext,
      shareMethod: 'images',
    );
    // This can be expanded to use different strategies based on joke content
    final shareResult = await _shareJokeImagesWithResult(
      joke,
      jokeContext: jokeContext,
      subject: subject,
      text: text,
    );

    // Only perform follow-up actions if user actually shared
    if (shareResult.success) {
      // Save share reaction to SharedPreferences and increment count in Firestore
      await _reactionsService.addUserReaction(joke.id, JokeReactionType.share);

      // Increment local shared jokes counter
      await _appUsageService.incrementSharedJokesCount();

      // Log successful share analytics
      final totalShared = await _appUsageService.getNumSharedJokes();
      _analyticsService.logJokeShareSuccess(
        joke.id,
        jokeContext: jokeContext,
        shareMethod: 'images',
        shareDestination: shareResult.shareDestination,
        totalJokesShared: totalShared,
      );

      // Trigger review check only on successful share
      await _reviewPromptCoordinator.maybePromptForReview(
        source: ReviewRequestSource.auto,
      );
    } else {
      // Log cancellation or failure
      _analyticsService.logJokeShareCanceled(
        joke.id,
        jokeContext: jokeContext,
        shareMethod: 'images',
        shareDestination: shareResult.shareDestination,
      );
    }

    return shareResult.success;
  }

  Future<ShareOperationResult> _shareJokeImagesWithResult(
    Joke joke, {
    required String jokeContext,
    required String subject,
    required String text,
  }) async {
    bool shareSuccessful = false;
    ShareResultStatus shareStatus = ShareResultStatus.dismissed; // default
    String shareDestination = "unknown";
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
        final setupFile = await _imageService.getCachedFileFromUrl(
          urls.setupUrl!,
        );
        final punchlineFile = await _imageService.getCachedFileFromUrl(
          urls.punchlineUrl!,
        );
        if (setupFile != null && punchlineFile != null) {
          files.add(setupFile);
          files.add(punchlineFile);
        }
      }

      if (files.isEmpty) {
        throw Exception('No images could be downloaded for sharing');
      }

      // Apply watermark overlay to each file before sharing
      final List<XFile> brandedFiles = await _imageService.addWatermarkToFiles(
        files,
      );

      final result = await _platformShareService.shareFiles(
        brandedFiles,
        subject: subject,
        text: text,
      );

      // Check if user actually shared (not dismissed)
      shareSuccessful = result.status == ShareResultStatus.success;
      shareStatus = result.status;
      shareDestination = result.raw;
    } catch (e) {
      debugPrint('Error sharing joke images: $e');
      // Log error-specific analytics
      _analyticsService.logErrorJokeShare(
        joke.id,
        jokeContext: jokeContext,
        shareMethod: 'images',
        errorMessage: e.toString(),
        errorContext: 'share_images',
        exceptionType: e.runtimeType.toString(),
      );
      shareSuccessful = false;
      shareStatus = ShareResultStatus.unavailable; // error state
    }

    return ShareOperationResult(shareSuccessful, shareStatus, shareDestination);
  }
}
