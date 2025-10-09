import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';

class _CrashSpy implements CrashReportingService {
  final List<String> logs = [];
  final List<Object> nonFatals = [];

  @override
  Future<void> initialize() async {}

  @override
  Future<void> setUser(String? userId) async {}

  @override
  Future<void> recordFlutterError(FlutterErrorDetails details) async {}

  @override
  Future<void> recordFatal(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?>? keys,
  }) async {}

  @override
  Future<void> recordNonFatal(
    Object error, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) async {
    nonFatals.add(error);
  }

  @override
  Future<void> log(String message) async {
    logs.add(message);
  }

  @override
  Future<void> setKeys(Map<String, Object?> keys) async {}
}

void main() {
  test(
    'AppLogger warn forwards to crash service in forced release mode',
    () async {
      final spy = _CrashSpy();
      final logger = AppLogger.createForTesting(
        crashReportingService: spy,
        forceReleaseMode: true,
      );
      AppLogger.setInstanceForTesting(logger);

      AppLogger.warn('something happened');
      await Future<void>.delayed(Duration.zero);
      expect(spy.logs.any((m) => m.contains('something happened')), isTrue);
    },
  );
}
