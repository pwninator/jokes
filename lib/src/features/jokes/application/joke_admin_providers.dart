import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

// Unified admin jokes provider: search path uses live search; otherwise
// builds from filtered snapshot of IDs and streams per-doc.
final adminJokesLiveProvider =
    Provider<AsyncValue<List<JokeWithVectorDistance>>>((ref) {
      final searchParams = ref.watch(
        searchQueryProvider(SearchScope.jokeManagementSearch),
      );

      // If there is a search query, delegate to live search provider
      if (searchParams.query.trim().isNotEmpty) {
        return ref.watch(
          searchResultsLiveProvider(SearchScope.jokeManagementSearch),
        );
      }

      final idsAsync = ref.watch(filteredJokeIdsProvider);
      if (idsAsync.isLoading) {
        return const AsyncValue.loading();
      }
      if (idsAsync.hasError) {
        return AsyncValue.error(
          idsAsync.error!,
          idsAsync.stackTrace ?? StackTrace.current,
        );
      }

      final ids = idsAsync.value ?? const <String>[];
      if (ids.isEmpty) {
        return const AsyncValue.data(<JokeWithVectorDistance>[]);
      }

      // Watch each joke by id
      final perJoke = <AsyncValue<Joke?>>[];
      for (final id in ids) {
        perJoke.add(ref.watch(jokeByIdProvider(id)));
      }

      // If any still loading, show loading
      if (perJoke.any((j) => j.isLoading)) {
        return const AsyncValue.loading();
      }

      // Surface first error if any
      final firstError = perJoke.firstWhere(
        (j) => j.hasError,
        orElse: () => const AsyncValue.data(null),
      );
      if (firstError.hasError) {
        return AsyncValue.error(
          firstError.error!,
          firstError.stackTrace ?? StackTrace.current,
        );
      }

      // Build ordered list based on ids, skipping nulls
      final ordered = <JokeWithVectorDistance>[];
      for (var i = 0; i < ids.length; i++) {
        final value = perJoke[i].value;
        if (value != null) {
          ordered.add(
            JokeWithVectorDistance(joke: value, vectorDistance: null),
          );
        }
      }

      return AsyncValue.data(ordered);
    });
