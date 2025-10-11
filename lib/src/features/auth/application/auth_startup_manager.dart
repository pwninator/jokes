import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/repositories/auth_repository.dart';

part 'auth_startup_manager.g.dart';

/// Coordinates background authentication at app startup.
///
/// Goals:
/// - Do not block UI while waiting for auth.
/// - Preserve previously restored sessions; avoid racing them.
/// - If no user appears, attempt anonymous sign-in with backoff.
class AuthStartupManager {
  AuthStartupManager({
    required FirebaseAuth firebaseAuth,
    required AuthRepository authRepository,
    required AnalyticsService analyticsService,
    List<Duration>? retrySchedule,
  }) : _firebaseAuth = firebaseAuth,
       _authRepository = authRepository,
       _analyticsService = analyticsService,
       _retrySchedule =
           retrySchedule ??
           const <Duration>[
             Duration(seconds: 4),
             Duration(seconds: 15),
             Duration(seconds: 60),
             Duration(minutes: 5),
           ];

  final FirebaseAuth _firebaseAuth;
  final AuthRepository _authRepository;
  final AnalyticsService _analyticsService;
  final List<Duration> _retrySchedule;

  bool _started = false;
  int _attemptIndex = 0;
  Timer? _timer;
  StreamSubscription<User?>? _authSub;

  /// Begin background auth flow. Safe to call multiple times; subsequent calls are no-ops.
  void start() {
    if (_started) return;
    _started = true;

    // If already signed in, nothing to do.
    if (_firebaseAuth.currentUser != null) {
      return;
    }

    // Listen for restoration or explicit sign-ins; cancel retries when a user appears.
    _authSub = _firebaseAuth.authStateChanges().listen((User? user) {
      if (user != null) {
        _cancelTimer();
      }
    });

    // Schedule initial attempt after a grace period to allow restoration.
    _scheduleNextAttempt();
  }

  void _scheduleNextAttempt() {
    if (_firebaseAuth.currentUser != null) return;

    final Duration delay =
        _retrySchedule[_attemptIndex.clamp(0, _retrySchedule.length - 1)];
    _cancelTimer();
    _timer = Timer(delay, () async {
      if (_firebaseAuth.currentUser != null) {
        return;
      }
      try {
        AppLogger.debug(
          'AuthStartupManager: attempting anonymous sign-in (attempt ${_attemptIndex + 1})',
        );
        await _authRepository.signInAnonymously();
        // Success: authStateChanges will fire and cancel the timer via listener.
      } catch (e, stackTrace) {
        // Silent failure per requirements; log analytics non-fatal.
        try {
          _analyticsService.logErrorAuthSignIn(
            source: 'startup_background_sign_in',
            errorMessage: e.toString(),
          );
        } catch (_) {}
        AppLogger.warn('AuthStartupManager: anonymous sign-in failed: $e');
        AppLogger.debug('STACKTRACE: $stackTrace');
        // Schedule next attempt with backoff if still unsigned.
        if (_firebaseAuth.currentUser == null) {
          _attemptIndex = (_attemptIndex + 1).clamp(
            0,
            _retrySchedule.length - 1,
          );
          _scheduleNextAttempt();
        }
      }
    });
  }

  void _cancelTimer() {
    _timer?.cancel();
    _timer = null;
  }

  /// Dispose resources. Typically managed by provider lifecycle.
  void dispose() {
    _cancelTimer();
    _authSub?.cancel();
    _authSub = null;
  }
}

/// Provider for AuthStartupManager
@Riverpod(keepAlive: true)
AuthStartupManager authStartupManager(Ref ref) {
  final firebaseAuth = ref.watch(firebaseAuthProvider);
  final authRepo = ref.watch(authRepositoryProvider);
  final analytics = ref.watch(analyticsServiceProvider);

  final manager = AuthStartupManager(
    firebaseAuth: firebaseAuth,
    authRepository: authRepo,
    analyticsService: analytics,
  );

  ref.onDispose(manager.dispose);
  return manager;
}
