import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/device_orientation_provider.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';

part 'banner_ad_service.g.dart';

/// Provides the ability to determine whether banner ads should be shown.
@Riverpod(keepAlive: true)
BannerAdService bannerAdService(Ref ref) {
  return BannerAdService(
    remoteConfigValues: ref.watch(remoteConfigValuesProvider),
    adminSettingsService: ref.watch(adminSettingsServiceProvider),
    orientationResolver: () => ref.read(deviceOrientationProvider),
  );
}

@Riverpod(keepAlive: true)
BannerAdEligibility bannerAdEligibility(Ref ref) {
  // Watching orientation ensures eligibility updates reactively when it changes.
  ref.watch(deviceOrientationProvider);
  final service = ref.watch(bannerAdServiceProvider);
  return service.evaluateEligibility();
}

/// Describes the result of the banner ad eligibility evaluation.
class BannerAdEligibility {
  const BannerAdEligibility({required this.isEligible, required this.reason});

  /// True when the banner ad should be displayed.
  final bool isEligible;

  /// Human readable reason describing the eligibility decision.
  final String reason;
}

class BannerAdService {
  const BannerAdService({
    required RemoteConfigValues remoteConfigValues,
    required AdminSettingsService adminSettingsService,
    required Orientation Function() orientationResolver,
  }) : _remoteConfigValues = remoteConfigValues,
       _adminSettingsService = adminSettingsService,
       _orientationResolver = orientationResolver;

  static const String eligibleReason = 'Eligible';
  static const String notBannerModeReason = 'Not banner mode';
  static const String notPortraitReason = 'Not portrait mode';

  final RemoteConfigValues _remoteConfigValues;
  final AdminSettingsService _adminSettingsService;
  final Orientation Function() _orientationResolver;

  BannerAdEligibility evaluateEligibility() {
    final adminOverride = _adminSettingsService.getAdminOverrideShowBannerAd();
    final configuredMode = _remoteConfigValues.getEnum<AdDisplayMode>(
      RemoteParam.adDisplayMode,
    );
    final effectiveMode = adminOverride ? AdDisplayMode.banner : configuredMode;

    if (effectiveMode != AdDisplayMode.banner) {
      AppLogger.info('BANNER_AD: Skipped: $notBannerModeReason');
      return const BannerAdEligibility(
        isEligible: false,
        reason: notBannerModeReason,
      );
    }

    final orientation = _orientationResolver();
    if (orientation != Orientation.portrait) {
      AppLogger.info('BANNER_AD: Skipped: $notPortraitReason');
      return const BannerAdEligibility(
        isEligible: false,
        reason: notPortraitReason,
      );
    }

    AppLogger.info('BANNER_AD: Showing');
    return const BannerAdEligibility(isEligible: true, reason: eligibleReason);
  }
}
