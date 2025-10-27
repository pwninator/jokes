import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

part 'feed_screen_status_provider.g.dart';

@Riverpod(keepAlive: true)
bool feedScreenStatus(Ref ref) {
  const String localKey = 'feed_screen_enabled_local';
  final settings = ref.read(settingsServiceProvider);

  final local = settings.getBool(localKey);
  if (local != null) {
    return local;
  }

  // Read remote config default and lock it in locally for this user
  final rv = ref.read(remoteConfigValuesProvider);
  final enabled = rv.getBool(RemoteParam.feedScreenEnabled);
  // Fire and forget set; provider returns synchronously with chosen value
  settings.setBool(localKey, enabled);
  return enabled;
}
