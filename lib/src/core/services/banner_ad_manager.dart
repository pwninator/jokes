import 'package:flutter/foundation.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

part 'banner_ad_manager.g.dart';

class BannerAdState {
  const BannerAdState({
    required this.ad,
    required this.isLoaded,
    required this.shouldShow,
  });

  final BannerAd? ad;
  final bool isLoaded;
  final bool shouldShow;

  const BannerAdState.initial()
    : ad = null,
      isLoaded = false,
      shouldShow = false;

  BannerAdState copyWith({BannerAd? ad, bool? isLoaded, bool? shouldShow}) {
    return BannerAdState(
      ad: ad ?? this.ad,
      isLoaded: isLoaded ?? this.isLoaded,
      shouldShow: shouldShow ?? this.shouldShow,
    );
  }
}

@Riverpod(keepAlive: true)
class BannerAdController extends _$BannerAdController {
  BannerAd? _ad;
  bool _isLoaded = false;
  bool _isLoading = false;

  static const Map<BannerAdPosition, String> _prodAdUnitIds = {
    BannerAdPosition.top: 'ca-app-pub-2479966366450616/4306883038',
    BannerAdPosition.bottom: 'ca-app-pub-2479966366450616/7835349916',
  };
  // Google official sample banner ad unit (safe in debug)
  static const String _testAdUnitId = 'ca-app-pub-3940256099942544/6300978111';

  @override
  BannerAdState build() {
    ref.onDispose(() {
      _ad?.dispose();
      _ad = null;
      _isLoaded = false;
      _isLoading = false;
    });
    return const BannerAdState.initial();
  }

  BannerAd? get currentAd => _ad;

  /// Returns the ad unit ID being used for the given position
  String adUnitIdForPosition(BannerAdPosition position) {
    if (kDebugMode) {
      return _testAdUnitId;
    }
    return _prodAdUnitIds[position]!;
  }

  void evaluate({
    required bool shouldShow,
    required String jokeContext,
    required BannerAdPosition position,
  }) {
    AppLogger.info(
      'BANNER_AD: evaluate: shouldShow: $shouldShow, jokeContext: $jokeContext',
    );
    // Guard: avoid redundant work/notifications
    final current = state;
    if (current.shouldShow == shouldShow) {
      if (!shouldShow) {
        return; // already hidden
      }
      if (current.isLoaded) {
        return; // already visible and loaded
      }
      // else: shouldShow && not loaded => continue to load
    }

    // Update visibility only when it actually changes
    if (current.shouldShow != shouldShow) {
      state = current.copyWith(shouldShow: shouldShow);
    }

    if (!shouldShow) {
      // Keep ad instance to persist across screens; do not dispose
      // Just mark not visible
      return;
    }

    if (_ad != null && _isLoaded) {
      // Already loaded and ready
      if (!state.isLoaded) state = state.copyWith(isLoaded: true);
      return;
    }

    if (_isLoading) return;
    _isLoading = true;
    final adUnitId = adUnitIdForPosition(position);

    final analytics = ref.read(analyticsServiceProvider);

    final banner = BannerAd(
      adUnitId: adUnitId,
      size: AdSize.banner,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (ad) {
          _ad = ad as BannerAd;
          _isLoaded = true;
          _isLoading = false;
          state = state.copyWith(ad: _ad, isLoaded: true);
          analytics.logAdBannerLoaded(ad.adUnitId, jokeContext: jokeContext);
        },
        onAdFailedToLoad: (ad, error) {
          ad.dispose();
          _ad = null;
          _isLoaded = false;
          _isLoading = false;
          state = state.copyWith(ad: null, isLoaded: false);
          analytics.logAdBannerFailedToLoad(
            adUnitId,
            errorMessage: error.message,
            errorCode: '${error.code}',
            jokeContext: jokeContext,
          );
        },
        onAdOpened: (ad) {
          analytics.logAdBannerClicked(ad.adUnitId, jokeContext: jokeContext);
        },
      ),
    );

    banner.load();
  }
}
