import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

/// A startup task that can be executed during app initialization.
///
/// Each task has a unique [id] and an [execute] function that performs
/// the initialization work using a [WidgetRef] to access providers.
class StartupTask {
  const StartupTask({
    required this.id,
    required this.execute,
    required this.traceName,
  });

  /// Unique identifier for this task (used for logging and debugging).
  final String id;

  /// The function that performs the initialization work.
  ///
  /// Tasks use [WidgetRef] to access and initialize providers during startup.
  /// Providers initialized here are available to the app via the shared ProviderScope.
  final Future<void> Function(WidgetRef ref) execute;

  /// Required trace name for Firebase Performance monitoring.
  ///
  /// A performance trace will be recorded for this task.
  final TraceName traceName;
}
