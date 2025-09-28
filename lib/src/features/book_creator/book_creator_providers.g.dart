// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'book_creator_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$searchedJokesHash() => r'c7402150c9905e41bed753104d2818d0ce5fc631';

/// See also [searchedJokes].
@ProviderFor(searchedJokes)
final searchedJokesProvider = AutoDisposeFutureProvider<List<Joke>>.internal(
  searchedJokes,
  name: r'searchedJokesProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$searchedJokesHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef SearchedJokesRef = AutoDisposeFutureProviderRef<List<Joke>>;
String _$bookTitleHash() => r'4cd698ed7d290db36ab3b6ddc061ad5019655583';

/// See also [BookTitle].
@ProviderFor(BookTitle)
final bookTitleProvider = NotifierProvider<BookTitle, String>.internal(
  BookTitle.new,
  name: r'bookTitleProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$bookTitleHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$BookTitle = Notifier<String>;
String _$selectedJokesHash() => r'18b2e2718c75b1056ada156e6fab3c649483591b';

/// See also [SelectedJokes].
@ProviderFor(SelectedJokes)
final selectedJokesProvider =
    NotifierProvider<SelectedJokes, List<Joke>>.internal(
      SelectedJokes.new,
      name: r'selectedJokesProvider',
      debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
          ? null
          : _$selectedJokesHash,
      dependencies: null,
      allTransitiveDependencies: null,
    );

typedef _$SelectedJokes = Notifier<List<Joke>>;
String _$jokeSearchQueryHash() => r'aad8d89d632a99665d9e99696a37045db7fdf575';

/// See also [JokeSearchQuery].
@ProviderFor(JokeSearchQuery)
final jokeSearchQueryProvider =
    NotifierProvider<JokeSearchQuery, String>.internal(
      JokeSearchQuery.new,
      name: r'jokeSearchQueryProvider',
      debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
          ? null
          : _$jokeSearchQueryHash,
      dependencies: null,
      allTransitiveDependencies: null,
    );

typedef _$JokeSearchQuery = Notifier<String>;
String _$bookCreatorControllerHash() =>
    r'5630b682b1499cfd6f6941d8de28fd7dd1782b4d';

/// See also [BookCreatorController].
@ProviderFor(BookCreatorController)
final bookCreatorControllerProvider =
    AutoDisposeAsyncNotifierProvider<BookCreatorController, void>.internal(
      BookCreatorController.new,
      name: r'bookCreatorControllerProvider',
      debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
          ? null
          : _$bookCreatorControllerHash,
      dependencies: null,
      allTransitiveDependencies: null,
    );

typedef _$BookCreatorController = AutoDisposeAsyncNotifier<void>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
