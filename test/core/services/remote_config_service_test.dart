import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

class MockRemoteConfigClient extends Mock implements RemoteConfigClient {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockFirebaseRemoteConfig extends Mock implements FirebaseRemoteConfig {}

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
    late MockRemoteConfigClient mockClient;
    late MockAnalyticsService mockAnalytics;

    setUp(() {
      mockClient = MockRemoteConfigClient();
      mockAnalytics = MockAnalyticsService();
    });

    test('configures settings with correct timeouts', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();

      final settings =
          verify(
                () => mockClient.setConfigSettings(captureAny()),
              ).captured.single
              as RemoteConfigSettings;
      expect(settings.fetchTimeout, const Duration(seconds: 10));
      expect(settings.minimumFetchInterval, const Duration(minutes: 1));
    });

    test('sets all parameter defaults correctly', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();

      final capturedDefaults =
          verify(() => mockClient.setDefaults(captureAny())).captured.single
              as Map<String, Object>;
      final expectedDefaults = <String, Object>{
        for (final e in remoteParams.entries) e.value.key: e.value.defaultValue,
      };
      expect(capturedDefaults, expectedDefaults);
    });

    test('fetches and activates remote config', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();

      verify(() => mockClient.fetchAndActivate()).called(1);
      verifyNever(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      );
    });

    test(
      'logs analytics error and continues when initialization fails',
      () async {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenThrow(Exception('boom'));
        when(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: any(named: 'phase'),
            errorMessage: any(named: 'errorMessage'),
          ),
        ).thenAnswer((_) async {});
        when(() => mockClient.getInt(any())).thenThrow(Exception('no value'));

        final service = RemoteConfigService(
          client: mockClient,
          analyticsService: mockAnalytics,
        );

        await service.initialize();

        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'initialize',
            errorMessage: any(named: 'errorMessage'),
          ),
        ).called(1);

        // Should still work with defaults after error
        final values = service.currentValues;
        expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 5);
      },
    );

    test('continues when analytics logging fails', () async {
      when(
        () => mockClient.setConfigSettings(any()),
      ).thenThrow(Exception('boom'));
      when(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenThrow(Exception('analytics error'));

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      // Should not throw even when analytics fails
      await service.initialize();

      final values = service.currentValues;
      expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 5);
    });
  });

  group('RemoteConfigService.typed readers', () {
    late MockRemoteConfigClient mockClient;
    late MockAnalyticsService mockAnalytics;
    late RemoteConfigService service;

    setUp(() {
      mockClient = MockRemoteConfigClient();
      mockAnalytics = MockAnalyticsService();
      service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );
    });

    group('pre-initialization', () {
      test('returns defaults for all parameter types', () {
        final values = service.currentValues;

        expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 5);
        expect(values.getBool(RemoteParam.defaultJokeViewerReveal), false);
        expect(
          values.getEnum<ShareImagesMode>(RemoteParam.shareImagesMode),
          ShareImagesMode.auto,
        );
      });
    });

    group('int parameters', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('returns valid values from client', () async {
        when(() => mockClient.getInt('review_min_saved_jokes')).thenReturn(7);

        await service.initialize();
        expect(
          service.currentValues.getInt(RemoteParam.reviewMinSavedJokes),
          7,
        );
      });

      test('accepts zero values', () async {
        when(() => mockClient.getInt('review_min_saved_jokes')).thenReturn(0);

        await service.initialize();
        expect(
          service.currentValues.getInt(RemoteParam.reviewMinSavedJokes),
          0,
        );
      });

      test('rejects negative values and falls back to default', () async {
        when(() => mockClient.getInt('review_min_saved_jokes')).thenReturn(-1);

        await service.initialize();
        expect(
          service.currentValues.getInt(RemoteParam.reviewMinSavedJokes),
          3,
        );
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getInt('review_min_viewed_jokes'),
        ).thenThrow(Exception('rc error'));

        await service.initialize();
        expect(
          service.currentValues.getInt(RemoteParam.reviewMinViewedJokes),
          30,
        );
      });
    });

    group('bool parameters', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('returns true values from client', () async {
        when(
          () => mockClient.getBool('default_joke_viewer_reveal'),
        ).thenReturn(true);

        await service.initialize();
        expect(
          service.currentValues.getBool(RemoteParam.defaultJokeViewerReveal),
          true,
        );
      });

      test('returns false values from client', () async {
        when(
          () => mockClient.getBool('default_joke_viewer_reveal'),
        ).thenReturn(false);

        await service.initialize();
        expect(
          service.currentValues.getBool(RemoteParam.defaultJokeViewerReveal),
          false,
        );
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getBool('default_joke_viewer_reveal'),
        ).thenThrow(Exception('rc error'));

        await service.initialize();
        expect(
          service.currentValues.getBool(RemoteParam.defaultJokeViewerReveal),
          false,
        );
      });
    });

    group('enum parameters', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('parses valid enum values (case-insensitive, trimmed)', () async {
        when(
          () => mockClient.getString('share_images_mode'),
        ).thenReturn('  STACKED  ');

        await service.initialize();
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.stacked,
        );
      });

      test('parses lowercase enum values', () async {
        when(
          () => mockClient.getString('share_images_mode'),
        ).thenReturn('separate');

        await service.initialize();
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.separate,
        );
      });

      test('falls back to default for unknown enum values', () async {
        when(
          () => mockClient.getString('share_images_mode'),
        ).thenReturn('unknown');

        await service.initialize();
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.auto,
        );
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getString('share_images_mode'),
        ).thenThrow(Exception('read error'));

        await service.initialize();
        expect(
          service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
          ShareImagesMode.auto,
        );
      });

      test('throws error for non-enum parameters', () async {
        await service.initialize();

        expect(
          () => service.currentValues.getEnum<ShareImagesMode>(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          throwsA(isA<TypeError>()),
        );
      });
    });
  });

  group('validateRemoteParams', () {
    test('accepts the production descriptors', () {
      expect(() => validateRemoteParams(remoteParams), returnsNormally);
    });

    test('rejects empty keys', () {
      final bad = <RemoteParam, RemoteParamDescriptor>{
        RemoteParam.subscriptionPromptMinJokesViewed:
            const RemoteParamDescriptor(
              key: '',
              type: RemoteParamType.intType,
              defaultInt: 1,
            ),
      };
      expect(() => validateRemoteParams(bad), throwsA(isA<StateError>()));
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

    test('rejects missing defaults for int parameters', () {
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
    });

    test('rejects missing defaults for bool parameters', () {
      expect(
        () => validateRemoteParams({
          RemoteParam.defaultJokeViewerReveal: const RemoteParamDescriptor(
            key: 'k2',
            type: RemoteParamType.boolType,
          ),
        }),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects missing defaults for double parameters', () {
      expect(
        () => validateRemoteParams({
          RemoteParam.reviewMinDaysUsed: const RemoteParamDescriptor(
            key: 'k3',
            type: RemoteParamType.doubleType,
          ),
        }),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects missing defaults for string parameters', () {
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

    test('rejects enum parameters missing enumValues', () {
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
    });

    test('rejects enum parameters missing enumDefault', () {
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
    });

    test('rejects enum parameters with default not in enumValues', () {
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
    late MockRemoteConfigClient mockClient;
    late MockAnalyticsService mockAnalytics;

    setUp(() {
      mockClient = MockRemoteConfigClient();
      mockAnalytics = MockAnalyticsService();
    });

    test('calls initialize if not yet initialized', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      final result = await service.refresh();

      expect(result, true);
      verify(() => mockClient.setConfigSettings(any())).called(1);
      verify(() => mockClient.setDefaults(any())).called(1);
      verify(() => mockClient.fetchAndActivate()).called(1);
    });

    test('returns true when new values are activated', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();
      final result = await service.refresh();

      expect(result, true);
      verify(() => mockClient.fetchAndActivate()).called(2);
      verifyNever(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      );
    });

    test('returns false when values are throttled/cached', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => false);

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();
      final result = await service.refresh();

      expect(result, false);
      verify(() => mockClient.fetchAndActivate()).called(2);
      verifyNever(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      );
    });

    test('logs error and returns false when refresh fails', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});

      var callCount = 0;
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async {
        callCount++;
        if (callCount == 1) {
          return true; // succeed on init
        } else {
          throw Exception('network error'); // fail on refresh
        }
      });

      when(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();
      final result = await service.refresh();

      expect(result, false);
      verify(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: 'refresh',
          errorMessage: any(named: 'errorMessage'),
        ),
      ).called(1);
    });

    test('returns false and continues when analytics logging fails', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});

      var callCount = 0;
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async {
        callCount++;
        if (callCount == 1) {
          return true;
        } else {
          throw Exception('network error');
        }
      });

      when(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: any(named: 'phase'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenThrow(Exception('analytics error'));

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
      );

      await service.initialize();

      final result = await service.refresh();
      expect(result, false);
    });
  });

  group('FirebaseRemoteConfigClient (adapter)', () {
    test('delegates to underlying FirebaseRemoteConfig', () async {
      final inner = MockFirebaseRemoteConfig();
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
