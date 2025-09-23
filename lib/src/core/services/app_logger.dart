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
        ? FirebaseCrashReportingService()
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

  // Instance methods
  void _debug(String message) {
    if (!_isRelease) {
      // Debug prints only in debug/profile
      debugPrint(message);
    }
  }

  void _info(String message) {
    if (!_isRelease) {
      debugPrint(message);
    }
  }

  void _warn(String message) async {
    if (_isRelease) {
      // Lightweight breadcrumb in release
      try {
        await _crashReportingService.log('WARN: $message');
      } catch (_) {}
    } else {
      debugPrint('WARN: $message');
    }
  }
}
