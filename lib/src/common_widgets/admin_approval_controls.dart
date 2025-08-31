import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/admin_review_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

const IconData kApprovedIcon = Icons.check;
const IconData kRejectedIcon = Icons.close;
const IconData kUnreviewedIcon = Icons.help;

/// Non-interactive icon for non-mutable states
Widget _staticIconForRating(JokeAdminRating rating, {required double size}) {
  switch (rating) {
    case JokeAdminRating.approved:
      return Icon(
        kApprovedIcon,
        size: size,
        color: Colors.green.withValues(alpha: 0.7),
      );
    case JokeAdminRating.rejected:
      return Icon(
        kRejectedIcon,
        size: size,
        color: Colors.red.withValues(alpha: 0.7),
      );
    case JokeAdminRating.unreviewed:
      return Icon(
        kUnreviewedIcon,
        size: size,
        color: Colors.red, // solid 100% alpha
      );
  }
}

/// Paired approval/rejection controls for admin users
/// - If state is mutable (APPROVED/REJECTED/UNREVIEWED): show two toggles
/// - Otherwise: show a single static icon for current rating (non-interactive)
class AdminApprovalControls extends ConsumerWidget {
  final String jokeId;
  final double size;

  const AdminApprovalControls({
    super.key,
    required this.jokeId,
    this.size = 24.0,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final jokeAsync = ref.watch(jokeByIdProvider(jokeId));

    return jokeAsync.when(
      data: (joke) {
        final rating = joke?.adminRating ?? JokeAdminRating.unreviewed;
        final state = joke?.state;
        final isMutable = state?.canMutateAdminRating ?? false;

        if (!isMutable) {
          return _staticIconForRating(rating, size: size);
        }

        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildAdminRatingButton(
              context: context,
              ref: ref,
              icon: kApprovedIcon,
              isActive: rating == JokeAdminRating.approved,
              onTap: () async {
                final service = ref.read(adminReviewServiceProvider);
                await service.toggleApprove(jokeId);
              },
            ),
            const SizedBox(width: 8),
            _buildAdminRatingButton(
              context: context,
              ref: ref,
              icon: kRejectedIcon,
              isActive: rating == JokeAdminRating.rejected,
              onTap: () async {
                final service = ref.read(adminReviewServiceProvider);
                await service.toggleReject(jokeId);
              },
            ),
          ],
        );
      },
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
          _buildErrorButton(kApprovedIcon),
          const SizedBox(width: 8),
          _buildErrorButton(kRejectedIcon),
        ],
      ),
    );
  }

  Widget _buildAdminRatingButton({
    required BuildContext context,
    required WidgetRef ref,
    required IconData icon,
    required bool isActive,
    required VoidCallback onTap,
  }) {
    final color = isActive
        ? (icon == kApprovedIcon ? Colors.green : Colors.red)
        : Colors.grey.shade600;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: isActive ? color.withValues(alpha: 0.4) : Colors.transparent,
          border: Border.all(color: color, width: 1.0),
          shape: BoxShape.circle,
        ),
        child: Center(
          child: Icon(icon, size: size * 0.7, color: color),
        ),
      ),
    );
  }

  Widget _buildLoadingButton() {
    return SizedBox(
      width: size,
      height: size,
      child: CircularProgressIndicator(
        strokeWidth: 2,
        color: Colors.grey.shade600,
      ),
    );
  }

  Widget _buildErrorButton(IconData icon) {
    return SizedBox(
      width: size,
      height: size,
      child: Center(
        child: Icon(icon, size: size, color: Colors.grey.shade600),
      ),
    );
  }
}
