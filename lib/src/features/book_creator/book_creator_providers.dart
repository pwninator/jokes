import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

// Book title state + provider
class BookTitle extends StateNotifier<String> {
  BookTitle() : super('');

  void setTitle(String title) {
    state = title;
  }
}

final bookTitleProvider = StateNotifierProvider<BookTitle, String>(
  (ref) => BookTitle(),
);

// Selected jokes state + provider
class SelectedJokes extends StateNotifier<List<Joke>> {
  SelectedJokes() : super(const []);

  void addJoke(Joke joke) {
    if (!state.any((existing) => existing.id == joke.id)) {
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

final selectedJokesProvider = StateNotifierProvider<SelectedJokes, List<Joke>>(
  (ref) => SelectedJokes(),
);

// Search query state + provider
class JokeSearchQuery extends StateNotifier<String> {
  JokeSearchQuery() : super('');

  void setQuery(String query) {
    state = query;
  }
}

final jokeSearchQueryProvider = StateNotifierProvider<JokeSearchQuery, String>(
  (ref) => JokeSearchQuery(),
);

// Search results provider
final searchedJokesProvider = FutureProvider.autoDispose<List<Joke>>((
  ref,
) async {
  final query = ref.watch(jokeSearchQueryProvider);
  if (query.isEmpty) {
    return [];
  }
  final bookRepository = ref.watch(bookRepositoryProvider);
  return bookRepository.searchJokes(query);
});

// Controller for creating a book
class BookCreatorController extends AutoDisposeAsyncNotifier<void> {
  @override
  Future<void> build() async {}

  Future<bool> createBook() async {
    state = const AsyncLoading();
    final title = ref.read(bookTitleProvider);
    final jokes = ref.read(selectedJokesProvider);

    if (title.isEmpty) {
      state = AsyncError('Title cannot be empty', StackTrace.current);
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

final bookCreatorControllerProvider =
    AutoDisposeAsyncNotifierProvider<BookCreatorController, void>(
      BookCreatorController.new,
    );
