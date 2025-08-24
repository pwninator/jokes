import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/auth/data/repositories/auth_repository.dart';

class _MockFirebaseAuth extends Mock implements FirebaseAuth {}

class _MockGoogleSignIn extends Mock implements GoogleSignIn {}

class _MockUser extends Mock implements User {}

class _MockUserCredential extends Mock implements UserCredential {}

void main() {
  late _MockFirebaseAuth mockAuth;
  late _MockGoogleSignIn mockGoogle;
  late AuthRepository repository;

  setUpAll(() {
    registerFallbackValue(const Duration(milliseconds: 1));
  });

  setUp(() {
    mockAuth = _MockFirebaseAuth();
    mockGoogle = _MockGoogleSignIn();
    repository = AuthRepository(mockAuth, mockGoogle);
  });

  group('ensureSignedIn', () {
    test(
      'returns existing current anonymous user without signing in again',
      () async {
        final user = _MockUser();
        when(() => user.uid).thenReturn('existing-anon');
        when(() => user.isAnonymous).thenReturn(true);
        when(() => mockAuth.currentUser).thenReturn(user);

        final appUser = await repository.ensureSignedIn(
          waitForRestore: const Duration(milliseconds: 50),
        );

        expect(appUser.id, 'existing-anon');
        expect(appUser.isAnonymous, isTrue);
        verifyNever(() => mockAuth.signInAnonymously());
      },
    );

    test('waits for restoration and returns restored anonymous user', () async {
      when(() => mockAuth.currentUser).thenReturn(null);
      final controller = StreamController<User?>();
      when(
        () => mockAuth.authStateChanges(),
      ).thenAnswer((_) => controller.stream);

      final restored = _MockUser();
      when(() => restored.uid).thenReturn('restored-anon');
      when(() => restored.isAnonymous).thenReturn(true);

      // Emit restored user shortly after call
      Future<void>.delayed(const Duration(milliseconds: 30), () {
        controller.add(restored);
      });

      final appUser = await repository.ensureSignedIn(
        waitForRestore: const Duration(milliseconds: 200),
      );

      expect(appUser.id, 'restored-anon');
      expect(appUser.isAnonymous, isTrue);
      verifyNever(() => mockAuth.signInAnonymously());

      await controller.close();
    });

    test('times out restoration and signs in anonymously', () async {
      when(() => mockAuth.currentUser).thenReturn(null);
      when(
        () => mockAuth.authStateChanges(),
      ).thenAnswer((_) => const Stream<User?>.empty());

      final anonUser = _MockUser();
      when(() => anonUser.uid).thenReturn('new-anon');
      when(() => anonUser.isAnonymous).thenReturn(true);

      final credential = _MockUserCredential();
      when(() => credential.user).thenReturn(anonUser);
      when(
        () => mockAuth.signInAnonymously(),
      ).thenAnswer((_) async => credential);

      final appUser = await repository.ensureSignedIn(
        waitForRestore: const Duration(milliseconds: 30),
      );

      expect(appUser.id, 'new-anon');
      expect(appUser.isAnonymous, isTrue);
      verify(() => mockAuth.signInAnonymously()).called(1);
    });

    test('de-duplicates concurrent calls', () async {
      when(() => mockAuth.currentUser).thenReturn(null);
      when(
        () => mockAuth.authStateChanges(),
      ).thenAnswer((_) => const Stream<User?>.empty());

      final anonUser = _MockUser();
      when(() => anonUser.uid).thenReturn('dedup-anon');
      when(() => anonUser.isAnonymous).thenReturn(true);

      final credential = _MockUserCredential();
      when(() => credential.user).thenReturn(anonUser);

      final completer = Completer<UserCredential>();
      when(
        () => mockAuth.signInAnonymously(),
      ).thenAnswer((_) => completer.future);

      final f1 = repository.ensureSignedIn(
        waitForRestore: const Duration(milliseconds: 10),
      );
      final f2 = repository.ensureSignedIn(
        waitForRestore: const Duration(milliseconds: 10),
      );

      // Complete sign-in once; both futures should resolve with same result
      completer.complete(credential);

      final results = await Future.wait([f1, f2]);
      expect(results[0].id, 'dedup-anon');
      expect(results[1].id, 'dedup-anon');
      verify(() => mockAuth.signInAnonymously()).called(1);
    });
  });
}
