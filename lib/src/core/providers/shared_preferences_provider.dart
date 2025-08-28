import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Provider for SharedPreferences that initializes the instance lazily
/// This approach avoids the need to create SharedPreferences in main.dart
final sharedPreferencesProvider = FutureProvider<SharedPreferences>((
  ref,
) async {
  return await SharedPreferences.getInstance();
});

/// Provider for when you need synchronous access to SharedPreferences
/// Use this after ensuring the sharedPreferencesProvider has loaded
final sharedPreferencesInstanceProvider = Provider<SharedPreferences>((ref) {
  final asyncValue = ref.watch(sharedPreferencesProvider);
  return asyncValue.when(
    data: (prefs) => prefs,
    loading: () => throw StateError('SharedPreferences not yet loaded'),
    error: (error, stack) =>
        throw StateError('Failed to load SharedPreferences: $error'),
  );
});
