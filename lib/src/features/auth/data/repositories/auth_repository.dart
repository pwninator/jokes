import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

class AuthRepository {
  final FirebaseAuth _firebaseAuth;
  final GoogleSignIn _googleSignIn;

  AuthRepository(this._firebaseAuth, this._googleSignIn);

  /// Stream of authentication state changes
  Stream<AppUser?> get authStateChanges {
    return _firebaseAuth.authStateChanges().asyncMap((firebaseUser) async {
      if (firebaseUser == null) return null;
      return await _createAppUser(firebaseUser);
    });
  }

  /// Current user (synchronous)
  Future<AppUser?> get currentUser async {
    final firebaseUser = _firebaseAuth.currentUser;
    if (firebaseUser == null) return null;
    return await _createAppUser(firebaseUser);
  }

  /// Sign in anonymously
  Future<AppUser> signInAnonymously() async {
    try {
      debugPrint('DEBUG: Starting anonymous sign-in...');
      final credential = await _firebaseAuth.signInAnonymously();
      final firebaseUser = credential.user!;
      debugPrint(
        'DEBUG: Anonymous sign-in successful. User ID: ${firebaseUser.uid}',
      );
      return AppUser.anonymous(firebaseUser.uid);
    } catch (e, stackTrace) {
      debugPrint('DEBUG: Anonymous sign-in failed: $e');
      debugPrint('DEBUG: Stack trace: $stackTrace');
      throw AuthException('Failed to sign in anonymously: $e');
    }
  }

  Future<AppUser> signInWithGoogle() async {
    try {
      debugPrint('DEBUG: Starting Google sign-in flow...');

      // Authenticate with Google (replaces signIn())
      final GoogleSignInAccount googleUser = await _googleSignIn.authenticate();

      debugPrint('DEBUG: Google user authenticated: ${googleUser.email}');

      // Get the authentication object for idToken
      final GoogleSignInAuthentication googleAuth = googleUser.authentication;
      final String? idToken = googleAuth.idToken;

      // Get authorization for Firebase scopes to get accessToken
      const scopes = ['openid', 'email', 'profile'];
      final authorization = await googleUser.authorizationClient
          .authorizeScopes(scopes);

      final String accessToken = authorization.accessToken;

      debugPrint(
        'DEBUG: Google auth tokens obtained - accessToken: $accessToken, idToken: $idToken',
      );

      // Create a new credential
      final credential = GoogleAuthProvider.credential(
        accessToken: accessToken,
        idToken: idToken,
      );

      debugPrint('DEBUG: Firebase credential created, signing in...');

      // Sign in to Firebase with the Google credential
      final userCredential = await _firebaseAuth.signInWithCredential(
        credential,
      );
      final firebaseUser = userCredential.user!;

      debugPrint(
        'DEBUG: Firebase sign-in successful. User: ${firebaseUser.uid}, Email: ${firebaseUser.email}',
      );

      final appUser = await _createAppUser(firebaseUser);
      debugPrint(
        'DEBUG: AppUser created successfully: ${appUser.email}, Role: ${appUser.role}',
      );

      return appUser;
    } catch (e, stackTrace) {
      debugPrint('DEBUG: Google sign-in failed with error: $e');
      debugPrint('DEBUG: Stack trace: $stackTrace');
      throw AuthException('Failed to sign in with Google: $e');
    }
  }

  /// Sign out and automatically sign in anonymously - Updated for v7.0.0
  Future<void> signOut() async {
    try {
      debugPrint('DEBUG: Starting sign out process...');

      // Disconnect from Google (replaces signOut())
      await _googleSignIn.disconnect();
      await _firebaseAuth.signOut();
      debugPrint('DEBUG: Sign out successful, signing in anonymously...');

      // Automatically sign in anonymously after signing out
      await signInAnonymously();
      debugPrint('DEBUG: Switched to anonymous authentication');
    } catch (e) {
      debugPrint('DEBUG: Sign out failed: $e');
      throw AuthException('Failed to sign out: $e');
    }
  }

  /// Create AppUser from FirebaseUser
  Future<AppUser> _createAppUser(User firebaseUser) async {
    if (firebaseUser.isAnonymous) {
      return AppUser.anonymous(firebaseUser.uid);
    }

    // Get user role from Firebase Auth custom claims
    final userRole = await _getUserRoleFromClaims(firebaseUser);

    return AppUser.authenticated(
      id: firebaseUser.uid,
      email: firebaseUser.email,
      displayName: firebaseUser.displayName,
      role: userRole,
    );
  }

  /// Get user role from Firebase Auth custom claims
  Future<UserRole> _getUserRoleFromClaims(User firebaseUser) async {
    try {
      debugPrint(
        'DEBUG: Getting user role from custom claims for UID: ${firebaseUser.uid}',
      );

      // Get the ID token to access custom claims
      final idTokenResult = await firebaseUser.getIdTokenResult();
      final claims = idTokenResult.claims;

      // Extract role from custom claims
      final roleString = claims?['role'] as String?;
      debugPrint('DEBUG: User role found in custom claims: $roleString');

      return _parseUserRole(roleString);
    } catch (e) {
      debugPrint(
        'DEBUG: Error getting user role from claims: $e, defaulting to user role',
      );
      return UserRole.user; // Default role on error
    }
  }

  /// Parse UserRole from string
  UserRole _parseUserRole(String? roleString) {
    switch (roleString?.toLowerCase()) {
      case 'admin':
        return UserRole.admin;
      case 'user':
        return UserRole.user;
      case 'anonymous':
        return UserRole.anonymous;
      default:
        return UserRole.user;
    }
  }
}

class AuthException implements Exception {
  final String message;
  AuthException(this.message);

  @override
  String toString() => 'AuthException: $message';
}
