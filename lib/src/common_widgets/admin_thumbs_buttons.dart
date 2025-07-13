import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_admin_thumbs_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

/// Provider for getting admin rating for a joke
final jokeAdminRatingProvider = FutureProvider.autoDispose
    .family<JokeAdminRating?, String>((ref, jokeId) async {
      final service = ref.watch(jokeAdminThumbsServiceProvider);
      return service.getAdminRating(jokeId);
    });

/// Paired thumbs up/down buttons for admin users
/// Handles mutually exclusive behavior where only one can be active at a time
class AdminThumbsButtons extends ConsumerWidget {
  final String jokeId;
  final double size;

  const AdminThumbsButtons({super.key, required this.jokeId, this.size = 24.0});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ratingAsync = ref.watch(jokeAdminRatingProvider(jokeId));

    return ratingAsync.when(
      data: (rating) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildThumbButton(
            context: context,
            ref: ref,
            icon: Icons.thumb_up,
            isActive: rating == JokeAdminRating.approved,
            onTap: () async {
              final service = ref.read(jokeAdminThumbsServiceProvider);
              await service.toggleThumbsUp(jokeId);
              ref.invalidate(jokeAdminRatingProvider(jokeId));
            },
          ),
          const SizedBox(width: 8),
          _buildThumbButton(
            context: context,
            ref: ref,
            icon: Icons.thumb_down,
            isActive: rating == JokeAdminRating.rejected,
            onTap: () async {
              final service = ref.read(jokeAdminThumbsServiceProvider);
              await service.toggleThumbsDown(jokeId);
              ref.invalidate(jokeAdminRatingProvider(jokeId));
            },
          ),
        ],
      ),
      loading: () => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildLoadingButton(),
          const SizedBox(width: 8),
          _buildLoadingButton(),
        ],
      ),
      error: (error, stack) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildErrorButton(Icons.thumb_up),
          const SizedBox(width: 8),
          _buildErrorButton(Icons.thumb_down),
        ],
      ),
    );
  }

  Widget _buildThumbButton({
    required BuildContext context,
    required WidgetRef ref,
    required IconData icon,
    required bool isActive,
    required VoidCallback onTap,
  }) {
    final color = isActive
        ? (icon == Icons.thumb_up ? Colors.green : Colors.red)
        : Colors.grey.shade600;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: size + 16,
        height: size + 16,
        child: Center(
          child: Icon(icon, size: size, color: color),
        ),
      ),
    );
  }

  Widget _buildLoadingButton() {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      width: size + 16,
      height: size + 16,
      child: Center(
        child: SizedBox(
          width: size * 0.7,
          height: size * 0.7,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: Colors.grey.shade600,
          ),
        ),
      ),
    );
  }

  Widget _buildErrorButton(IconData icon) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      width: size + 16,
      height: size + 16,
      child: Center(
        child: Icon(icon, size: size, color: Colors.grey.shade600),
      ),
    );
  }
}
