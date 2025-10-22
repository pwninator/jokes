import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/banner_ad_manager.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';
import 'package:snickerdoodle/src/utils/joke_viewer_utils.dart';

class AdBannerWidget extends ConsumerStatefulWidget {
  const AdBannerWidget({super.key, required this.jokeContext});

  final String jokeContext;

  @override
  ConsumerState<AdBannerWidget> createState() => _AdBannerWidgetState();
}

class _AdBannerWidgetState extends ConsumerState<AdBannerWidget> {
  void _evaluate() {
    final analytics = ref.read(analyticsServiceProvider);
    final adminSettingsService = ref.read(adminSettingsServiceProvider);
    final rc = ref.read(remoteConfigValuesProvider);
    final mode = rc.getEnum<AdDisplayMode>(RemoteParam.adDisplayMode);
    final ctx = getJokeViewerContext(context, ref);

    String? skippedReason;

    // Check admin override first - if enabled, force banner mode regardless of remote config
    final adminOverride = adminSettingsService.getAdminOverrideShowBannerAd();
    final effectiveMode = adminOverride ? AdDisplayMode.banner : mode;

    if (effectiveMode != AdDisplayMode.banner) {
      skippedReason = 'Not banner mode';
      AppLogger.info('BANNER_AD: Skipped: Not banner mode');
    } else if (!ctx.isPortrait) {
      skippedReason = 'Not portrait mode';
      AppLogger.info('BANNER_AD: Skipped: Not portrait mode');
    } else {
      skippedReason = null;
      AppLogger.info('BANNER_AD: Showing');
    }

    // Decide desired visibility based on gating logic
    final shouldShow = skippedReason == null;

    // Log skip on transition to hidden (avoid duplicate logs when state unchanged)
    if (!shouldShow) {
      final controllerState = ref.read(bannerAdControllerProvider);
      if (controllerState.shouldShow != shouldShow) {
        analytics.logAdBannerStatus(skipReason: skippedReason);
      }
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      // Always delegate; controller guards redundant work
      ref
          .read(bannerAdControllerProvider.notifier)
          .evaluate(shouldShow: shouldShow, jokeContext: widget.jokeContext);
    });
  }

  @override
  Widget build(BuildContext context) {
    _evaluate();
    final state = ref.watch(bannerAdControllerProvider);
    final ad = state.ad;
    if (!state.shouldShow || !state.isLoaded || ad == null) {
      return const SizedBox.shrink();
    }
    return SafeArea(
      top: false,
      bottom: false,
      child: SizedBox(
        height: ad.size.height.toDouble(),
        width: ad.size.width.toDouble(),
        child: AdWidget(ad: ad),
      ),
    );
  }
}
