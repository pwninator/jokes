import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';

/// Initializes app usage tracking once per app start after SharedPreferences is ready
final appUsageInitializationProvider = FutureProvider<void>((ref) async {
  // Ensure SharedPreferences has been loaded
  await ref.watch(sharedPreferencesProvider.future);

  // Log app usage for this launch
  final appUsageService = ref.read(appUsageServiceProvider);
  await appUsageService.logAppUsage();
});
