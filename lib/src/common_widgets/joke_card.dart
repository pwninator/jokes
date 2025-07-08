import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeCard extends StatelessWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onSetupTap;
  final VoidCallback? onPunchlineTap;
  final Function(int)? onImageStateChanged;
  final bool isAdminMode;
  final List<Joke>? jokesToPreload;
  final bool showSaveButton;
  final bool showShareButton;
  final bool showThumbsButtons;
  final String? title;
  final String jokeContext;

  const JokeCard({
    super.key,
    required this.joke,
    this.index,
    this.onSetupTap,
    this.onPunchlineTap,
    this.onImageStateChanged,
    this.isAdminMode = false,
    this.jokesToPreload,
    this.showSaveButton = true,
    this.showShareButton = true,
    this.showThumbsButtons = false,
    this.title,
    required this.jokeContext,
  });

  @override
  Widget build(BuildContext context) {
    // Determine which state to show based on image URLs
    // Check for non-null, non-empty, and non-whitespace URLs
    final hasSetupImage =
        joke.setupImageUrl != null && joke.setupImageUrl!.trim().isNotEmpty;
    final hasPunchlineImage =
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.trim().isNotEmpty;

    if (hasSetupImage && hasPunchlineImage) {
      // Both images available - show carousel
      return JokeImageCarousel(
        joke: joke,
        index: index,
        onSetupTap: onSetupTap,
        onPunchlineTap: onPunchlineTap,
        onImageStateChanged: onImageStateChanged,
        isAdminMode: isAdminMode,
        jokesToPreload: jokesToPreload,
        showSaveButton: showSaveButton,
        showShareButton: showShareButton,
        showThumbsButtons: showThumbsButtons,
        title: title,
        jokeContext: jokeContext,
      );
    } else {
      // No images or incomplete images - show text with populate button
      return JokeTextCard(joke: joke, index: index, onTap: onSetupTap);
    }
  }
}
