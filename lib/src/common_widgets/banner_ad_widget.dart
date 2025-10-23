import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/banner_ad_manager.dart';
import 'package:snickerdoodle/src/features/ads/banner_ad_service.dart';

class AdBannerWidget extends ConsumerStatefulWidget {
  const AdBannerWidget({super.key, required this.jokeContext});

  final String jokeContext;

  @override
  ConsumerState<AdBannerWidget> createState() => _AdBannerWidgetState();
}

class _AdBannerWidgetState extends ConsumerState<AdBannerWidget> {
  bool _eligibilityListenerInitialized = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final eligibility = ref.read(bannerAdEligibilityProvider);
      _handleEligibility(eligibility);
    });
  }

  void _handleEligibility(BannerAdEligibility eligibility) {
    final analytics = ref.read(analyticsServiceProvider);
    final skippedReason = eligibility.isEligible ? null : eligibility.reason;
    final shouldShow = eligibility.isEligible;

    analytics.logAdBannerStatus(skipReason: skippedReason);

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
    if (!_eligibilityListenerInitialized) {
      ref.listen<BannerAdEligibility>(bannerAdEligibilityProvider, (
        previous,
        next,
      ) {
        if (previous == next) return;
        _handleEligibility(next);
      });
      _eligibilityListenerInitialized = true;
    }

    final state = ref.watch(bannerAdControllerProvider);
    final ad = state.ad;
    if (!state.shouldShow || !state.isLoaded || ad == null) {
      return const SizedBox.shrink();
    }
    return SafeArea(
      top: true,
      bottom: false,
      child: SizedBox(
        height: ad.size.height.toDouble(),
        width: ad.size.width.toDouble(),
        child: AdWidget(ad: ad),
      ),
    );
  }
}
