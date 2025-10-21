import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/banner_ad_manager.dart';

class _MockAnalytics extends Mock implements AnalyticsService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('BannerAdController', () {
    late ProviderContainer container;
    late _MockAnalytics mockAnalytics;

    setUp(() {
      mockAnalytics = _MockAnalytics();
      container = ProviderContainer(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalytics),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    test('adUnitId returns test ID in debug mode', () {
      // This test verifies the ad unit ID getter
      final controller = container.read(bannerAdControllerProvider.notifier);
      final adUnitId = controller.adUnitId;

      if (kDebugMode) {
        expect(adUnitId, 'ca-app-pub-3940256099942544/6300978111');
      } else {
        expect(adUnitId, 'ca-app-pub-2479966366450616/4692246057');
      }
    });

    test('initial state is correct', () {
      final state = container.read(bannerAdControllerProvider);

      expect(state.ad, isNull);
      expect(state.isLoaded, false);
      expect(state.shouldShow, false);
    });

    test('evaluate with shouldShow=false does not load ad', () {
      final controller = container.read(bannerAdControllerProvider.notifier);

      controller.evaluate(shouldShow: false, jokeContext: 'test');

      final state = container.read(bannerAdControllerProvider);
      expect(state.ad, isNull);
      expect(state.isLoaded, false);
      expect(state.shouldShow, false);
    });
  });
}

