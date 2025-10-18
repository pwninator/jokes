import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_performance/firebase_performance.dart';
import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'firebase_providers.g.dart';

@Riverpod(keepAlive: true)
FirebaseFirestore firebaseFirestore(Ref ref) {
  throw StateError(
    'FirebaseFirestore must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebasePerformance firebasePerformance(Ref ref) {
  throw StateError(
    'FirebasePerformance must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebaseAnalytics firebaseAnalytics(Ref ref) {
  throw StateError(
    'FirebaseAnalytics must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebaseFunctions firebaseFunctions(Ref ref) {
  throw StateError(
    'FirebaseFunctions must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebaseRemoteConfig firebaseRemoteConfig(Ref ref) {
  throw StateError(
    'FirebaseRemoteConfig must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebaseAuth firebaseAuth(Ref ref) {
  throw StateError(
    'FirebaseAuth must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebaseMessaging firebaseMessaging(Ref ref) {
  throw StateError(
    'FirebaseMessaging must be overridden. If this is a test, you are missing a mock somewhere',
  );
}

@Riverpod(keepAlive: true)
FirebaseCrashlytics firebaseCrashlytics(Ref ref) {
  throw StateError(
    'FirebaseCrashlytics must be overridden. If this is a test, you are missing a mock somewhere',
  );
}
