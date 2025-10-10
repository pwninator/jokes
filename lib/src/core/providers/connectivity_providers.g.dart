// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'connectivity_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$isOnlineHash() => r'1cc2057dc700ee3d82e953131292c05dd3cc9119';

/// Exposes a simple online/offline signal.
///
/// We treat anything other than `none` as online. This does not guarantee
/// reachability to app backends but is sufficient to trigger retry attempts
/// when radio connectivity returns.
///
/// Copied from [isOnline].
@ProviderFor(isOnline)
final isOnlineProvider = AutoDisposeStreamProvider<bool>.internal(
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
typedef IsOnlineRef = AutoDisposeStreamProviderRef<bool>;
String _$isOnlineNowHash() => r'a1a6225ab1469ae80fda8140cabf026c9f709676';

/// See also [isOnlineNow].
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
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
