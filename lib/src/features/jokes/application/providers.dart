import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jokes/src/features/jokes/data/models/joke_model.dart';
import 'package:jokes/src/features/jokes/data/repositories/joke_repository.dart';

// Provider for FirebaseFirestore instance
final firebaseFirestoreProvider = Provider<FirebaseFirestore>((ref) {
  return FirebaseFirestore.instance;
});

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
