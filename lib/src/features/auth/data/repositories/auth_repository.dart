import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

class AuthRepository {
  final FirebaseAuth _firebaseAuth;
  final FirebaseFirestore _firestore;
  final GoogleSignIn _googleSignIn;

  AuthRepository(this._firebaseAuth, this._firestore, this._googleSignIn);

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
      debugPrint('DEBUG: Anonymous sign-in successful. User ID: ${firebaseUser.uid}');
      return AppUser.anonymous(firebaseUser.uid);
    } catch (e, stackTrace) {
      debugPrint('DEBUG: Anonymous sign-in failed: $e');
      debugPrint('DEBUG: Stack trace: $stackTrace');
      throw AuthException('Failed to sign in anonymously: $e');
    }
  }

  /// Sign in with Google
  Future<AppUser> signInWithGoogle() async {
    try {
      debugPrint('DEBUG: Starting Google sign-in flow...');
      
      // Trigger the authentication flow
      final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
      
              if (googleUser == null) {
          debugPrint('DEBUG: Google sign-in was cancelled by user');
          throw AuthException('Google sign-in was cancelled');
        }

        debugPrint('DEBUG: Google user selected: ${googleUser.email}');

        // Obtain the auth details from the request
        final GoogleSignInAuthentication googleAuth = await googleUser.authentication;
        
        debugPrint('DEBUG: Google auth tokens obtained - accessToken: ${googleAuth.accessToken != null ? 'present' : 'null'}, idToken: ${googleAuth.idToken != null ? 'present' : 'null'}');

      // Create a new credential
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

              debugPrint('DEBUG: Firebase credential created, signing in...');

        // Sign in to Firebase with the Google credential
        final userCredential = await _firebaseAuth.signInWithCredential(credential);
        final firebaseUser = userCredential.user!;

        debugPrint('DEBUG: Firebase sign-in successful. User: ${firebaseUser.uid}, Email: ${firebaseUser.email}');

        // Create user document in Firestore if this is a new user
        if (userCredential.additionalUserInfo?.isNewUser == true) {
          debugPrint('DEBUG: New user detected, creating user document...');
          await _createUserDocument(firebaseUser, firebaseUser.displayName);
        } else {
          debugPrint('DEBUG: Existing user, skipping document creation');
        }

        final appUser = await _createAppUser(firebaseUser);
        debugPrint('DEBUG: AppUser created successfully: ${appUser.email}, Role: ${appUser.role}');
        
        return appUser;
      } catch (e, stackTrace) {
        debugPrint('DEBUG: Google sign-in failed with error: $e');
        debugPrint('DEBUG: Stack trace: $stackTrace');
      throw AuthException('Failed to sign in with Google: $e');
    }
  }

  /// Sign out
  Future<void> signOut() async {
    try {
      await _googleSignIn.signOut();
      await _firebaseAuth.signOut();
    } catch (e) {
      throw AuthException('Failed to sign out: $e');
    }
  }

  /// Create AppUser from FirebaseUser
  Future<AppUser> _createAppUser(User firebaseUser) async {
    if (firebaseUser.isAnonymous) {
      return AppUser.anonymous(firebaseUser.uid);
    }

    // Get user role from Firestore
    final userRole = await _getUserRole(firebaseUser.uid);

    return AppUser.authenticated(
      id: firebaseUser.uid,
      email: firebaseUser.email,
      displayName: firebaseUser.displayName,
      role: userRole,
    );
  }

  /// Get user role from Firestore
  Future<UserRole> _getUserRole(String uid) async {
    try {
      debugPrint('DEBUG: Getting user role for UID: $uid');
      final doc = await _firestore.collection('users').doc(uid).get();
      if (doc.exists) {
        final data = doc.data()!;
        final roleString = data['role'] as String?;
        debugPrint('DEBUG: User role found in Firestore: $roleString');
        return _parseUserRole(roleString);
      }
      debugPrint('DEBUG: User document not found, defaulting to user role');
      return UserRole.user; // Default role
    } catch (e) {
      debugPrint('DEBUG: Error getting user role: $e, defaulting to user role');
      return UserRole.user; // Default role on error
    }
  }

  /// Create user document in Firestore
  Future<void> _createUserDocument(User firebaseUser, String? displayName) async {
    try {
      await _firestore.collection('users').doc(firebaseUser.uid).set({
        'email': firebaseUser.email,
        'displayName': displayName ?? firebaseUser.displayName,
        'role': 'user',
        'createdAt': FieldValue.serverTimestamp(),
        'updatedAt': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      // Log error but don't throw - user creation succeeded even if document creation failed
      // In production, consider using a proper logging solution like logger package
      debugPrint('DEBUG: Failed to create user document: $e');
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