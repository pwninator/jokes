import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/auth/data/repositories/auth_repository.dart';

// Mock classes for authentication
class MockAuthRepository extends Mock implements AuthRepository {}

class MockAuthController extends Mock implements AuthController {}

// Mock classes for GoogleSignIn v7.0.0 types (if needed for future tests)
class MockGoogleSignIn extends Mock implements GoogleSignIn {}

class MockGoogleSignInAccount extends Mock implements GoogleSignInAccount {}

class MockGoogleSignInAuthentication extends Mock
    implements GoogleSignInAuthentication {}

class MockFirebaseAuth extends Mock implements FirebaseAuth {}

/// Authentication-specific mocks for unit tests
class AuthMocks {
  static MockAuthRepository? _mockAuthRepository;
  static MockAuthController? _mockAuthController;

  /// Get or create mock auth repository
  static MockAuthRepository get mockAuthRepository {
    _mockAuthRepository ??= MockAuthRepository();
    _setupAuthRepositoryDefaults(_mockAuthRepository!);
    return _mockAuthRepository!;
  }

  /// Get or create mock auth controller
  static MockAuthController get mockAuthController {
    _mockAuthController ??= MockAuthController();
    _setupAuthControllerDefaults(_mockAuthController!);
    return _mockAuthController!;
  }

  /// Reset all auth mocks (call this in setUp if needed)
  static void reset() {
    _mockAuthRepository = null;
    _mockAuthController = null;
  }

  /// Get auth-specific provider overrides
  static List<Override> getAuthProviderOverrides({
    AppUser? testUser,
    List<Override> additionalOverrides = const [],
  }) {
    final defaultUser =
        testUser ??
        const AppUser(
          id: 'test-user',
          email: 'test@example.com',
          displayName: 'Test User',
          isAnonymous: false,
          role: UserRole.user,
        );

    return [
      // Mock auth repository
      authRepositoryProvider.overrideWithValue(mockAuthRepository),

      // Mock auth controller
      authControllerProvider.overrideWithValue(mockAuthController),

      // Mock auth state to return a test user stream
      authStateProvider.overrideWith((ref) => Stream.value(defaultUser)),

      // Add any additional overrides
      ...additionalOverrides,
    ];
  }

  /// Create anonymous user for testing
  static AppUser createAnonymousUser() {
    return const AppUser(
      id: 'test-anonymous-user',
      email: null,
      displayName: null,
      isAnonymous: true,
      role: UserRole.anonymous,
    );
  }

  /// Create authenticated user for testing
  static AppUser createAuthenticatedUser({
    String? email,
    String? displayName,
    UserRole? role,
  }) {
    return AppUser(
      id: 'test-auth-user',
      email: email ?? 'auth@example.com',
      displayName: displayName ?? 'Authenticated User',
      isAnonymous: false,
      role: role ?? UserRole.user,
    );
  }

  static void _setupAuthRepositoryDefaults(MockAuthRepository mock) {
    // Setup default behaviors that won't throw
    // Ensure mocktail has a fallback for Duration used in named matchers
    try {
      registerFallbackValue(const Duration(milliseconds: 1));
    } catch (_) {
      // ignore if already registered
    }
    when(() => mock.authStateChanges).thenAnswer(
      (_) => Stream.value(
        const AppUser(
          id: 'test-user',
          email: 'test@example.com',
          displayName: 'Test User',
          isAnonymous: false,
          role: UserRole.user,
        ),
      ),
    );
    when(() => mock.currentUser).thenAnswer(
      (_) async => const AppUser(
        id: 'test-user',
        email: 'test@example.com',
        displayName: 'Test User',
        isAnonymous: false,
        role: UserRole.user,
      ),
    );
    when(() => mock.signInAnonymously()).thenAnswer(
      (_) async => const AppUser(
        id: 'test-anonymous-user',
        email: null,
        displayName: null,
        isAnonymous: true,
        role: UserRole.anonymous,
      ),
    );
    when(() => mock.signInWithGoogle()).thenAnswer(
      (_) async => const AppUser(
        id: 'test-google-user',
        email: 'google@example.com',
        displayName: 'Google User',
        isAnonymous: false,
        role: UserRole.user,
      ),
    );
    when(() => mock.signOut()).thenAnswer((_) async {});
    when(
      () => mock.ensureSignedIn(waitForRestore: any(named: 'waitForRestore')),
    ).thenAnswer(
      (_) async => const AppUser(
        id: 'test-user',
        email: 'test@example.com',
        displayName: 'Test User',
        isAnonymous: false,
        role: UserRole.user,
      ),
    );
  }

  static void _setupAuthControllerDefaults(MockAuthController mock) {
    // Setup default behaviors that won't throw
    when(
      () => mock.ensureSignedIn(waitForRestore: any(named: 'waitForRestore')),
    ).thenAnswer(
      (_) async => const AppUser(
        id: 'test-user',
        email: 'test@example.com',
        displayName: 'Test User',
        isAnonymous: false,
        role: UserRole.user,
      ),
    );
    when(() => mock.signInAnonymously()).thenAnswer((_) async {});
    when(() => mock.signInWithGoogle()).thenAnswer((_) async {});
    when(() => mock.signOut()).thenAnswer((_) async {});
  }
}
