import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/device_orientation_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';

part 'banner_ad_service.g.dart';

/// Provides the ability to determine whether banner ads should be shown.
@Riverpod(keepAlive: true)
BannerAdService bannerAdService(Ref ref) {
  final remoteConfigValues = ref.watch(remoteConfigValuesProvider);
  final adminSettingsService = ref.watch(adminSettingsServiceProvider);
  final analyticsService = ref.watch(analyticsServiceProvider);
  return BannerAdService(
    remoteConfigValues: remoteConfigValues,
    adminSettingsService: adminSettingsService,
    analyticsService: analyticsService,
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
  const BannerAdEligibility({
    required this.isEligible,
    required this.reason,
    required this.position,
  });

  /// True when the banner ad should be displayed.
  final bool isEligible;

  /// Human readable reason describing the eligibility decision.
  final String reason;

  /// Preferred placement for eligible banner ads.
  final BannerAdPosition position;
}

class BannerAdService {
  const BannerAdService({
    required RemoteConfigValues remoteConfigValues,
    required AdminSettingsService adminSettingsService,
    required AnalyticsService analyticsService,
    required Orientation Function() orientationResolver,
  }) : _remoteConfigValues = remoteConfigValues,
       _adminSettingsService = adminSettingsService,
       _analyticsService = analyticsService,
       _orientationResolver = orientationResolver;

  static const String eligibleReason = 'Eligible';
  static const String notBannerModeReason = 'Not banner mode';
  static const String notPortraitReason = 'Not portrait mode';

  final RemoteConfigValues _remoteConfigValues;
  final AdminSettingsService _adminSettingsService;
  final AnalyticsService _analyticsService;
  final Orientation Function() _orientationResolver;

  BannerAdEligibility evaluateEligibility() {
    final adminOverride = _adminSettingsService.getAdminOverrideShowBannerAd();
    final configuredMode = _remoteConfigValues.getEnum<AdDisplayMode>(
      RemoteParam.adDisplayMode,
    );
    final configuredPosition = _remoteConfigValues.getEnum<BannerAdPosition>(
      RemoteParam.bannerAdPosition,
    );
    final effectiveMode = adminOverride ? AdDisplayMode.banner : configuredMode;

    if (effectiveMode != AdDisplayMode.banner) {
      return bannerAdEligibility(
        isEligible: false,
        reason: notBannerModeReason,
        position: configuredPosition,
      );
    }

    final orientation = _orientationResolver();
    if (orientation != Orientation.portrait) {
      return bannerAdEligibility(
        isEligible: false,
        reason: notPortraitReason,
        position: configuredPosition,
      );
    }

    return bannerAdEligibility(
      isEligible: true,
      reason: eligibleReason,
      position: configuredPosition,
    );
  }

  BannerAdEligibility bannerAdEligibility({
    required bool isEligible,
    required String reason,
    required BannerAdPosition position,
  }) {
    _analyticsService.logAdBannerStatus(eligibilityStatus: reason);
    return BannerAdEligibility(
      isEligible: isEligible,
      reason: reason,
      position: position,
    );
  }
}
