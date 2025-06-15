import 'package:flutter_riverpod/flutter_riverpod.dart'; // Changed from riverpod_annotation

// part 'counter_provider.g.dart'; // Not needed for manual provider

// @riverpod // Not needed for manual provider
// class Counter extends _$Counter {
//   @override
//   int build() => 0; // Initial state for the counter

//   void increment() => state++;
// }

final counterProvider = StateProvider<int>((ref) => 0);
