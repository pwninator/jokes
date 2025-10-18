import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

/// Reader function type compatible with both WidgetRef.read and
/// ProviderContainer.read. This allows startup tasks to run with either
/// a widget ref (parent scope) or a container (overridden scope).
typedef StartupReader = T Function<T>(ProviderListenable<T> provider);

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
  /// Tasks use [StartupReader] to access providers during startup. Critical
  /// tasks should create concrete instances and return provider overrides.
  /// Tasks that don't provide overrides must return an empty list.
  final Future<List<Override>> Function(StartupReader read) execute;

  /// Required trace name for Firebase Performance monitoring.
  ///
  /// A performance trace will be recorded for this task.
  final TraceName traceName;
}
