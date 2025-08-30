import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

class AdminPopulateJokeButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;
  final Duration holdDuration;

  const AdminPopulateJokeButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
    this.holdDuration = const Duration(seconds: 3),
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('populate-joke-button'),
      icon: Icons.auto_awesome,
      holdCompleteIcon: Icons.refresh,
      onTap: () async {
        final notifier = ref.read(jokePopulationProvider.notifier);
        await notifier.populateJoke(jokeId, imagesOnly: false);
      },
      onHoldComplete: () async {
        final notifier = ref.read(jokePopulationProvider.notifier);
        await notifier.populateJoke(jokeId, imagesOnly: false);
      },
      isLoading: isLoading,
      theme: theme,
      color: theme.colorScheme.secondaryContainer,
      holdDuration: holdDuration,
    );
  }
}

class AdminDeleteJokeButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;
  final Duration holdDuration;

  const AdminDeleteJokeButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
    this.holdDuration = const Duration(seconds: 3),
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('delete-joke-button'),
      icon: Icons.delete,
      holdCompleteIcon: Icons.delete_forever,
      onTap: () {
        // No-op on tap
      },
      onHoldComplete: () async {
        final repository = ref.read(jokeRepositoryProvider);
        await repository.deleteJoke(jokeId);
      },
      isLoading: isLoading,
      theme: theme,
      color: theme.colorScheme.error,
      holdDuration: holdDuration,
    );
  }
}

class AdminEditJokeButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminEditJokeButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('edit-joke-button'),
      icon: Icons.edit,
      holdCompleteIcon: Icons.refresh,
      onTap: () {
        context.pushNamed(
          RouteNames.adminEditorWithJoke,
          pathParameters: {'jokeId': jokeId},
        );
      },
      onHoldComplete: () async {
        final notifier = ref.read(jokePopulationProvider.notifier);
        await notifier.populateJoke(jokeId, imagesOnly: false);
      },
      isLoading: isLoading,
      theme: theme,
      color: theme.colorScheme.tertiaryContainer,
    );
  }
}

class AdminRegenerateImagesButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;
  final Duration holdDuration;

  const AdminRegenerateImagesButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
    this.holdDuration = const Duration(seconds: 3),
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('regenerate-images-button'),
      icon: Icons.image,
      holdCompleteIcon: Icons.refresh,
      onTap: () async {
        final notifier = ref.read(jokePopulationProvider.notifier);
        await notifier.populateJoke(
          jokeId,
          imagesOnly: true,
          additionalParams: {"image_quality": "medium"},
        );
      },
      onHoldComplete: () async {
        final notifier = ref.read(jokePopulationProvider.notifier);
        await notifier.populateJoke(
          jokeId,
          imagesOnly: true,
          additionalParams: {"image_quality": "high"},
        );
      },
      isLoading: isLoading,
      theme: theme,
      color: theme.colorScheme.secondaryContainer,
      holdDuration: holdDuration,
    );
  }
}
