import 'package:flutter/foundation.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
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
    final result = await SharePlus.instance.share(
      ShareParams(subject: subject, files: files, text: text),
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
  final RemoteConfigValues _remoteConfig;

  JokeShareServiceImpl({
    required ImageService imageService,
    required AnalyticsService analyticsService,
    required JokeReactionsService reactionsService,
    required PlatformShareService platformShareService,
    required AppUsageService appUsageService,
    required ReviewPromptCoordinator reviewPromptCoordinator,
    required RemoteConfigValues remoteConfig,
  })  : _imageService = imageService,
        _analyticsService = analyticsService,
        _reactionsService = reactionsService,
        _platformShareService = platformShareService,
        _appUsageService = appUsageService,
        _reviewPromptCoordinator = reviewPromptCoordinator,
        _remoteConfig = remoteConfig;

  @override
  Future<bool> shareJoke(
    Joke joke, {
    required String jokeContext,
    String subject = 'Thought this might make you smile 😊',
    String text = 'Freshly baked laughs from snickerdoodlejokes.com 🍪',
  }) async {
    final bool stackImages =
        _remoteConfig.getBool(RemoteParam.shareJokeImageStacked);
    final String shareMethod = stackImages ? 'image_stacked' : 'images_separate';

    _analyticsService.logJokeShareInitiated(
      joke.id,
      jokeContext: jokeContext,
      shareMethod: shareMethod,
    );

    final shareResult = await _shareJokeImagesWithResult(
      joke,
      jokeContext: jokeContext,
      subject: subject,
      text: text,
      stackImages: stackImages,
    );

    if (shareResult.success) {
      await _reactionsService.addUserReaction(joke.id, JokeReactionType.share);
      await _appUsageService.incrementSharedJokesCount();
      final totalShared = await _appUsageService.getNumSharedJokes();
      _analyticsService.logJokeShareSuccess(
        joke.id,
        jokeContext: jokeContext,
        shareMethod: shareMethod,
        shareDestination: shareResult.shareDestination,
        totalJokesShared: totalShared,
      );
      await _reviewPromptCoordinator.maybePromptForReview(
        source: ReviewRequestSource.auto,
      );
    } else {
      _analyticsService.logJokeShareCanceled(
        joke.id,
        jokeContext: jokeContext,
        shareMethod: shareMethod,
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
    required bool stackImages,
  }) async {
    bool shareSuccessful = false;
    ShareResultStatus shareStatus = ShareResultStatus.dismissed;
    String shareDestination = "unknown";
    try {
      final hasSetupImage =
          joke.setupImageUrl != null && joke.setupImageUrl!.isNotEmpty;
      final hasPunchlineImage =
          joke.punchlineImageUrl != null && joke.punchlineImageUrl!.isNotEmpty;

      if (!hasSetupImage || !hasPunchlineImage) {
        throw Exception('Joke has no images for sharing');
      }

      final urls = await _imageService.precacheJokeImages(joke);
      if (urls.setupUrl == null || urls.punchlineUrl == null) {
        throw Exception('Failed to precache joke images');
      }

      final setupFile =
          await _imageService.getCachedFileFromUrl(urls.setupUrl!);
      final punchlineFile =
          await _imageService.getCachedFileFromUrl(urls.punchlineUrl!);

      if (setupFile == null || punchlineFile == null) {
        throw Exception('No images could be downloaded for sharing');
      }

      List<XFile> brandedFiles = [];
      if (stackImages) {
        final stackedFile = await _imageService.stackImagesVertically(
          setupFile,
          punchlineFile,
        );
        if (stackedFile != null) {
          brandedFiles.add(await _imageService.addWatermarkToFile(stackedFile));
        }
      } else {
        brandedFiles = await _imageService.addWatermarkToFiles(
          [setupFile, punchlineFile],
        );
      }

      if (brandedFiles.isEmpty) {
        throw Exception('Failed to process images for sharing');
      }

      final result = await _platformShareService.shareFiles(
        brandedFiles,
        subject: subject,
        text: text,
      );

      shareSuccessful = result.status == ShareResultStatus.success;
      shareStatus = result.status;
      shareDestination = result.raw;
    } catch (e) {
      debugPrint('Error sharing joke images: $e');
      _analyticsService.logErrorJokeShare(
        joke.id,
        jokeContext: jokeContext,
        shareMethod: stackImages ? 'image_stacked' : 'images_separate',
        errorMessage: e.toString(),
        errorContext: 'share_images',
        exceptionType: e.runtimeType.toString(),
      );
      shareSuccessful = false;
      shareStatus = ShareResultStatus.unavailable;
    }

    return ShareOperationResult(shareSuccessful, shareStatus, shareDestination);
  }
}
