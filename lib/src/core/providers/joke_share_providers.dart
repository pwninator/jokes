import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';

/// Provider for the joke sharing service
final jokeShareServiceProvider = Provider<JokeShareService>((ref) {
  final imageService = ref.watch(imageServiceProvider);
  final jokeReactionsService = ref.watch(jokeReactionsServiceProvider);

  return JokeShareServiceImpl(
    imageService: imageService,
    jokeReactionsService: jokeReactionsService,
  );
});
