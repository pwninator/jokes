import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

part 'book_creator_providers.g.dart';

@Riverpod(keepAlive: true)
class BookTitle extends _$BookTitle {
  @override
  String build() => '';

  void setTitle(String title) {
    state = title;
  }
}

@Riverpod(keepAlive: true)
class SelectedJokes extends _$SelectedJokes {
  @override
  List<Joke> build() => [];

  void addJoke(Joke joke) {
    if (!state.any((j) => j.id == joke.id)) {
      state = [...state, joke];
    }
  }

  void removeJoke(Joke joke) {
    state = state.where((j) => j.id != joke.id).toList();
  }

  void setJokes(List<Joke> jokes) {
    state = jokes;
  }

  void toggleJokeSelection(Joke joke) {
    if (state.any((j) => j.id == joke.id)) {
      removeJoke(joke);
    } else {
      addJoke(joke);
    }
  }
}

@Riverpod(keepAlive: true)
class JokeSearchQuery extends _$JokeSearchQuery {
  @override
  String build() => '';

  void setQuery(String query) {
    state = query;
  }
}

@riverpod
Future<List<Joke>> searchedJokes(SearchedJokesRef ref) async {
  final query = ref.watch(jokeSearchQueryProvider);
  if (query.isEmpty) {
    return [];
  }
  final bookRepository = ref.watch(bookRepositoryProvider);
  return await bookRepository.searchJokes(query);
}

@riverpod
class BookCreatorController extends _$BookCreatorController {
  @override
  Future<void> build() async {
    // No-op
  }

  Future<bool> createBook() async {
    state = const AsyncLoading();
    final title = ref.read(bookTitleProvider);
    final jokes = ref.read(selectedJokesProvider);

    if (title.isEmpty || jokes.isEmpty) {
      state = AsyncError('Title and jokes cannot be empty', StackTrace.current);
      return false;
    }

    final bookRepository = ref.read(bookRepositoryProvider);
    try {
      await bookRepository.createBook(title, jokes.map((j) => j.id).toList());
      state = const AsyncData(null);
      return true;
    } catch (e, st) {
      state = AsyncError(e, st);
      return false;
    }
  }
}
