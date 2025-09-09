import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';

final crashReportingServiceProvider = Provider<CrashReportingService>((ref) {
  if (kReleaseMode) {
    return FirebaseCrashReportingService();
  }
  return NoopCrashReportingService();
});
