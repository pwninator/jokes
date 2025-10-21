import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_context.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

JokeViewerContext getJokeViewerContext(BuildContext context, WidgetRef ref) {
  final orientation = MediaQuery.of(context).orientation;
  final isPortrait = orientation == Orientation.portrait;
  final revealModeEnabled = ref.watch(jokeViewerRevealProvider);
  final brightness = Theme.of(context).brightness;
  final screenOrientation = isPortrait
      ? AnalyticsScreenOrientation.portrait
      : AnalyticsScreenOrientation.landscape;

  final mode = revealModeEnabled
      ? JokeViewerMode.reveal
      : JokeViewerMode.bothAdaptive;

  return JokeViewerContext(
    isPortrait: isPortrait,
    isRevealMode: revealModeEnabled,
    jokeViewerMode: mode,
    brightness: brightness,
    screenOrientation: screenOrientation,
  );
}
