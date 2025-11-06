// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'joke_category_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$jokeCategoryRepositoryHash() =>
    r'a90b44542ec17e50f43655afd468556383b85c32';

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
String _$hasUnviewedCategoriesHash() =>
    r'59c174722466c3e5b277b152b207101f9aaa5668';

/// Whether there exist any approved Discover categories that the user has not viewed yet.
/// Used to show an "unviewed" indicator on the Discover tab icon.
///
/// Copied from [hasUnviewedCategories].
@ProviderFor(hasUnviewedCategories)
final hasUnviewedCategoriesProvider = Provider<bool>.internal(
  hasUnviewedCategories,
  name: r'hasUnviewedCategoriesProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$hasUnviewedCategoriesHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef HasUnviewedCategoriesRef = ProviderRef<bool>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
