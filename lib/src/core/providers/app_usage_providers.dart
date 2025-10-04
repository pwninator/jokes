import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';

/// Initializes app usage tracking once per app start.
final appUsageInitializationProvider = FutureProvider<void>((ref) async {
  final appUsageService = ref.read(appUsageServiceProvider);
  await appUsageService.logAppUsage();
});
