import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';

class _MockRemoteConfigClient extends Mock implements RemoteConfigClient {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  setUpAll(() {
    registerFallbackValue(Exception('fallback'));
    // Fallback for RemoteConfigSettings used with any(named: ...)
    registerFallbackValue(
      RemoteConfigSettings(
        fetchTimeout: const Duration(seconds: 1),
        minimumFetchInterval: const Duration(seconds: 1),
      ),
    );
  });

  group('RemoteConfigService', () {
    test('initialize sets defaults and fetches successfully', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );

      await service.initialize();

      verify(() => client.setConfigSettings(any())).called(1);
      verify(() => client.setDefaults(any())).called(1);
      verify(() => client.fetchAndActivate()).called(1);
      verifyNever(
        () => analytics.logErrorRemoteConfig(
          errorMessage: any(named: 'errorMessage'),
          phase: any(named: 'phase'),
        ),
      );
    });

    test('initialize logs analytics on error', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenThrow(Exception('boom'));
      when(
        () => analytics.logErrorRemoteConfig(
          errorMessage: any(named: 'errorMessage'),
          phase: any(named: 'phase'),
        ),
      ).thenAnswer((_) async {});

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      await service.initialize();

      verify(
        () => analytics.logErrorRemoteConfig(
          errorMessage: any(named: 'errorMessage'),
          phase: 'initialize',
        ),
      ).called(1);
    });

    test(
      'currentValues falls back to default when key missing or invalid',
      () async {
        final client = _MockRemoteConfigClient();
        final analytics = _MockAnalyticsService();

        when(() => client.getInt(any())).thenReturn(0);

        final service = RemoteConfigService(
          client: client,
          analyticsService: analytics,
        );
        final values = service.currentValues;
        expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 5);
      },
    );

    test('getInt accepts zero for non-negative integer params', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => true);

      // Return zero specifically for review_min_saved_jokes
      when(() => client.getInt('review_min_saved_jokes')).thenReturn(0);

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      await service.initialize();

      final values = service.currentValues;
      expect(values.getInt(RemoteParam.reviewMinSavedJokes), 0);
    });

    test('negative values fall back to default for integer params', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => true);

      // Return negative specifically for review_min_saved_jokes
      when(() => client.getInt('review_min_saved_jokes')).thenReturn(-1);

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      await service.initialize();

      final values = service.currentValues;
      // Default for reviewMinSavedJokes is 3
      expect(values.getInt(RemoteParam.reviewMinSavedJokes), 3);
    });
  });
}
