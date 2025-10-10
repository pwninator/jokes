// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'connectivity_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$isOnlineHash() => r'79a537daa267edbe67143c690ab98135431c7151';

/// Exposes a simple online/offline signal.
///
/// We treat anything other than `none` as online. This does not guarantee
/// reachability to app backends but is sufficient to trigger retry attempts
/// when radio connectivity returns.
///
/// Copied from [isOnline].
@ProviderFor(isOnline)
final isOnlineProvider = StreamProvider<bool>.internal(
  isOnline,
  name: r'isOnlineProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$isOnlineHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef IsOnlineRef = StreamProviderRef<bool>;
String _$isOnlineNowHash() => r'6b4259b715699f6869c1e1a52a248fbe184ad6a1';

/// Checks if the device is currently online.
///
/// Copied from [isOnlineNow].
@ProviderFor(isOnlineNow)
final isOnlineNowProvider = AutoDisposeProvider<bool>.internal(
  isOnlineNow,
  name: r'isOnlineNowProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$isOnlineNowHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef IsOnlineNowRef = AutoDisposeProviderRef<bool>;
String _$offlineToOnlineHash() => r'6b263521b981c2116e309c02f0784ef1bda8b702';

/// Emits an incrementing counter each time connectivity transitions from
/// offline to online. Downstream clients can listen to this provider to react
/// to connectivity restoration.
///
/// Copied from [offlineToOnline].
@ProviderFor(offlineToOnline)
final offlineToOnlineProvider = StreamProvider<int>.internal(
  offlineToOnline,
  name: r'offlineToOnlineProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$offlineToOnlineHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef OfflineToOnlineRef = StreamProviderRef<int>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
