import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/common_widgets/modify_image_dialog.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_modification_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
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
        await notifier.populateJoke(jokeId, imageQuality: 'low');
      },
      onHoldComplete: () async {
        final notifier = ref.read(jokePopulationProvider.notifier);
        await notifier.populateJoke(jokeId, imageQuality: 'medium');
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
        await notifier.populateJoke(jokeId, imageQuality: 'medium');
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
  final bool hasUpscaledImage;

  const AdminRegenerateImagesButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
    this.hasUpscaledImage = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return HoldableButton(
      key: const Key('regenerate-images-button'),
      icon: Icons.image,
      holdCompleteIcon: Icons.refresh,
      onTap: () async {
        _showImageQualityDialog(context, ref);
      },
      onHoldComplete: () {},
      isLoading: isLoading,
      theme: theme,
      color: theme.colorScheme.secondary,
      borderColor: hasUpscaledImage ? Colors.amber : null,
      borderWidth: hasUpscaledImage ? 2.0 : 0.0,
    );
  }

  void _showImageQualityDialog(BuildContext context, WidgetRef ref) {
    final qualityOptions = [
      'low_mini',
      'medium_mini',
      'high_mini',
      'low',
      'medium',
      'high',
      'low_15',
      'medium_15',
      'high_15',
    ];

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Select Image Quality'),
          content: SizedBox(
            width: double.maxFinite,
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: qualityOptions.length,
              itemBuilder: (context, index) {
                final quality = qualityOptions[index];
                return ListTile(
                  key: Key('image-quality-option-$quality'),
                  title: Text(quality),
                  onTap: () async {
                    Navigator.of(context).pop();
                    final notifier = ref.read(jokePopulationProvider.notifier);
                    await notifier.regenerateImagesViaCreationProcess(
                      jokeId,
                      imageQuality: quality,
                    );
                  },
                );
              },
            ),
          ),
          actions: [
            TextButton(
              key: const Key('cancel-image-quality-dialog'),
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
          ],
        );
      },
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
      holdDuration: const Duration(seconds: 1),
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
      holdDuration: const Duration(seconds: 1),
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

class AdminModifyImageButton extends ConsumerWidget {
  final String jokeId;
  final ThemeData theme;
  final bool isLoading;
  final String? setupImageUrl;
  final String? punchlineImageUrl;
  final bool hasUpscaledImage;

  const AdminModifyImageButton({
    super.key,
    required this.jokeId,
    required this.theme,
    required this.isLoading,
    this.setupImageUrl,
    this.punchlineImageUrl,
    this.hasUpscaledImage = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final modificationState = ref.watch(jokeModificationProvider);
    final isModifying = modificationState.modifyingJokes.contains(jokeId);

    return HoldableButton(
      key: const Key('modify-image-button'),
      icon: Icons.edit_note,
      holdCompleteIcon: Icons.edit_note,
      onTap: () {
        _showModifyImageDialog(context, ref);
      },
      onHoldComplete: () {
        final notifier = ref.read(jokeModificationProvider.notifier);
        notifier.upscaleJoke(jokeId);
      },
      isLoading: isLoading || isModifying,
      theme: theme,
      color: theme.colorScheme.tertiary,
      borderColor: hasUpscaledImage ? Colors.amber : null,
      borderWidth: hasUpscaledImage ? 2.0 : 0.0,
    );
  }

  void _showModifyImageDialog(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (context) => ModifyImageDialog(
        jokeId: jokeId,
        setupImageUrl: setupImageUrl,
        punchlineImageUrl: punchlineImageUrl,
      ),
    );
  }
}
