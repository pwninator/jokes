import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';

class _MockCrashlytics extends Mock implements FirebaseCrashlytics {}

void main() {
  setUpAll(() {
    registerFallbackValue(FlutterErrorDetails(exception: Exception('x')));
  });

  group('FirebaseCrashReportingService', () {
    void stubAll(_MockCrashlytics mock) {
      when(() => mock.setCustomKey(any(), any<int>())).thenAnswer((_) async {});
      when(
        () => mock.setCustomKey(any(), any<double>()),
      ).thenAnswer((_) async {});
      when(
        () => mock.setCustomKey(any(), any<bool>()),
      ).thenAnswer((_) async {});
      when(
        () => mock.setCustomKey(any(), any<String>()),
      ).thenAnswer((_) async {});
      when(() => mock.setUserIdentifier(any())).thenAnswer((_) async {});
      when(
        () => mock.recordError(any(), any(), fatal: any(named: 'fatal')),
      ).thenAnswer((_) async {});
      when(() => mock.log(any())).thenAnswer((_) async {});
      when(() => mock.recordFlutterError(any())).thenAnswer((_) async {});
    }

    test(
      'recordNonFatal forwards keys and records error as non-fatal',
      () async {
        final mockCrashlytics = _MockCrashlytics();
        stubAll(mockCrashlytics);
        final service = FirebaseCrashReportingService(
          crashlytics: mockCrashlytics,
        );

        final error = Exception('image failed');
        final stack = StackTrace.current;

        // When
        await service.recordNonFatal(
          error,
          stackTrace: stack,
          keys: {
            'intKey': 1,
            'doubleKey': 1.5,
            'boolKey': true,
            'stringKey': 'value',
            'nullKey': null,
            'objKey': DateTime(2020, 1, 1),
          },
        );

        // Then
        verify(() => mockCrashlytics.setCustomKey('intKey', 1)).called(1);
        verify(() => mockCrashlytics.setCustomKey('doubleKey', 1.5)).called(1);
        verify(() => mockCrashlytics.setCustomKey('boolKey', true)).called(1);
        verify(
          () => mockCrashlytics.setCustomKey('stringKey', 'value'),
        ).called(1);
        // nullKey is skipped (check against all supported overloads)
        verifyNever(() => mockCrashlytics.setCustomKey('nullKey', any<int>()));
        verifyNever(
          () => mockCrashlytics.setCustomKey('nullKey', any<double>()),
        );
        verifyNever(() => mockCrashlytics.setCustomKey('nullKey', any<bool>()));
        verifyNever(
          () => mockCrashlytics.setCustomKey('nullKey', any<String>()),
        );
        // objKey falls back to string
        verify(
          () => mockCrashlytics.setCustomKey('objKey', any<String>()),
        ).called(1);
        verify(
          () => mockCrashlytics.recordError(error, stack, fatal: false),
        ).called(1);
      },
    );

    test(
      'setUser sets/crashes user identifier and clears on null/empty',
      () async {
        final mockCrashlytics = _MockCrashlytics();
        stubAll(mockCrashlytics);
        final service = FirebaseCrashReportingService(
          crashlytics: mockCrashlytics,
        );

        await service.setUser('abc');
        verify(() => mockCrashlytics.setUserIdentifier('abc')).called(1);

        await service.setUser('');
        verify(() => mockCrashlytics.setUserIdentifier('')).called(1);

        await service.setUser(null);
        verify(() => mockCrashlytics.setUserIdentifier('')).called(1);
      },
    );

    test('recordFatal records fatal error', () async {
      final mockCrashlytics = _MockCrashlytics();
      stubAll(mockCrashlytics);
      final service = FirebaseCrashReportingService(
        crashlytics: mockCrashlytics,
      );

      final error = Exception('boom');
      final stack = StackTrace.current;

      await service.recordFatal(error, stack);

      verify(
        () => mockCrashlytics.recordError(error, stack, fatal: true),
      ).called(1);
    });

    test('log forwards to Crashlytics', () async {
      final mockCrashlytics = _MockCrashlytics();
      stubAll(mockCrashlytics);
      final service = FirebaseCrashReportingService(
        crashlytics: mockCrashlytics,
      );

      await service.log('hello');

      verify(() => mockCrashlytics.log('hello')).called(1);
    });
  });
}
