import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

part 'app_providers.g.dart';

/// Provider for the kDebugMode boolean
final debugModeProvider = Provider<bool>((ref) => kDebugMode);

/// Provider for PerformanceService (Firebase Performance)
@Riverpod(keepAlive: true)
PerformanceService performanceService(Ref ref) {
  return FirebasePerformanceService();
}
