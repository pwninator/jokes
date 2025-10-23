import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

part 'admob_service.g.dart';

@Riverpod(keepAlive: true)
AdMobService adMobService(Ref ref) {
  return GoogleAdMobService();
}

abstract class AdMobService {
  Future<void> initialize();
}

class GoogleAdMobService implements AdMobService {
  GoogleAdMobService();

  @override
  Future<void> initialize() async {
    try {
      final configuration = RequestConfiguration(
        tagForChildDirectedTreatment: TagForChildDirectedTreatment.yes,
        tagForUnderAgeOfConsent: TagForUnderAgeOfConsent.yes,
        maxAdContentRating: MaxAdContentRating.g,
        testDeviceIds: const <String>[
          'TEST_DEVICE_ID',
          'D3B83E413D3297B99A61183DDB51FC19',
        ],
      );
      await MobileAds.instance.updateRequestConfiguration(configuration);
      await MobileAds.instance.initialize();
      AppLogger.debug(
        'ADMOB: Initialized with Families policy (G-rated, child-directed)',
      );
    } catch (e) {
      AppLogger.fatal('AdMob initialization failed: $e');
    }
  }
}
