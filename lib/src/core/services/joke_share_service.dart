import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

/// Internal exception to signal that the user aborted share preparation.
class SharePreparationCanceledException implements Exception {}

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
    AppLogger.debug('PlatformShareServiceImpl shareFiles result: $result');
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
    SharePreparationController? controller,
    required BuildContext context,
  });
}

/// Implementation of joke sharing service using share_plus
class JokeShareServiceImpl implements JokeShareService {
  final ImageService _imageService;
  final AnalyticsService _analyticsService;
  final JokeReactionsService _reactionsService;
  final PlatformShareService _platformShareService;
  final AppUsageService _appUsageService;
  final PerformanceService _performanceService;
  final RemoteConfigValues _remoteConfigValues;
  final bool Function() _getRevealModeEnabled;

  JokeShareServiceImpl({
    required ImageService imageService,
    required AnalyticsService analyticsService,
    required JokeReactionsService reactionsService,
    required PlatformShareService platformShareService,
    required AppUsageService appUsageService,
    required PerformanceService performanceService,
    required RemoteConfigValues remoteConfigValues,
    required bool Function() getRevealModeEnabled,
  }) : _imageService = imageService,
       _analyticsService = analyticsService,
       _reactionsService = reactionsService,
       _platformShareService = platformShareService,
       _appUsageService = appUsageService,
       _performanceService = performanceService,
       _remoteConfigValues = remoteConfigValues,
       _getRevealModeEnabled = getRevealModeEnabled;

  @override
  Future<bool> shareJoke(
    Joke joke, {
    required String jokeContext,
    String subject = 'Thought this might make you smile 😊',
    SharePreparationController? controller,
    required BuildContext context,
  }) async {
    // For now, use the images sharing method as default
    // Track share initiation
    _analyticsService.logJokeShareInitiated(joke.id, jokeContext: jokeContext);
    // This can be expanded to use different strategies based on joke content
    final shareResult = await _shareJokeImagesWithResult(
      joke,
      jokeContext: jokeContext,
      subject: subject,
      controller: controller,
    );

    // Only perform follow-up actions if user actually shared
    if (shareResult.success) {
      // Save share reaction to SharedPreferences and increment count in Firestore
      await _reactionsService.addUserReaction(
        joke.id,
        JokeReactionType.share,
        context: context, // ignore: use_build_context_synchronously
      );

      // Increment local shared jokes counter
      await _appUsageService.incrementSharedJokesCount();

      // Log successful share analytics
      final totalShared = await _appUsageService.getNumSharedJokes();
      _analyticsService.logJokeShareSuccess(
        joke.id,
        jokeContext: jokeContext,
        shareDestination: shareResult.shareDestination,
        totalJokesShared: totalShared,
      );
    }

    return shareResult.success;
  }

  Future<ShareOperationResult> _shareJokeImagesWithResult(
    Joke joke, {
    required String jokeContext,
    required String subject,
    SharePreparationController? controller,
  }) async {
    controller?.setProgress(0);

    final String traceKey = 'images:${joke.id}';
    _performanceService.startNamedTrace(
      name: TraceName.sharePreparation,
      key: traceKey,
      attributes: {'method': 'images', 'joke_id': joke.id},
    );
    bool shareSuccessful = false;
    ShareResultStatus shareStatus = ShareResultStatus.dismissed;
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

      // Early cancellation check
      if (controller?.isCanceled == true) {
        throw SharePreparationCanceledException();
      }

      controller?.setProgress(1);

      // Compute processed URLs directly and fetch both files in parallel
      final setupProcessedUrl = _imageService.getProcessedJokeImageUrl(
        joke.setupImageUrl,
      );
      final punchlineProcessedUrl = _imageService.getProcessedJokeImageUrl(
        joke.punchlineImageUrl,
      );

      final List<XFile> files = [];
      if (setupProcessedUrl != null && punchlineProcessedUrl != null) {
        final results = await Future.wait([
          _imageService.getCachedFileFromUrl(setupProcessedUrl),
          _imageService.getCachedFileFromUrl(punchlineProcessedUrl),
        ]);
        final setupFile = results[0];
        final punchlineFile = results[1];
        if (setupFile != null && punchlineFile != null) {
          files.add(setupFile);
          files.add(punchlineFile);
        }
        controller?.setProgress(4);
      }

      // Cancellation after download
      if (controller?.isCanceled == true) {
        throw SharePreparationCanceledException();
      }

      if (files.isEmpty) {
        throw Exception('No images could be downloaded for sharing');
      }

      final List<XFile> filesToWatermark;
      ShareImagesMode mode = _remoteConfigValues.getEnum<ShareImagesMode>(
        RemoteParam.shareImagesMode,
      );
      if (mode == ShareImagesMode.auto) {
        mode = _getRevealModeEnabled()
            ? ShareImagesMode.separate
            : ShareImagesMode.stacked;
      }
      if (mode == ShareImagesMode.stacked) {
        filesToWatermark = [await _imageService.stackImages(files)];
      } else {
        filesToWatermark = files;
      }
      controller?.setProgress(6);

      // Cancellation after stacking
      if (controller?.isCanceled == true) {
        throw SharePreparationCanceledException();
      }

      final filesToShare = await _imageService.addWatermarkToFiles(
        filesToWatermark,
      );
      controller?.setProgress(9);

      // Cancellation after watermarking
      if (controller?.isCanceled == true) {
        throw SharePreparationCanceledException();
      }

      // Stop preparation trace right before invoking platform share
      _performanceService.stopNamedTrace(
        name: TraceName.sharePreparation,
        key: traceKey,
      );

      // Notify UI to close progress just before OS sheet
      controller?.setProgress(10);
      controller?.onBeforePlatformShare?.call();
      final result = await _platformShareService.shareFiles(
        filesToShare,
        subject: subject,
      );
      if (result.status == ShareResultStatus.dismissed) {
        _analyticsService.logJokeShareCanceled(
          joke.id,
          jokeContext: jokeContext,
        );
      }

      // Check if user actually shared (not dismissed)
      shareSuccessful = result.status == ShareResultStatus.success;
      shareStatus = result.status;
      shareDestination = result.raw;
    } catch (e, _) {
      if (e is SharePreparationCanceledException) {
        _analyticsService.logJokeShareAborted(
          joke.id,
          jokeContext: jokeContext,
        );
        // User canceled: no error logging
        shareSuccessful = false;
        shareStatus = ShareResultStatus.dismissed;
      } else {
        AppLogger.warn('Error sharing joke images: $e');
        // Log error-specific analytics
        _analyticsService.logErrorJokeShare(
          joke.id,
          jokeContext: jokeContext,
          errorMessage: e.toString(),
          errorContext: 'share_images',
          exceptionType: e.runtimeType.toString(),
        );
        shareSuccessful = false;
        shareStatus = ShareResultStatus.unavailable; // error state
      }
    } finally {
      // Safe to stop multiple times; underlying service guards this
      _performanceService.stopNamedTrace(
        name: TraceName.sharePreparation,
        key: traceKey,
      );
    }

    return ShareOperationResult(shareSuccessful, shareStatus, shareDestination);
  }
}

/// Controller for cooperative cancellation and progress reporting during share preparation
class SharePreparationController extends ChangeNotifier {
  bool _canceled = false;
  bool get isCanceled => _canceled;

  /// Invoked by UI right before platform share opens
  VoidCallback? onBeforePlatformShare;

  final int _totalUnits = 10;
  int _completedUnits = 0;

  int get totalUnits => _totalUnits;
  int get completedUnits => _completedUnits;
  double get fraction => _totalUnits == 0 ? 0.0 : _completedUnits / _totalUnits;

  void cancel() {
    _canceled = true;
    notifyListeners();
  }

  /// Sets progress to a specific value within [0, totalUnits]
  void setProgress(int value) {
    _completedUnits = value.clamp(0, _totalUnits);
    notifyListeners();
  }
}
