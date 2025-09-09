import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';

/// Abstraction for crash reporting so we can mock/disable in tests
abstract class CrashReportingService {
  Future<void> initialize();

  Future<void> recordFlutterError(FlutterErrorDetails details);

  Future<void> recordFatal(Object error, StackTrace stackTrace);

  Future<void> recordNonFatal(
    Object error, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  });

  Future<void> log(String message);

  Future<void> setKeys(Map<String, Object?> keys);
}

class FirebaseCrashReportingService implements CrashReportingService {
  final FirebaseCrashlytics _crashlytics;

  FirebaseCrashReportingService({FirebaseCrashlytics? crashlytics})
    : _crashlytics = crashlytics ?? FirebaseCrashlytics.instance;

  @override
  Future<void> initialize() async {
    // Nothing required here for now; placeholder for future config (e.g., opt-in)
  }

  @override
  Future<void> recordFlutterError(FlutterErrorDetails details) async {
    await _crashlytics.recordFlutterError(details);
    debugPrint('CRASHLYTICS: Flutter error recorded: $details');
  }

  @override
  Future<void> recordFatal(Object error, StackTrace stackTrace) async {
    await _crashlytics.recordError(error, stackTrace, fatal: true);
    debugPrint('CRASHLYTICS: Fatal error recorded: $error');
  }

  @override
  Future<void> recordNonFatal(
    Object error, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) async {
    if (keys != null && keys.isNotEmpty) {
      await setKeys(keys);
    }
    await _crashlytics.recordError(error, stackTrace, fatal: false);
    debugPrint('CRASHLYTICS: Non-fatal error recorded: $error');
  }

  @override
  Future<void> log(String message) async {
    await _crashlytics.log(message);
    debugPrint('CRASHLYTICS: Log recorded: $message');
  }

  @override
  Future<void> setKeys(Map<String, Object?> keys) async {
    for (final entry in keys.entries) {
      final key = entry.key;
      final value = entry.value;
      if (value is int) {
        await _crashlytics.setCustomKey(key, value);
      } else if (value is double) {
        await _crashlytics.setCustomKey(key, value);
      } else if (value is bool) {
        await _crashlytics.setCustomKey(key, value);
      } else if (value is String) {
        await _crashlytics.setCustomKey(key, value);
      } else if (value == null) {
        // Crashlytics does not support null custom keys; skip
      } else {
        // Fallback to string representation for unsupported types
        await _crashlytics.setCustomKey(key, value.toString());
      }
    }
  }
}

/// No-op implementation used for tests or when diagnostics are disabled
class NoopCrashReportingService implements CrashReportingService {
  @override
  Future<void> initialize() async {}

  @override
  Future<void> recordFlutterError(FlutterErrorDetails details) async {
    debugPrint('CRASHLYTICS NO-OP: Flutter error recorded: $details');
  }

  @override
  Future<void> recordFatal(Object error, StackTrace stackTrace) async {
    debugPrint('CRASHLYTICS NO-OP: Fatal error recorded: $error');
  }

  @override
  Future<void> recordNonFatal(
    Object error, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) async {
    debugPrint('CRASHLYTICS NO-OP: Non-fatal error recorded: $error');
  }

  @override
  Future<void> log(String message) async {
    debugPrint('CRASHLYTICS NO-OP: Log recorded: $message');
  }

  @override
  Future<void> setKeys(Map<String, Object?> keys) async {}
}
