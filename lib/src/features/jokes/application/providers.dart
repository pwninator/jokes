import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

// Provider for JokeRepository
final jokeRepositoryProvider = Provider<JokeRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return JokeRepository(firestore);
});

// StreamProvider for the list of jokes
final jokesProvider = StreamProvider<List<Joke>>((ref) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokes();
});
