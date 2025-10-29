import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

part 'random_starting_id_provider.g.dart';

@Riverpod(keepAlive: true)
RandomStartingIdService randomStartingIdService(Ref ref) {
  final settings = ref.read(settingsServiceProvider);
  return RandomStartingIdService(settings);
}

@Riverpod(keepAlive: true)
Future<int> randomStartingId(Ref ref) async {
  final service = ref.read(randomStartingIdServiceProvider);
  return await service.getRandomStartingId();
}

class RandomStartingIdService {
  RandomStartingIdService(this._settings);

  final SettingsService _settings;

  static const String _key = 'random_starting_id';

  /// Get the user's random starting ID. If not present, generates a new one
  /// and stores it. The ID will never change after initial generation.
  Future<int> getRandomStartingId() async {
    final existing = _settings.getInt(_key);
    if (existing != null) {
      return existing;
    }

    // Generate a random 32-bit positive integer (0 to 2^31-1)
    // This matches Python's random.randint(0, 2**31 - 1)
    final random = Random();
    final randomId = random.nextInt(1 << 31); // 2^31 = 2147483648

    // Store the generated ID
    await _settings.setInt(_key, randomId);

    return randomId;
  }
}
