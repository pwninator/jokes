import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

class JokeCard extends ConsumerWidget {
  final Joke joke;
  final int? index;
  final Function(int)? onImageStateChanged;
  final bool isAdminMode;
  final List<Joke>? jokesToPreload;
  final bool showSaveButton;
  final bool showShareButton;
  final bool showAdminRatingButtons;
  final bool showUserRatingButtons;
  final bool showUsageStats;
  final String? title;
  final String jokeContext;
  final JokeImageCarouselController? controller;
  final String? topRightBadgeText;
  final bool showSimilarSearchButton;
  final String? dataSource;

  const JokeCard({
    super.key,
    required this.joke,
    this.index,
    this.onImageStateChanged,
    this.isAdminMode = false,
    this.jokesToPreload,
    this.showSaveButton = false,
    this.showShareButton = false,
    this.showAdminRatingButtons = false,
    this.showUserRatingButtons = false,
    this.showUsageStats = false,
    this.title,
    required this.jokeContext,
    this.controller,
    this.topRightBadgeText,
    this.showSimilarSearchButton = false,
    this.dataSource,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Determine which state to show based on image URLs
    // Check for non-null, non-empty, and non-whitespace URLs
    final hasSetupImage =
        joke.setupImageUrl != null && joke.setupImageUrl!.trim().isNotEmpty;
    final hasPunchlineImage =
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.trim().isNotEmpty;

    if (hasSetupImage && hasPunchlineImage) {
      final bool reveal = ref.watch(jokeViewerRevealProvider);
      final mode = reveal ? JokeViewerMode.reveal : JokeViewerMode.bothAdaptive;
      // Both images available - show carousel
      return JokeImageCarousel(
        joke: joke,
        index: index,
        onImageStateChanged: onImageStateChanged,
        isAdminMode: isAdminMode,
        jokesToPreload: jokesToPreload,
        showSaveButton: showSaveButton,
        showShareButton: showShareButton,
        showAdminRatingButtons: showAdminRatingButtons,
        showUserRatingButtons: showUserRatingButtons,
        showUsageStats: showUsageStats,
        title: title,
        jokeContext: jokeContext,
        controller: controller,
        overlayBadgeText: topRightBadgeText,
        showSimilarSearchButton: showSimilarSearchButton,
        mode: mode,
        dataSource: dataSource,
      );
    } else {
      // No images or incomplete images - show text with populate button
      return JokeTextCard(
        joke: joke,
        index: index,
        isAdminMode: isAdminMode,
        overlayBadgeText: topRightBadgeText,
      );
    }
  }
}
