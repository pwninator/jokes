import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final deviceOrientationProvider = StateProvider<Orientation>(
  (_) => Orientation.portrait,
);

/// Keeps `deviceOrientationProvider` in sync with the current `MediaQuery`
/// orientation for the subtree.
class DeviceOrientationObserver extends ConsumerStatefulWidget {
  const DeviceOrientationObserver({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<DeviceOrientationObserver> createState() =>
      _DeviceOrientationObserverState();
}

class _DeviceOrientationObserverState
    extends ConsumerState<DeviceOrientationObserver> {
  Orientation? _lastOrientation;

  void _syncOrientation(Orientation orientation) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final controller = ref.read(deviceOrientationProvider.notifier);
      if (controller.state != orientation) {
        controller.state = orientation;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final orientation = MediaQuery.of(context).orientation;
    if (_lastOrientation != orientation) {
      _lastOrientation = orientation;
      _syncOrientation(orientation);
    }

    return widget.child;
  }
}
