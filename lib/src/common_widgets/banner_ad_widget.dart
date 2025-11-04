import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:snickerdoodle/src/core/services/banner_ad_manager.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/ads/banner_ad_service.dart';

class AdBannerWidget extends ConsumerStatefulWidget {
  const AdBannerWidget({
    super.key,
    required this.jokeContext,
    required this.position,
  });

  final String jokeContext;
  final BannerAdPosition position;

  @override
  ConsumerState<AdBannerWidget> createState() => _AdBannerWidgetState();
}

class _AdBannerWidgetState extends ConsumerState<AdBannerWidget> {
  late final ProviderSubscription<BannerAdEligibility> _eligibilitySubscription;

  @override
  void initState() {
    super.initState();
    final initialEligibility = ref.read(bannerAdEligibilityProvider);
    _handleEligibility(initialEligibility);
    _eligibilitySubscription = ref.listenManual<BannerAdEligibility>(
      bannerAdEligibilityProvider,
      (previous, next) {
        if (previous == next) return;
        _handleEligibility(next);
      },
    );
  }

  void _handleEligibility(BannerAdEligibility eligibility) {
    final shouldShow =
        eligibility.isEligible && eligibility.position == widget.position;
    Future.microtask(() {
      if (!mounted) return;
      ref
          .read(bannerAdControllerProvider.notifier)
          .evaluate(
            shouldShow: shouldShow,
            jokeContext: widget.jokeContext,
            position: widget.position,
          );
    });
  }

  @override
  void dispose() {
    _eligibilitySubscription.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final eligibility = ref.watch(bannerAdEligibilityProvider);
    if (!eligibility.isEligible || eligibility.position != widget.position) {
      return const SizedBox.shrink();
    }

    final state = ref.watch(bannerAdControllerProvider);
    final ad = state.ad;
    final height =
        ad?.size.height.toDouble() ?? AdSize.banner.height.toDouble();
    final width = ad?.size.width.toDouble() ?? AdSize.banner.width.toDouble();
    final adWidget = ad != null ? AdWidget(ad: ad) : const SizedBox.shrink();
    final content = SizedBox(height: height, width: width, child: adWidget);

    // Wrap bottom-positioned ads in SafeArea to avoid system UI overlap
    if (widget.position == BannerAdPosition.bottom) {
      return SafeArea(top: false, bottom: true, child: content);
    }

    return content;
  }
}
