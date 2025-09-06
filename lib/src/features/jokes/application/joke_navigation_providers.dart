import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Stores and exposes the last-known page index for a given viewer instance.
final jokeViewerPageIndexProvider = StateProvider.family<int, String>((
  ref,
  viewerId,
) {
  return 0;
});
