import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

/// Computes whether the global app bar feedback action should be shown
final shouldShowFeedbackActionProvider = FutureProvider<bool>((ref) async {
  // Recompute when app usage changes (e.g., jokes viewed) or other listeners trigger
  ref.watch(appUsageEventsProvider);

  final store = ref.read(feedbackPromptStateStoreProvider);
  final hasViewed = await store.hasViewed();
  if (hasViewed) return false;

  final appUsage = ref.read(appUsageServiceProvider);
  final jokesViewed = await appUsage.getNumJokesViewed();

  final rc = ref.read(remoteConfigValuesProvider);
  final minViewed = rc.getInt(RemoteParam.feedbackMinJokesViewed);

  return jokesViewed >= minViewed;
});
