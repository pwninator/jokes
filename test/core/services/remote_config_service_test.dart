import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

class _MockRemoteConfigClient extends Mock implements RemoteConfigClient {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockFirebaseRemoteConfig extends Mock implements FirebaseRemoteConfig {}

void main() {
  setUpAll(() {
    // Fallback for RemoteConfigSettings used with any()
    registerFallbackValue(
      RemoteConfigSettings(
        fetchTimeout: const Duration(seconds: 1),
        minimumFetchInterval: const Duration(seconds: 1),
      ),
    );
  });

  group('RemoteConfigService.initialize', () {
    test(
      'configures settings, sets defaults, fetches; no analytics on success',
      () async {
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

        // Verify settings configured with expected durations
        final settings =
            verify(() => client.setConfigSettings(captureAny())).captured.single
                as RemoteConfigSettings;
        expect(settings.fetchTimeout, const Duration(seconds: 10));
        // Tests run in debug mode; minimumFetchInterval should be 1 minute
        expect(settings.minimumFetchInterval, const Duration(minutes: 1));

        // Verify defaults contain all keys with correct default values
        final capturedDefaults =
            verify(() => client.setDefaults(captureAny())).captured.single
                as Map<String, Object>;
        final expectedDefaults = <String, Object>{
          for (final e in remoteParams.entries)
            e.value.key: e.value.defaultValue,
        };
        expect(capturedDefaults, expectedDefaults);

        verify(() => client.fetchAndActivate()).called(1);
        verifyNever(
          () => analytics.logErrorRemoteConfig(
            phase: any(named: 'phase'),
            errorMessage: any(named: 'errorMessage'),
          ),
        );
      },
    );

    test('logs analytics and still initializes when an error occurs', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenThrow(Exception('boom'));
      when(
        () => analytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
      // After initialize, reading should not crash and should fall back to defaults on client errors
      when(() => client.getInt(any())).thenThrow(Exception('no value'));

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      await service.initialize();

      verify(
        () => analytics.logErrorRemoteConfig(
          phase: 'initialize',
          errorMessage: any(named: 'errorMessage'),
        ),
      ).called(1);

      final values = service.currentValues;
      expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 5);
    });
  });

  group('RemoteConfigService.typed readers', () {
    test('pre-initialize values return defaults (int/bool/enum)', () {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();
      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      final values = service.currentValues;

      expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 5);
      expect(values.getBool(RemoteParam.defaultJokeViewerReveal), false);
      expect(
        values.getEnum<ShareImagesMode>(RemoteParam.shareImagesMode),
        ShareImagesMode.auto,
      );
    });

    test('int: accepts zero, rejects negative (falls back)', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();
      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => true);

      when(() => client.getInt('review_min_saved_jokes')).thenReturn(0);

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      await service.initialize();
      expect(service.currentValues.getInt(RemoteParam.reviewMinSavedJokes), 0);

      // Now negative -> fallback to default (3)
      when(() => client.getInt('review_min_saved_jokes')).thenReturn(-1);
      expect(service.currentValues.getInt(RemoteParam.reviewMinSavedJokes), 3);
    });

    test('int: client error falls back to default', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();
      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => true);
      when(() => client.getInt(any())).thenThrow(Exception('rc error'));

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );
      await service.initialize();
      expect(
        service.currentValues.getInt(RemoteParam.reviewMinViewedJokes),
        30,
      );
    });

    test(
      'enum: valid value (case-insensitive, trimmed) is parsed; invalid falls back',
      () async {
        final client = _MockRemoteConfigClient();
        final analytics = _MockAnalyticsService();
        when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
        when(() => client.setDefaults(any())).thenAnswer((_) async {});
        when(() => client.fetchAndActivate()).thenAnswer((_) async => true);

        when(
          () => client.getString('share_images_mode'),
        ).thenReturn('  STACKED  ');

        final service = RemoteConfigService(
          client: client,
          analyticsService: analytics,
        );
        await service.initialize();
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.stacked,
        );

        // Unknown -> default (auto)
        when(() => client.getString('share_images_mode')).thenReturn('unknown');
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.auto,
        );

        // Error -> default (auto)
        when(
          () => client.getString('share_images_mode'),
        ).thenThrow(Exception('read error'));
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.auto,
        );
      },
    );
  });

  group('validateRemoteParams', () {
    test('accepts the production descriptors', () {
      expect(() => validateRemoteParams(remoteParams), returnsNormally);
    });

    test('rejects duplicate keys', () {
      final bad = <RemoteParam, RemoteParamDescriptor>{
        RemoteParam.subscriptionPromptMinJokesViewed:
            const RemoteParamDescriptor(
              key: 'dup',
              type: RemoteParamType.intType,
              defaultInt: 1,
            ),
        RemoteParam.feedbackMinJokesViewed: const RemoteParamDescriptor(
          key: 'dup',
          type: RemoteParamType.intType,
          defaultInt: 2,
        ),
      };
      expect(() => validateRemoteParams(bad), throwsA(isA<StateError>()));
    });

    test('rejects missing defaults for int/bool/double/string', () {
      expect(
        () => validateRemoteParams({
          RemoteParam.subscriptionPromptMinJokesViewed:
              const RemoteParamDescriptor(
                key: 'k1',
                type: RemoteParamType.intType,
              ),
        }),
        throwsA(isA<StateError>()),
      );

      expect(
        () => validateRemoteParams({
          RemoteParam.defaultJokeViewerReveal: const RemoteParamDescriptor(
            key: 'k2',
            type: RemoteParamType.boolType,
          ),
        }),
        throwsA(isA<StateError>()),
      );

      // double
      expect(
        () => validateRemoteParams({
          RemoteParam.reviewMinDaysUsed: const RemoteParamDescriptor(
            key: 'k3',
            type: RemoteParamType.doubleType,
          ),
        }),
        throwsA(isA<StateError>()),
      );

      // string
      expect(
        () => validateRemoteParams({
          RemoteParam.reviewMinSharedJokes: const RemoteParamDescriptor(
            key: 'k4',
            type: RemoteParamType.stringType,
          ),
        }),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects bad enum configurations', () {
      // missing enumValues
      expect(
        () => validateRemoteParams({
          RemoteParam.shareImagesMode: const RemoteParamDescriptor(
            key: 'e1',
            type: RemoteParamType.enumType,
            enumDefault: ShareImagesMode.auto,
          ),
        }),
        throwsA(isA<StateError>()),
      );

      // missing enumDefault
      expect(
        () => validateRemoteParams({
          RemoteParam.shareImagesMode: RemoteParamDescriptor(
            key: 'e2',
            type: RemoteParamType.enumType,
            enumValues: ShareImagesMode.values,
          ),
        }),
        throwsA(isA<StateError>()),
      );

      // default not in enumValues
      expect(
        () => validateRemoteParams({
          RemoteParam.shareImagesMode: const RemoteParamDescriptor(
            key: 'e3',
            type: RemoteParamType.enumType,
            enumValues: [ShareImagesMode.separate, ShareImagesMode.stacked],
            enumDefault: ShareImagesMode.auto,
          ),
        }),
        throwsA(isA<StateError>()),
      );
    });

    test('accepts well-formed double and string descriptors', () {
      expect(
        () => validateRemoteParams({
          // Re-use enum keys as map keys; keys need only be unique within the map
          RemoteParam.reviewMinDaysUsed: const RemoteParamDescriptor(
            key: 'double_key',
            type: RemoteParamType.doubleType,
            defaultDouble: 1.5,
          ),
          RemoteParam.reviewMinSharedJokes: const RemoteParamDescriptor(
            key: 'string_key',
            type: RemoteParamType.stringType,
            defaultString: 'abc',
          ),
        }),
        returnsNormally,
      );
    });
  });

  group('RemoteConfigService.refresh', () {
    test('calls initialize if not yet initialized', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );

      // Call refresh before initialize
      final result = await service.refresh();

      expect(result, true);
      verify(() => client.setConfigSettings(any())).called(1);
      verify(() => client.setDefaults(any())).called(1);
      verify(() => client.fetchAndActivate()).called(1);
    });

    test('returns true when new values are activated', () async {
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
      final result = await service.refresh();

      expect(result, true);
      verify(
        () => client.fetchAndActivate(),
      ).called(2); // Once for init, once for refresh
      verifyNever(
        () => analytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      );
    });

    test('returns false when values are throttled/cached', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});
      when(() => client.fetchAndActivate()).thenAnswer((_) async => false);

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );

      await service.initialize();
      final result = await service.refresh();

      expect(result, false);
      verify(() => client.fetchAndActivate()).called(2);
      verifyNever(
        () => analytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      );
    });

    test('logs error and returns false when refresh fails', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});

      // First call succeeds (initialize), second call fails (refresh)
      var callCount = 0;
      when(() => client.fetchAndActivate()).thenAnswer((_) async {
        callCount++;
        if (callCount == 1) {
          return true; // succeed on init
        } else {
          throw Exception('network error'); // fail on refresh
        }
      });

      when(
        () => analytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );

      await service.initialize();
      final result = await service.refresh();

      expect(result, false);
      verify(
        () => analytics.logErrorRemoteConfig(
          phase: 'refresh',
          errorMessage: any(named: 'errorMessage'),
        ),
      ).called(1);
    });

    test('returns false and continues when analytics logging fails', () async {
      final client = _MockRemoteConfigClient();
      final analytics = _MockAnalyticsService();

      when(() => client.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => client.setDefaults(any())).thenAnswer((_) async {});

      // First call succeeds (initialize), second call fails (refresh)
      var callCount = 0;
      when(() => client.fetchAndActivate()).thenAnswer((_) async {
        callCount++;
        if (callCount == 1) {
          return true;
        } else {
          throw Exception('network error');
        }
      });

      when(
        () => analytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenThrow(Exception('analytics error'));

      final service = RemoteConfigService(
        client: client,
        analyticsService: analytics,
      );

      await service.initialize();

      // Should not throw even when analytics fails
      final result = await service.refresh();
      expect(result, false);
    });
  });

  group('FirebaseRemoteConfigClient (adapter)', () {
    test('delegates to underlying FirebaseRemoteConfig', () async {
      final inner = _MockFirebaseRemoteConfig();
      final adapter = FirebaseRemoteConfigClient(inner);

      when(() => inner.fetchAndActivate()).thenAnswer((_) async => true);
      when(() => inner.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => inner.setDefaults(any())).thenAnswer((_) async {});
      when(() => inner.getInt('i')).thenReturn(42);
      when(() => inner.getBool('b')).thenReturn(true);
      when(() => inner.getDouble('d')).thenReturn(3.14);
      when(() => inner.getString('s')).thenReturn('x');

      expect(await adapter.fetchAndActivate(), true);
      await adapter.setConfigSettings(
        RemoteConfigSettings(
          fetchTimeout: const Duration(seconds: 2),
          minimumFetchInterval: const Duration(minutes: 5),
        ),
      );
      await adapter.setDefaults(const {'k': 'v'});
      expect(adapter.getInt('i'), 42);
      expect(adapter.getBool('b'), true);
      expect(adapter.getDouble('d'), 3.14);
      expect(adapter.getString('s'), 'x');

      verify(() => inner.fetchAndActivate()).called(1);
      verify(() => inner.setConfigSettings(any())).called(1);
      verify(() => inner.setDefaults(any())).called(1);
      verify(() => inner.getInt('i')).called(1);
      verify(() => inner.getBool('b')).called(1);
      verify(() => inner.getDouble('d')).called(1);
      verify(() => inner.getString('s')).called(1);
    });
  });
}
