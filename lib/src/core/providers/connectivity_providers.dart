import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'connectivity_providers.g.dart';

/// Exposes a simple online/offline signal.
///
/// We treat anything other than `none` as online. This does not guarantee
/// reachability to app backends but is sufficient to trigger retry attempts
/// when radio connectivity returns.
@Riverpod()
Stream<bool> isOnline(Ref ref) async* {
  final connectivity = Connectivity();
  final initial = await connectivity.checkConnectivity();
  yield initial.any((r) => r != ConnectivityResult.none);

  yield* connectivity.onConnectivityChanged.map(
    (results) => results.any((r) => r != ConnectivityResult.none),
  );
}

@Riverpod()
bool isOnlineNow(Ref ref) {
  final value = ref.watch(isOnlineProvider);
  return value.maybeWhen(data: (v) => v, orElse: () => true);
}
