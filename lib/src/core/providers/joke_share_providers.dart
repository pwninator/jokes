import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

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
  final performanceService = ref.watch(performanceServiceProvider);
  final remoteConfigValues = ref.watch(remoteConfigValuesProvider);
  bool getRevealModeEnabled() => ref.read(jokeViewerRevealProvider);

  return JokeShareServiceImpl(
    imageService: imageService,
    analyticsService: analyticsService,
    reactionsService: reactionsService,
    platformShareService: platformShareService,
    appUsageService: appUsageService,
    performanceService: performanceService,
    remoteConfigValues: remoteConfigValues,
    getRevealModeEnabled: getRevealModeEnabled,
  );
});
