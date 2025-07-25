import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';

/// Provider for platform sharing service
final platformShareServiceProvider = Provider<PlatformShareService>((ref) {
  return PlatformShareServiceImpl();
});

/// Provider for the joke sharing service
final jokeShareServiceProvider = Provider<JokeShareService>((ref) {
  final imageService = ref.watch(imageServiceProvider);
  final analyticsService = ref.watch(analyticsServiceProvider);
  final reactionsService = ref.watch(jokeReactionsServiceProvider);
  final platformShareService = ref.watch(platformShareServiceProvider);

  return JokeShareServiceImpl(
    imageService: imageService,
    analyticsService: analyticsService,
    reactionsService: reactionsService,
    platformShareService: platformShareService,
  );
});
