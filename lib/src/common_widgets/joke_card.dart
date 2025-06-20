import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeCard extends StatelessWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onTap;
  final bool showTrailingIcon;

  const JokeCard({
    super.key,
    required this.joke,
    this.index,
    this.onTap,
    this.showTrailingIcon = true,
  });

  @override
  Widget build(BuildContext context) {
    // Determine which state to show based on image URLs
    // Check for non-null, non-empty, and non-whitespace URLs
    final hasSetupImage = joke.setupImageUrl != null && 
        joke.setupImageUrl!.trim().isNotEmpty;
    final hasPunchlineImage = joke.punchlineImageUrl != null && 
        joke.punchlineImageUrl!.trim().isNotEmpty;

    if (hasSetupImage && hasPunchlineImage) {
      // Both images available - show carousel
      return JokeImageCarousel(joke: joke, index: index, onTap: onTap);
    } else {
      // No images or incomplete images - show text with populate button
      return JokeTextCard(
        joke: joke,
        index: index,
        onTap: onTap,
        showTrailingIcon: showTrailingIcon,
      );
    }
  }
}
