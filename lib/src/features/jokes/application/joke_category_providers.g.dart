// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'joke_category_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$jokeCategoryRepositoryHash() =>
    r'df8ea33f7e6e8269eb10bbce2edb1c56b20a9ef4';

/// See also [jokeCategoryRepository].
@ProviderFor(jokeCategoryRepository)
final jokeCategoryRepositoryProvider =
    Provider<JokeCategoryRepository>.internal(
      jokeCategoryRepository,
      name: r'jokeCategoryRepositoryProvider',
      debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
          ? null
          : _$jokeCategoryRepositoryHash,
      dependencies: null,
      allTransitiveDependencies: null,
    );

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef JokeCategoryRepositoryRef = ProviderRef<JokeCategoryRepository>;
String _$viewedCategoryIdsHash() => r'9210c49fca687c52404f50f376bfaac516938b30';

/// See also [viewedCategoryIds].
@ProviderFor(viewedCategoryIds)
final viewedCategoryIdsProvider = StreamProvider<Set<String>>.internal(
  viewedCategoryIds,
  name: r'viewedCategoryIdsProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$viewedCategoryIdsHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef ViewedCategoryIdsRef = StreamProviderRef<Set<String>>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
