import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

class JokeViewerContext {
  JokeViewerContext({
    required this.isPortrait,
    required this.isRevealMode,
    required this.jokeViewerMode,
    required this.brightness,
    required this.screenOrientation,
  });

  final bool isPortrait;
  final bool isRevealMode;
  final JokeViewerMode jokeViewerMode;
  final Brightness brightness;
  final String screenOrientation;
}
