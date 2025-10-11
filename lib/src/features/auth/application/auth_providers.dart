import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/auth/data/repositories/auth_repository.dart';

part 'auth_providers.g.dart';

/// Provider for GoogleSignIn instance
@Riverpod(keepAlive: true)
GoogleSignIn googleSignIn(Ref ref) {
  return GoogleSignIn(scopes: ['email', 'profile']);
}

/// Provider for AuthRepository
@Riverpod(keepAlive: true)
AuthRepository authRepository(Ref ref) {
  final firebaseAuth = ref.watch(firebaseAuthProvider);
  final googleSignIn = ref.watch(googleSignInProvider);
  return AuthRepository(firebaseAuth, googleSignIn);
}

/// StreamProvider for authentication state
@Riverpod(keepAlive: true)
Stream<AppUser?> authState(Ref ref) {
  final authRepository = ref.watch(authRepositoryProvider);
  return authRepository.authStateChanges;
}

/// Provider to check if user is authenticated
@Riverpod()
bool isAuthenticated(Ref ref) {
  final authState = ref.watch(authStateProvider);
  return authState.maybeWhen(data: (user) => user != null, orElse: () => false);
}

/// Provider to check if user is admin
@Riverpod()
bool isAdmin(Ref ref) {
  final authState = ref.watch(authStateProvider);
  return authState.maybeWhen(
    data: (user) => user?.isAdmin ?? false,
    orElse: () => false,
  );
}

/// Provider to check if user is anonymous
@Riverpod()
bool isAnonymous(Ref ref) {
  final authState = ref.watch(authStateProvider);
  return authState.maybeWhen(
    data: (user) => user?.isAnonymous ?? false,
    orElse: () => false,
  );
}

/// Provider for the current user
@Riverpod()
AppUser? currentUser(Ref ref) {
  final authState = ref.watch(authStateProvider);
  return authState.maybeWhen(data: (user) => user, orElse: () => null);
}

/// Auth controller for managing authentication actions
@Riverpod(keepAlive: true)
AuthController authController(Ref ref) {
  final authRepository = ref.watch(authRepositoryProvider);
  return AuthController(authRepository);
}

class AuthController {
  final AuthRepository _authRepository;

  AuthController(this._authRepository);

  Future<void> signInAnonymously() async {
    await _authRepository.signInAnonymously();
  }

  Future<void> signInWithGoogle() async {
    await _authRepository.signInWithGoogle();
  }

  Future<void> signOut() async {
    await _authRepository.signOut();
  }
}
