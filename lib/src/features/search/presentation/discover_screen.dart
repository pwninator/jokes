import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';

/// Temporary placeholder that forwards to the existing SearchScreen.
/// Stage 1 keeps behaviour identical while routing transitions to /discover.
class DiscoverScreen extends ConsumerWidget {
  const DiscoverScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const SearchScreen();
  }
}
