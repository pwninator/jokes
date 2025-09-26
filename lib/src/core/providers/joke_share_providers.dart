import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/providers/remote_config_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
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
  final appUsageService = ref.watch(appUsageServiceProvider);
  final reviewCoordinator = ref.watch(reviewPromptCoordinatorProvider);
  final performanceService = ref.watch(performanceServiceProvider);
  final remoteConfig = ref.watch(remoteConfigProvider);

  return JokeShareServiceImpl(
    imageService: imageService,
    analyticsService: analyticsService,
    reactionsService: reactionsService,
    platformShareService: platformShareService,
    appUsageService: appUsageService,
    reviewPromptCoordinator: reviewCoordinator,
    performanceService: performanceService,
    remoteConfig: remoteConfig,
  );
});
