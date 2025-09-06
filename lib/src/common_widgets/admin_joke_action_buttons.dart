import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

class AdminPopulateJokeButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminPopulateJokeButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
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
      color: Colors.red,
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
      color: theme.colorScheme.secondary,
    );
  }
}

class AdminRegenerateImagesButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminRegenerateImagesButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
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
      color: theme.colorScheme.secondary,
    );
  }
}

class AdminPublishJokeButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminPublishJokeButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('publish-joke-button'),
      icon: Icons.public,
      holdCompleteIcon: Icons.check_circle,
      onTap: () {
        // No-op on tap
      },
      onHoldComplete: () async {
        final scheduleService = ref.read(jokeScheduleAutoFillServiceProvider);
        await scheduleService.publishJokeImmediately(jokeId);
      },
      isLoading: isLoading,
      theme: theme,
      color: Colors.green,
    );
  }
}

class AdminUnpublishJokeButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminUnpublishJokeButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('unpublish-joke-button'),
      icon: Icons.public_off,
      holdCompleteIcon: Icons.undo,
      onTap: () {
        // No-op on tap
      },
      onHoldComplete: () async {
        final scheduleService = ref.read(jokeScheduleAutoFillServiceProvider);
        await scheduleService.unpublishJoke(jokeId);
      },
      isLoading: isLoading,
      theme: theme,
      color: Colors.orange,
    );
  }
}

class AdminAddToDailyScheduleButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminAddToDailyScheduleButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('add-to-daily-schedule-button'),
      icon: Icons.calendar_month,
      holdCompleteIcon: Icons.check_circle,
      onTap: () {
        // No-op on tap
      },
      onHoldComplete: () async {
        final scheduleService = ref.read(jokeScheduleAutoFillServiceProvider);
        await scheduleService.addJokeToNextAvailableSchedule(jokeId);
      },
      isLoading: isLoading,
      theme: theme,
      color: Colors.purple,
    );
  }
}

class AdminRemoveFromDailyScheduleButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;

  const AdminRemoveFromDailyScheduleButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('remove-from-daily-schedule-button'),
      icon: Icons.event_busy,
      holdCompleteIcon: Icons.undo,
      onTap: () {
        // No-op on tap
      },
      onHoldComplete: () async {
        final scheduleService = ref.read(jokeScheduleAutoFillServiceProvider);
        await scheduleService.removeJokeFromDailySchedule(jokeId);
      },
      isLoading: isLoading,
      theme: theme,
      color: Colors.orange,
    );
  }
}
