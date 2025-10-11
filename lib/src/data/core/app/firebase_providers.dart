import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_performance/firebase_performance.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'firebase_providers.g.dart';

@Riverpod(keepAlive: true)
FirebaseFirestore firebaseFirestore(Ref ref) {
  return FirebaseFirestore.instance;
}

@Riverpod(keepAlive: true)
FirebasePerformance firebasePerformance(Ref ref) {
  return FirebasePerformance.instance;
}
