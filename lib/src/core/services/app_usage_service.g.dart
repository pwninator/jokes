// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_usage_service.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$appUsageServiceHash() => r'90878c43b3c96bac2ede83a1b53296bb33ba2c48';

/// See also [appUsageService].
@ProviderFor(appUsageService)
final appUsageServiceProvider = Provider<AppUsageService>.internal(
  appUsageService,
  name: r'appUsageServiceProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$appUsageServiceHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef AppUsageServiceRef = ProviderRef<AppUsageService>;
String _$isJokeSavedHash() => r'06fb217de6824b0903131d485d22f080b99dc699';

/// Copied from Dart SDK
class _SystemHash {
  _SystemHash._();

  static int combine(int hash, int value) {
    // ignore: parameter_assignments
    hash = 0x1fffffff & (hash + value);
    // ignore: parameter_assignments
    hash = 0x1fffffff & (hash + ((0x0007ffff & hash) << 10));
    return hash ^ (hash >> 6);
  }

  static int finish(int hash) {
    // ignore: parameter_assignments
    hash = 0x1fffffff & (hash + ((0x03ffffff & hash) << 3));
    // ignore: parameter_assignments
    hash = hash ^ (hash >> 11);
    return 0x1fffffff & (hash + ((0x00003fff & hash) << 15));
  }
}

/// Provider for checking if a joke is saved (reactive)
///
/// Copied from [isJokeSaved].
@ProviderFor(isJokeSaved)
const isJokeSavedProvider = IsJokeSavedFamily();

/// Provider for checking if a joke is saved (reactive)
///
/// Copied from [isJokeSaved].
class IsJokeSavedFamily extends Family<AsyncValue<bool>> {
  /// Provider for checking if a joke is saved (reactive)
  ///
  /// Copied from [isJokeSaved].
  const IsJokeSavedFamily();

  /// Provider for checking if a joke is saved (reactive)
  ///
  /// Copied from [isJokeSaved].
  IsJokeSavedProvider call(String jokeId) {
    return IsJokeSavedProvider(jokeId);
  }

  @override
  IsJokeSavedProvider getProviderOverride(
    covariant IsJokeSavedProvider provider,
  ) {
    return call(provider.jokeId);
  }

  static const Iterable<ProviderOrFamily>? _dependencies = null;

  @override
  Iterable<ProviderOrFamily>? get dependencies => _dependencies;

  static const Iterable<ProviderOrFamily>? _allTransitiveDependencies = null;

  @override
  Iterable<ProviderOrFamily>? get allTransitiveDependencies =>
      _allTransitiveDependencies;

  @override
  String? get name => r'isJokeSavedProvider';
}

/// Provider for checking if a joke is saved (reactive)
///
/// Copied from [isJokeSaved].
class IsJokeSavedProvider extends AutoDisposeStreamProvider<bool> {
  /// Provider for checking if a joke is saved (reactive)
  ///
  /// Copied from [isJokeSaved].
  IsJokeSavedProvider(String jokeId)
    : this._internal(
        (ref) => isJokeSaved(ref as IsJokeSavedRef, jokeId),
        from: isJokeSavedProvider,
        name: r'isJokeSavedProvider',
        debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
            ? null
            : _$isJokeSavedHash,
        dependencies: IsJokeSavedFamily._dependencies,
        allTransitiveDependencies: IsJokeSavedFamily._allTransitiveDependencies,
        jokeId: jokeId,
      );

  IsJokeSavedProvider._internal(
    super._createNotifier, {
    required super.name,
    required super.dependencies,
    required super.allTransitiveDependencies,
    required super.debugGetCreateSourceHash,
    required super.from,
    required this.jokeId,
  }) : super.internal();

  final String jokeId;

  @override
  Override overrideWith(Stream<bool> Function(IsJokeSavedRef provider) create) {
    return ProviderOverride(
      origin: this,
      override: IsJokeSavedProvider._internal(
        (ref) => create(ref as IsJokeSavedRef),
        from: from,
        name: null,
        dependencies: null,
        allTransitiveDependencies: null,
        debugGetCreateSourceHash: null,
        jokeId: jokeId,
      ),
    );
  }

  @override
  AutoDisposeStreamProviderElement<bool> createElement() {
    return _IsJokeSavedProviderElement(this);
  }

  @override
  bool operator ==(Object other) {
    return other is IsJokeSavedProvider && other.jokeId == jokeId;
  }

  @override
  int get hashCode {
    var hash = _SystemHash.combine(0, runtimeType.hashCode);
    hash = _SystemHash.combine(hash, jokeId.hashCode);

    return _SystemHash.finish(hash);
  }
}

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
mixin IsJokeSavedRef on AutoDisposeStreamProviderRef<bool> {
  /// The parameter `jokeId` of this provider.
  String get jokeId;
}

class _IsJokeSavedProviderElement extends AutoDisposeStreamProviderElement<bool>
    with IsJokeSavedRef {
  _IsJokeSavedProviderElement(super.provider);

  @override
  String get jokeId => (origin as IsJokeSavedProvider).jokeId;
}

String _$isJokeSharedHash() => r'3ac6194580355bd623f2ea61c0ec6730e6415b49';

/// Provider for checking if a joke is shared (reactive)
///
/// Copied from [isJokeShared].
@ProviderFor(isJokeShared)
const isJokeSharedProvider = IsJokeSharedFamily();

/// Provider for checking if a joke is shared (reactive)
///
/// Copied from [isJokeShared].
class IsJokeSharedFamily extends Family<AsyncValue<bool>> {
  /// Provider for checking if a joke is shared (reactive)
  ///
  /// Copied from [isJokeShared].
  const IsJokeSharedFamily();

  /// Provider for checking if a joke is shared (reactive)
  ///
  /// Copied from [isJokeShared].
  IsJokeSharedProvider call(String jokeId) {
    return IsJokeSharedProvider(jokeId);
  }

  @override
  IsJokeSharedProvider getProviderOverride(
    covariant IsJokeSharedProvider provider,
  ) {
    return call(provider.jokeId);
  }

  static const Iterable<ProviderOrFamily>? _dependencies = null;

  @override
  Iterable<ProviderOrFamily>? get dependencies => _dependencies;

  static const Iterable<ProviderOrFamily>? _allTransitiveDependencies = null;

  @override
  Iterable<ProviderOrFamily>? get allTransitiveDependencies =>
      _allTransitiveDependencies;

  @override
  String? get name => r'isJokeSharedProvider';
}

/// Provider for checking if a joke is shared (reactive)
///
/// Copied from [isJokeShared].
class IsJokeSharedProvider extends AutoDisposeStreamProvider<bool> {
  /// Provider for checking if a joke is shared (reactive)
  ///
  /// Copied from [isJokeShared].
  IsJokeSharedProvider(String jokeId)
    : this._internal(
        (ref) => isJokeShared(ref as IsJokeSharedRef, jokeId),
        from: isJokeSharedProvider,
        name: r'isJokeSharedProvider',
        debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
            ? null
            : _$isJokeSharedHash,
        dependencies: IsJokeSharedFamily._dependencies,
        allTransitiveDependencies:
            IsJokeSharedFamily._allTransitiveDependencies,
        jokeId: jokeId,
      );

  IsJokeSharedProvider._internal(
    super._createNotifier, {
    required super.name,
    required super.dependencies,
    required super.allTransitiveDependencies,
    required super.debugGetCreateSourceHash,
    required super.from,
    required this.jokeId,
  }) : super.internal();

  final String jokeId;

  @override
  Override overrideWith(
    Stream<bool> Function(IsJokeSharedRef provider) create,
  ) {
    return ProviderOverride(
      origin: this,
      override: IsJokeSharedProvider._internal(
        (ref) => create(ref as IsJokeSharedRef),
        from: from,
        name: null,
        dependencies: null,
        allTransitiveDependencies: null,
        debugGetCreateSourceHash: null,
        jokeId: jokeId,
      ),
    );
  }

  @override
  AutoDisposeStreamProviderElement<bool> createElement() {
    return _IsJokeSharedProviderElement(this);
  }

  @override
  bool operator ==(Object other) {
    return other is IsJokeSharedProvider && other.jokeId == jokeId;
  }

  @override
  int get hashCode {
    var hash = _SystemHash.combine(0, runtimeType.hashCode);
    hash = _SystemHash.combine(hash, jokeId.hashCode);

    return _SystemHash.finish(hash);
  }
}

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
mixin IsJokeSharedRef on AutoDisposeStreamProviderRef<bool> {
  /// The parameter `jokeId` of this provider.
  String get jokeId;
}

class _IsJokeSharedProviderElement
    extends AutoDisposeStreamProviderElement<bool>
    with IsJokeSharedRef {
  _IsJokeSharedProviderElement(super.provider);

  @override
  String get jokeId => (origin as IsJokeSharedProvider).jokeId;
}

// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
