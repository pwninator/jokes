import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';

/// Thin, release-safe logger with simple levels.
/// - Debug/info: printed only in debug mode.
/// - Warn: breadcrumb in release, printed in debug.
/// - Error: non-fatal in release, printed in debug.
class AppLogger {
  static AppLogger? _instance;

  final CrashReportingService _crashReportingService;
  final bool _forceReleaseModeForTests;

  AppLogger._(
    this._crashReportingService, {
    bool forceReleaseModeForTests = false,
  }) : _forceReleaseModeForTests = forceReleaseModeForTests;

  /// Default instance uses Crashlytics in release and NOOP in debug.
  static AppLogger get instance {
    final existing = _instance;
    if (existing != null) return existing;
    final crashService = kReleaseMode
        ? FirebaseCrashReportingService(
            crashlytics: FirebaseCrashlytics.instance,
          )
        : NoopCrashReportingService();
    final created = AppLogger._(crashService);
    _instance = created;
    return created;
  }

  /// Override the singleton for tests.
  static void setInstanceForTesting(AppLogger logger) {
    _instance = logger;
  }

  /// Factory for tests to create a logger with a custom crash service and
  /// an option to force release-like behavior.
  static AppLogger createForTesting({
    required CrashReportingService crashReportingService,
    bool forceReleaseMode = false,
  }) {
    return AppLogger._(
      crashReportingService,
      forceReleaseModeForTests: forceReleaseMode,
    );
  }

  bool get _isRelease => _forceReleaseModeForTests ? true : kReleaseMode;

  // Static helpers
  static void debug(String message) => instance._debug(message);
  static void info(String message) => instance._info(message);
  static void warn(String message) => instance._warn(message);
  static void error(
    String message, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) => instance._error(message, stackTrace: stackTrace, keys: keys);
  static void fatal(
    String message, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) => instance._fatal(message, stackTrace: stackTrace, keys: keys);

  // Instance methods
  void _debug(String message) {
    _maybeDebugPrint(message);
  }

  void _info(String message) {
    _maybeDebugPrint(message);
  }

  void _warn(String message) async {
    _maybeDebugPrint('WARN: $message');

    try {
      await _crashReportingService.log('WARN: $message');
    } catch (_) {}
  }

  void _error(
    String message, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) async {
    _maybeDebugPrint('ERROR: $message');

    try {
      await _crashReportingService.recordNonFatal(
        'ERROR: $message',
        stackTrace: stackTrace ?? StackTrace.current,
        keys: keys,
      );
    } catch (_) {}
  }

  void _fatal(
    String message, {
    StackTrace? stackTrace,
    Map<String, Object?>? keys,
  }) async {
    _maybeDebugPrint('FATAL: $message');

    try {
      await _crashReportingService.recordFatal(
        'FATAL: $message',
        stackTrace ?? StackTrace.current,
        keys: keys,
      );
    } catch (_) {}
  }

  void _maybeDebugPrint(String message) {
    if (!_isRelease) {
      debugPrint(message);
    }
  }
}
