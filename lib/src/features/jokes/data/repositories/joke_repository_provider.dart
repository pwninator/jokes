import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';

// Provider for FirebaseFirestore instance (local to jokes feature)
final firebaseFirestoreProvider = Provider<FirebaseFirestore>((ref) {
  return FirebaseFirestore.instance;
});

// Provider for JokeRepository
final jokeRepositoryProvider = Provider<JokeRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  final isAdmin = ref.watch(isAdminProvider);
  final perf = ref.read(performanceServiceProvider);
  return JokeRepository(firestore, isAdmin, kDebugMode, perf: perf);
});
