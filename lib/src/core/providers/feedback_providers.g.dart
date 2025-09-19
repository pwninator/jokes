// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'feedback_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$userFeedbackHash() => r'563edd57bb0f7aec5fa94e58c155680cd8bff1bf';

/// See also [userFeedback].
@ProviderFor(userFeedback)
final userFeedbackProvider =
    AutoDisposeStreamProvider<List<FeedbackEntry>>.internal(
      userFeedback,
      name: r'userFeedbackProvider',
      debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
          ? null
          : _$userFeedbackHash,
      dependencies: null,
      allTransitiveDependencies: null,
    );

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef UserFeedbackRef = AutoDisposeStreamProviderRef<List<FeedbackEntry>>;
String _$unreadFeedbackHash() => r'807947adae7dda1badb59d32b25cd307531d4bf2';

/// See also [unreadFeedback].
@ProviderFor(unreadFeedback)
final unreadFeedbackProvider =
    AutoDisposeProvider<List<FeedbackEntry>>.internal(
      unreadFeedback,
      name: r'unreadFeedbackProvider',
      debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
          ? null
          : _$unreadFeedbackHash,
      dependencies: null,
      allTransitiveDependencies: null,
    );

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef UnreadFeedbackRef = AutoDisposeProviderRef<List<FeedbackEntry>>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
