import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'connectivity_providers.g.dart';

/// Exposes a simple online/offline signal.
///
/// We treat anything other than `none` as online. This does not guarantee
/// reachability to app backends but is sufficient to trigger retry attempts
/// when radio connectivity returns.
@Riverpod(keepAlive: true)
Stream<bool> isOnline(Ref ref) async* {
  final connectivity = Connectivity();
  final initial = await connectivity.checkConnectivity();
  yield initial.any((r) => r != ConnectivityResult.none);

  yield* connectivity.onConnectivityChanged.map(
    (results) => results.any((r) => r != ConnectivityResult.none),
  );
}

/// Checks if the device is currently online.
@Riverpod()
bool isOnlineNow(Ref ref) {
  final value = ref.read(isOnlineProvider);
  final result = value.maybeWhen(data: (v) => v, orElse: () => true);
  return result;
}

/// Emits an incrementing counter each time connectivity transitions from
/// offline to online. Downstream clients can listen to this provider to react
/// to connectivity restoration.
@Riverpod(keepAlive: true)
Stream<int> offlineToOnline(Ref ref) async* {
  int counter = 0;
  bool? wasOffline;

  // Listen to the same connectivity stream as isOnlineProvider
  final connectivity = Connectivity();
  await for (final results in connectivity.onConnectivityChanged) {
    final isOnline = results.any((r) => r != ConnectivityResult.none);
    final isTransition = wasOffline == true && isOnline == true;
    if (isTransition) {
      counter++;
      yield counter;
    }
    wasOffline = !isOnline;
  }
}
