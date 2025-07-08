import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';

/// Provider for the joke sharing service
final jokeShareServiceProvider = Provider<JokeShareService>((ref) {
  final analyticsService = ref.watch(analyticsServiceProvider);
  final imageService = ref.watch(imageServiceProvider);
  
  return JokeShareServiceImpl(
    analyticsService: analyticsService,
    imageService: imageService,
  );
}); 