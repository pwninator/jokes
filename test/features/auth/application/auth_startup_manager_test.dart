import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_startup_manager.dart';
import 'package:snickerdoodle/src/features/auth/data/repositories/auth_repository.dart';

class _MockFirebaseAuth extends Mock implements FirebaseAuth {}

class _MockAuthRepository extends Mock implements AuthRepository {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockUser extends Mock implements User {}

void main() {
  setUpAll(() {
    registerFallbackValue(const Duration(seconds: 1));
  });

  test('does nothing when currentUser is already present', () async {
    final auth = _MockFirebaseAuth();
    final repo = _MockAuthRepository();
    final analytics = _MockAnalyticsService();

    final user = _MockUser();
    when(() => auth.currentUser).thenReturn(user);
    when(
      () => auth.authStateChanges(),
    ).thenAnswer((_) => const Stream<User?>.empty());

    final manager = AuthStartupManager(
      firebaseAuth: auth,
      authRepository: repo,
      analyticsService: analytics,
    );

    manager.start();
    await Future<void>.delayed(const Duration(milliseconds: 10));

    verifyNever(() => repo.signInAnonymously());
  });

  test('attempts anonymous sign-in after grace period when no user', () async {
    final auth = _MockFirebaseAuth();
    final repo = _MockAuthRepository();
    final analytics = _MockAnalyticsService();

    when(() => auth.currentUser).thenReturn(null);
    final controller = StreamController<User?>();
    when(() => auth.authStateChanges()).thenAnswer((_) => controller.stream);
    when(() => repo.signInAnonymously()).thenAnswer(
      (_) async =>
          // Return a valid AppUser to satisfy non-nullable generic in Future.value
          Future.value(AppUser.anonymous('test-anon-1')),
    );

    final manager = AuthStartupManager(
      firebaseAuth: auth,
      authRepository: repo,
      analyticsService: analytics,
      retrySchedule: const [Duration(milliseconds: 20)],
    );

    manager.start();
    await Future<void>.delayed(const Duration(milliseconds: 50));

    verify(() => repo.signInAnonymously()).called(1);
    await controller.close();
  });

  test('cancels retries when user appears', () async {
    final auth = _MockFirebaseAuth();
    final repo = _MockAuthRepository();
    final analytics = _MockAnalyticsService();

    when(() => auth.currentUser).thenReturn(null);
    final controller = StreamController<User?>();
    when(() => auth.authStateChanges()).thenAnswer((_) => controller.stream);
    when(
      () => repo.signInAnonymously(),
    ).thenAnswer((_) async => Future.value(AppUser.anonymous('test-anon-2')));

    final manager = AuthStartupManager(
      firebaseAuth: auth,
      authRepository: repo,
      analyticsService: analytics,
      retrySchedule: const [
        Duration(milliseconds: 20),
        Duration(milliseconds: 20),
      ],
    );

    manager.start();
    // First attempt should happen ~20ms
    await Future<void>.delayed(const Duration(milliseconds: 25));
    verify(() => repo.signInAnonymously()).called(1);

    // Emit a user to cancel further retries
    final user = _MockUser();
    controller.add(user);

    // Wait another backoff window; no additional calls expected
    await Future<void>.delayed(const Duration(milliseconds: 40));
    verifyNoMoreInteractions(repo);

    await controller.close();
  });
}
