import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

/// Abstraction for crash reporting so we can mock/disable in tests
abstract class CrashReportingService {
  Future<void> initialize();

  /// Set or clear the currently authenticated user for crash reports
  Future<void> setUser(String? userId);

  Future<void> recordFlutterError(FlutterErrorDetails details);

  Future<void> recordFatal(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?>? keys,
  });

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

  FirebaseCrashReportingService({required FirebaseCrashlytics crashlytics})
    : _crashlytics = crashlytics;

  @override
  Future<void> initialize() async {
    // Nothing required here for now; placeholder for future config (e.g., opt-in)
  }

  @override
  Future<void> setUser(String? userId) async {
    if (userId == null || userId.isEmpty) {
      await _crashlytics.setUserIdentifier('');
      return;
    }
    await _crashlytics.setUserIdentifier(userId);
  }

  @override
  Future<void> recordFlutterError(FlutterErrorDetails details) async {
    await _crashlytics.recordFlutterError(details);
    AppLogger.debug('CRASHLYTICS: Flutter error recorded: $details');
  }

  @override
  Future<void> recordFatal(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?>? keys,
  }) async {
    if (keys != null && keys.isNotEmpty) {
      await setKeys(keys);
    }
    await _crashlytics.recordError(error, stackTrace, fatal: true);
    AppLogger.debug('CRASHLYTICS: Fatal error recorded: $error');
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
    AppLogger.debug('CRASHLYTICS: Non-fatal error recorded: $error');
  }

  @override
  Future<void> log(String message) async {
    await _crashlytics.log(message);
    AppLogger.debug('CRASHLYTICS: Log recorded: $message');
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
  Future<void> setUser(String? userId) async {}

  @override
  Future<void> recordFlutterError(FlutterErrorDetails details) async {
    AppLogger.debug('CRASHLYTICS NO-OP: Flutter error recorded: $details');
  }

  @override
  Future<void> recordFatal(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?>? keys,
  }) async {
    AppLogger.debug(
      'CRASHLYTICS NO-OP: Fatal error recorded: $error:\n$stackTrace',
    );
  }

  @override
  Future<void> recordNonFatal(
    Object error, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) async {
    AppLogger.debug(
      'CRASHLYTICS NO-OP: Non-fatal error recorded: $error:\n$stackTrace',
    );
  }

  @override
  Future<void> log(String message) async {
    AppLogger.debug('CRASHLYTICS NO-OP: Log recorded: $message');
  }

  @override
  Future<void> setKeys(Map<String, Object?> keys) async {}
}
