import 'package:flutter_riverpod/flutter_riverpod.dart';

/// A simple integer counter to invalidate dependents when app usage changes
final appUsageEventsProvider = StateProvider<int>((ref) => 0);
