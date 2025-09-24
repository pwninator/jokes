import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

class PopularJokesPaginator {
  PopularJokesPaginator({
    required this.ref,
    this.jokes = const [],
    this.hasMore = true,
    this.isLoading = false,
    this.cursor,
  });

  final Ref ref;
  final List<Joke> jokes;
  final bool hasMore;
  final bool isLoading;
  final JokeListPageCursor? cursor;

  PopularJokesPaginator copyWith({
    List<Joke>? jokes,
    bool? hasMore,
    bool? isLoading,
    JokeListPageCursor? cursor,
  }) {
    return PopularJokesPaginator(
      ref: ref,
      jokes: jokes ?? this.jokes,
      hasMore: hasMore ?? this.hasMore,
      isLoading: isLoading ?? this.isLoading,
      cursor: cursor ?? this.cursor,
    );
  }
}

final popularJokesPaginatorProvider =
    StateNotifierProvider<PopularJokesPaginatorNotifier, PopularJokesPaginator>(
  (ref) => PopularJokesPaginatorNotifier(ref: ref),
);

class PopularJokesPaginatorNotifier extends StateNotifier<PopularJokesPaginator> {
  PopularJokesPaginatorNotifier({required Ref ref})
      : super(PopularJokesPaginator(ref: ref)) {
    loadMore();
  }

  Future<void> loadMore() async {
    if (state.isLoading || !state.hasMore) return;

    state = state.copyWith(isLoading: true);

    final jokeRepository = state.ref.read(jokeRepositoryProvider);
    final result = await jokeRepository.getPopularJokes(
      limit: 10,
      lastDoc: state.cursor,
    );

    if (result.ids.isNotEmpty) {
      final newJokes =
          await state.ref.read(jokesByIdsGetProvider(result.ids).future);
      state = state.copyWith(
        jokes: [...state.jokes, ...newJokes],
        cursor: result.cursor,
        isLoading: false,
      );
    } else {
      state = state.copyWith(hasMore: false, isLoading: false);
    }
  }
}

final popularJokesProvider =
    Provider<AsyncValue<List<JokeWithDate>>>((ref) {
  final paginator = ref.watch(popularJokesPaginatorProvider);
  final jokes = paginator.jokes
      .map((joke) => JokeWithDate(joke: joke))
      .toList();
  return AsyncValue.data(jokes);
});
