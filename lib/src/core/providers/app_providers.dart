import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

/// Provider for the kDebugMode boolean
final debugModeProvider = Provider<bool>((ref) => kDebugMode);

/// Provider for PerformanceService (Firebase Performance)
final performanceServiceProvider = Provider<PerformanceService>((ref) {
  return FirebasePerformanceService();
});
