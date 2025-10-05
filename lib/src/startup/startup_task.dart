import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

/// A startup task that can be executed during app initialization.
///
/// Each task has a unique [id] and an [execute] function that performs
/// the initialization work.
class StartupTask {
  const StartupTask({required this.id, required this.execute, this.traceName});

  /// Unique identifier for this task (used for logging and debugging).
  final String id;

  /// The function that performs the initialization work.
  ///
  /// Tasks can use the [StartupContext] to access the provider container
  /// and register provider overrides that will be used when the app starts.
  final Future<void> Function(StartupContext context) execute;

  /// Optional trace name for Firebase Performance monitoring.
  ///
  /// If provided, a performance trace will be recorded for this task.
  final TraceName? traceName;
}

/// Context provided to startup tasks during execution.
///
/// Allows tasks to access the provider container and register overrides
/// that will be applied when the main app widget is created.
class StartupContext {
  StartupContext(this._container);

  /// Private constructor for recreating context with a new container and
  /// existing overrides. Used when transitioning between startup phases.
  StartupContext._withExistingOverrides(
    this._container,
    List<Override> existingOverrides,
  ) {
    _overrides.addAll(existingOverrides);
  }

  final ProviderContainer _container;
  final List<Override> _overrides = [];

  /// Access the provider container to read providers during startup.
  ProviderContainer get container => _container;

  /// Register a provider override that will be applied to the main app.
  ///
  /// This is typically used to inject initialized values (like SharedPreferences)
  /// into providers that need them.
  void addOverride(Override override) {
    _overrides.add(override);
  }

  /// Returns all registered overrides.
  List<Override> get overrides => List.unmodifiable(_overrides);

  /// Creates a new context with a fresh container that has all accumulated overrides.
  ///
  /// This is used to transition between startup phases, ensuring that later tasks
  /// have access to overrides registered by earlier tasks.
  StartupContext recreateWithOverrides(List<Override> initialOverrides) {
    final newContainer = ProviderContainer(
      overrides: [...initialOverrides, ..._overrides],
    );
    return StartupContext._withExistingOverrides(newContainer, _overrides);
  }
}
