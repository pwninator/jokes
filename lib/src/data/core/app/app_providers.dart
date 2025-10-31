import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

/// Provider for the kDebugMode boolean
final debugModeProvider = Provider<bool>((ref) => kDebugMode);

/// Provider for the current time.
/// Defaults to DateTime.now() but can be overridden in tests.
final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);
