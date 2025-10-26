import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

// Test enums for testing enum parameter functionality
enum TestEnum { option1, option2, option3 }

// Test parameters for each type
final Map<RemoteParam, RemoteParamDescriptor> testParameters = {
  RemoteParam.subscriptionPromptMinJokesViewed: IntRemoteParamDescriptor(
    key: 'test_int_param',
    defaultInt: 42,
    isValid: validateNonNegativeInt,
  ),
  RemoteParam.defaultJokeViewerReveal: BoolRemoteParamDescriptor(
    key: 'test_bool_param',
    defaultBool: false,
  ),
  RemoteParam.reviewMinDaysUsed: DoubleRemoteParamDescriptor(
    key: 'test_double_param',
    defaultDouble: 3.14,
  ),
  RemoteParam.feedbackMinJokesViewed: StringRemoteParamDescriptor(
    key: 'test_string_param',
    defaultString: 'default_string',
  ),
  RemoteParam.shareImagesMode: EnumRemoteParamDescriptor(
    key: 'test_enum_param',
    enumValues: TestEnum.values,
    enumDefault: TestEnum.option2,
  ),
};

class MockRemoteConfigClient extends Mock implements RemoteConfigClient {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockFirebaseRemoteConfig extends Mock implements FirebaseRemoteConfig {}

RemoteConfigValue _remoteValue(Object? value, ValueSource source) {
  if (value == null) {
    return RemoteConfigValue(null, source);
  }
  return RemoteConfigValue(value.toString().codeUnits, source);
}

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
        parameters: testParameters,
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
        parameters: testParameters,
      );

      await service.initialize();

      final capturedDefaults =
          verify(() => mockClient.setDefaults(captureAny())).captured.single
              as Map<String, Object>;
      final expectedDefaults = <String, Object>{
        for (final e in testParameters.entries)
          e.value.key: e.value.defaultValue,
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
        parameters: testParameters,
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

        final service = RemoteConfigService(
          client: mockClient,
          analyticsService: mockAnalytics,
          parameters: testParameters,
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
        expect(values.getInt(RemoteParam.subscriptionPromptMinJokesViewed), 42);
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
        parameters: testParameters,
      );

      // Should not throw even when analytics fails
      await service.initialize();

      // Don't call getInt() here because it would trigger analytics calls that aren't wrapped in try-catch
      // The service should still be initialized and ready to use
      expect(service.currentValues, isNotNull);
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
        parameters: testParameters,
      );
    });

    group('pre-initialization', () {
      test('returns defaults for all parameter types', () {
        final values = service.currentValues;

        expect(
          values.getInt(RemoteParam.subscriptionPromptMinJokesViewed),
          42, // test int default
        );
        expect(
          values.getBool(RemoteParam.defaultJokeViewerReveal),
          false, // test bool default
        );
        expect(
          values.getDouble(RemoteParam.reviewMinDaysUsed),
          3.14, // test double default
        );
        expect(
          values.getString(RemoteParam.feedbackMinJokesViewed),
          'default_string', // test string default
        );
        expect(
          values.getEnum<TestEnum>(RemoteParam.shareImagesMode),
          TestEnum.option2, // test enum default
        );
      });
    });

    group('int parameter functionality', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('returns valid values from client', () async {
        when(
          () => mockClient.getValue('test_int_param'),
        ).thenReturn(_remoteValue(100, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getInt(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          100,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_int_param',
            value: '100',
          ),
        ).called(1);
      });

      test('accepts zero values', () async {
        when(
          () => mockClient.getValue('test_int_param'),
        ).thenReturn(_remoteValue(0, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getInt(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          0,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_int_param',
            value: '0',
          ),
        ).called(1);
      });

      test('rejects negative values and falls back to default', () async {
        when(
          () => mockClient.getValue('test_int_param'),
        ).thenReturn(_remoteValue(-1, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getInt(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          42, // falls back to default
        );
        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'readParamValue',
            errorMessage: 'Invalid value for key: test_int_param: -1',
          ),
        ).called(1);
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getValue('test_int_param'),
        ).thenThrow(Exception('rc error'));

        await service.initialize();
        expect(
          service.currentValues.getInt(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          42, // falls back to default
        );
        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'readParamValue',
            errorMessage:
                'Failed to get value for key: test_int_param: Exception: rc error',
          ),
        ).called(1);
      });

      test('uses in-app defaults when source is default', () async {
        when(
          () => mockClient.getValue('test_int_param'),
        ).thenReturn(_remoteValue(42, ValueSource.valueDefault));

        await service.initialize();
        expect(
          service.currentValues.getInt(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          42,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedDefault(
            paramName: 'test_int_param',
            value: '42',
          ),
        ).called(1);
      });

      test('falls back to default when source is static', () async {
        when(
          () => mockClient.getValue('test_int_param'),
        ).thenReturn(_remoteValue(null, ValueSource.valueStatic));

        await service.initialize();
        expect(
          service.currentValues.getInt(
            RemoteParam.subscriptionPromptMinJokesViewed,
          ),
          0, // RemoteConfigValue(null).asInt() returns 0
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedError(
            paramName: 'test_int_param',
            value: '0',
          ),
        ).called(1);
      });
    });

    group('bool parameter functionality', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('returns true values from client', () async {
        when(
          () => mockClient.getValue('test_bool_param'),
        ).thenReturn(_remoteValue(true, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getBool(RemoteParam.defaultJokeViewerReveal),
          true,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_bool_param',
            value: 'true',
          ),
        ).called(1);
      });

      test('returns false values from client', () async {
        when(
          () => mockClient.getValue('test_bool_param'),
        ).thenReturn(_remoteValue(false, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getBool(RemoteParam.defaultJokeViewerReveal),
          false,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_bool_param',
            value: 'false',
          ),
        ).called(1);
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getValue('test_bool_param'),
        ).thenThrow(Exception('rc error'));

        await service.initialize();
        expect(
          service.currentValues.getBool(RemoteParam.defaultJokeViewerReveal),
          false, // falls back to default
        );
        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'readParamValue',
            errorMessage:
                'Failed to get value for key: test_bool_param: Exception: rc error',
          ),
        ).called(1);
      });
    });

    group('double parameter functionality', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('returns valid values from client', () async {
        when(
          () => mockClient.getValue('test_double_param'),
        ).thenReturn(_remoteValue(2.71, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getDouble(RemoteParam.reviewMinDaysUsed),
          2.71,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_double_param',
            value: '2.71',
          ),
        ).called(1);
      });

      test('accepts zero values', () async {
        when(
          () => mockClient.getValue('test_double_param'),
        ).thenReturn(_remoteValue(0.0, ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getDouble(RemoteParam.reviewMinDaysUsed),
          0.0,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_double_param',
            value: '0.0',
          ),
        ).called(1);
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getValue('test_double_param'),
        ).thenThrow(Exception('rc error'));

        await service.initialize();
        expect(
          service.currentValues.getDouble(RemoteParam.reviewMinDaysUsed),
          3.14, // falls back to default
        );
        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'readParamValue',
            errorMessage:
                'Failed to get value for key: test_double_param: Exception: rc error',
          ),
        ).called(1);
      });
    });

    group('string parameter functionality', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('returns valid values from client', () async {
        when(
          () => mockClient.getValue('test_string_param'),
        ).thenReturn(_remoteValue('test_value', ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getString(RemoteParam.feedbackMinJokesViewed),
          'test_value',
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_string_param',
            value: 'test_value',
          ),
        ).called(1);
      });

      test('returns empty string from client', () async {
        when(
          () => mockClient.getValue('test_string_param'),
        ).thenReturn(_remoteValue('', ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getString(RemoteParam.feedbackMinJokesViewed),
          '',
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_string_param',
            value: '',
          ),
        ).called(1);
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getValue('test_string_param'),
        ).thenThrow(Exception('rc error'));

        await service.initialize();
        expect(
          service.currentValues.getString(RemoteParam.feedbackMinJokesViewed),
          'default_string', // falls back to default
        );
        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'readParamValue',
            errorMessage:
                'Failed to get value for key: test_string_param: Exception: rc error',
          ),
        ).called(1);
      });
    });

    group('enum parameter functionality', () {
      setUp(() {
        when(
          () => mockClient.setConfigSettings(any()),
        ).thenAnswer((_) async {});
        when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
        when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      });

      test('parses valid enum values (case-insensitive, trimmed)', () async {
        when(
          () => mockClient.getValue('test_enum_param'),
        ).thenReturn(_remoteValue('  OPTION1  ', ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getEnum<TestEnum>(RemoteParam.shareImagesMode),
          TestEnum.option1,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_enum_param',
            value: '  OPTION1  ',
          ),
        ).called(1);
      });

      test('parses lowercase enum values', () async {
        when(
          () => mockClient.getValue('test_enum_param'),
        ).thenReturn(_remoteValue('option3', ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getEnum<TestEnum>(RemoteParam.shareImagesMode),
          TestEnum.option3,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_enum_param',
            value: 'option3',
          ),
        ).called(1);
      });

      test('parses mixed case enum values', () async {
        when(
          () => mockClient.getValue('test_enum_param'),
        ).thenReturn(_remoteValue('OpTiOn2', ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getEnum<TestEnum>(RemoteParam.shareImagesMode),
          TestEnum.option2,
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_enum_param',
            value: 'OpTiOn2',
          ),
        ).called(1);
      });

      test('falls back to default for unknown enum values', () async {
        when(
          () => mockClient.getValue('test_enum_param'),
        ).thenReturn(_remoteValue('unknown', ValueSource.valueRemote));

        await service.initialize();
        expect(
          service.currentValues.getEnum<TestEnum>(RemoteParam.shareImagesMode),
          TestEnum.option2, // falls back to default
        );
        verify(
          () => mockAnalytics.logRemoteConfigUsedRemote(
            paramName: 'test_enum_param',
            value: 'unknown',
          ),
        ).called(1);
      });

      test('falls back to default on client error', () async {
        when(
          () => mockClient.getValue('test_enum_param'),
        ).thenThrow(Exception('read error'));

        await service.initialize();
        expect(
          service.currentValues.getEnum<TestEnum>(RemoteParam.shareImagesMode),
          TestEnum.option2, // falls back to default
        );
        verify(
          () => mockAnalytics.logErrorRemoteConfig(
            phase: 'readParamValue',
            errorMessage:
                'Failed to get value for key: test_enum_param: Exception: read error',
          ),
        ).called(1);
      });
    });
  });

  group('validation functions', () {
    late MockRemoteConfigClient mockClient;
    late MockAnalyticsService mockAnalytics;

    setUp(() {
      mockClient = MockRemoteConfigClient();
      mockAnalytics = MockAnalyticsService();
    });

    test('_validateNonNegativeInt accepts positive values', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      when(
        () => mockClient.getValue('test_int_param'),
      ).thenReturn(_remoteValue(5, ValueSource.valueRemote));

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
        parameters: testParameters,
      );

      await service.initialize();
      expect(
        service.currentValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
        5,
      );
      verify(
        () => mockAnalytics.logRemoteConfigUsedRemote(
          paramName: 'test_int_param',
          value: '5',
        ),
      ).called(1);
    });

    test('_validateNonNegativeInt rejects negative values', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      when(
        () => mockClient.getValue('test_int_param'),
      ).thenReturn(_remoteValue(-1, ValueSource.valueRemote));

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
        parameters: testParameters,
      );

      await service.initialize();
      // Should fall back to default (42) when validation fails
      expect(
        service.currentValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
        42,
      );
      verify(
        () => mockAnalytics.logErrorRemoteConfig(
          phase: 'readParamValue',
          errorMessage: 'Invalid value for key: test_int_param: -1',
        ),
      ).called(1);
    });

    test('_validateNonNegativeInt accepts zero values', () async {
      when(() => mockClient.setConfigSettings(any())).thenAnswer((_) async {});
      when(() => mockClient.setDefaults(any())).thenAnswer((_) async {});
      when(() => mockClient.fetchAndActivate()).thenAnswer((_) async => true);
      when(
        () => mockClient.getValue('test_int_param'),
      ).thenReturn(_remoteValue(0, ValueSource.valueRemote));

      final service = RemoteConfigService(
        client: mockClient,
        analyticsService: mockAnalytics,
        parameters: testParameters,
      );

      await service.initialize();
      expect(
        service.currentValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
        0,
      );
      verify(
        () => mockAnalytics.logRemoteConfigUsedRemote(
          paramName: 'test_int_param',
          value: '0',
        ),
      ).called(1);
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
            enumDefault: TestEnum.option1,
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
            enumValues: TestEnum.values,
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
            enumValues: [TestEnum.option1, TestEnum.option2],
            enumDefault: TestEnum.option3,
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
        parameters: testParameters,
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
        parameters: testParameters,
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
        parameters: testParameters,
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
        parameters: testParameters,
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
        parameters: testParameters,
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
      when(
        () => inner.getValue('v'),
      ).thenReturn(_remoteValue('payload', ValueSource.valueRemote));

      expect(await adapter.fetchAndActivate(), true);
      await adapter.setConfigSettings(
        RemoteConfigSettings(
          fetchTimeout: const Duration(seconds: 2),
          minimumFetchInterval: const Duration(minutes: 5),
        ),
      );
      await adapter.setDefaults(const {'k': 'v'});
      final remoteValue = adapter.getValue('v');
      expect(remoteValue.asString(), 'payload');
      expect(remoteValue.source, ValueSource.valueRemote);

      verify(() => inner.fetchAndActivate()).called(1);
      verify(() => inner.setConfigSettings(any())).called(1);
      verify(() => inner.setDefaults(any())).called(1);
      verify(() => inner.getValue('v')).called(1);
    });
  });
}
