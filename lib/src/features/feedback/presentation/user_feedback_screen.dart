import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

class UserFeedbackScreen extends ConsumerStatefulWidget {
  const UserFeedbackScreen({super.key});

  @override
  ConsumerState<UserFeedbackScreen> createState() => _UserFeedbackScreenState();
}

class _UserFeedbackScreenState extends ConsumerState<UserFeedbackScreen> {
  final TextEditingController _initialMessageController =
      TextEditingController();
  final TextEditingController _composerController = TextEditingController();
  bool _submittingInitial = false;
  bool _sendingMessage = false;
  bool _hasMarkedPrompt = false;
  DateTime? _lastMarkedAdminMessage;
  ProviderSubscription<AsyncValue<List<FeedbackEntry>>>? _feedbackSubscription;
  late final StateController<bool> _keyboardResizeController;

  @override
  void initState() {
    super.initState();
    _keyboardResizeController = ref.read(keyboardResizeProvider.notifier);
    _feedbackSubscription = ref.listenManual<AsyncValue<List<FeedbackEntry>>>(
      userFeedbackProvider,
      (previous, next) => _processFeedbackEntries(next),
      fireImmediately: true,
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_keyboardResizeController.mounted) {
        _keyboardResizeController.state = true;
      }
      _handleScreenOpened();
    });
  }

  @override
  Widget build(BuildContext context) {
    final feedbackAsync = ref.watch(userFeedbackProvider);
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Feedback')),
      body: SafeArea(
        child: feedbackAsync.when(
          data: (entries) {
            final entry = entries.isNotEmpty ? entries.first : null;
            if (entry == null || entry.conversation.isEmpty) {
              return _InitialFeedbackView(
                controller: _initialMessageController,
                submitting: _submittingInitial,
                onSubmit: () => _handleInitialSubmit(context, user),
              );
            }
            return _ConversationView(
              entry: entry,
              controller: _composerController,
              sending: _sendingMessage,
              onSend: () => _handleSendMessage(context, entry.id),
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Text(
              'Something went wrong while loading feedback.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _feedbackSubscription?.close();
    Future.microtask(() {
      if (_keyboardResizeController.mounted) {
        _keyboardResizeController.state = false;
      }
    });
    _initialMessageController.dispose();
    _composerController.dispose();
    super.dispose();
  }

  Future<void> _handleScreenOpened() async {
    try {
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logFeedbackDialogShown();
    } catch (e) {
      AppLogger.warn('FEEDBACK_SCREEN analytics error: ');
    }
  }

  void _processFeedbackEntries(AsyncValue<List<FeedbackEntry>> value) {
    value.whenData((entries) {
      if (!_hasMarkedPrompt && entries.isEmpty) {
        _hasMarkedPrompt = true;
        _markPromptViewed();
      }

      final entry = entries.isNotEmpty ? entries.first : null;
      if (entry != null) {
        _maybeMarkConversationViewed(entry);
      }
    });
  }

  Future<void> _markPromptViewed() async {
    try {
      final promptStore = ref.read(feedbackPromptStateStoreProvider);
      await promptStore.markViewed();
      ref.read(appUsageEventsProvider.notifier).state++;
    } catch (e) {
      AppLogger.warn('FEEDBACK_SCREEN prompt store error: ');
    }
  }

  void _maybeMarkConversationViewed(FeedbackEntry entry) {
    final lastMessage = entry.lastMessage;
    if (lastMessage == null || lastMessage.speaker != SpeakerType.admin) {
      return;
    }

    if (_lastMarkedAdminMessage != null &&
        !_lastMarkedAdminMessage!.isBefore(lastMessage.timestamp)) {
      return;
    }

    final lastUserView = entry.lastUserViewTime;
    if (lastUserView != null && !lastUserView.isBefore(lastMessage.timestamp)) {
      return;
    }

    _lastMarkedAdminMessage = lastMessage.timestamp;

    ref
        .read(feedbackServiceProvider)
        .updateLastUserViewTime(entry.id)
        .catchError((error) {
          AppLogger.warn('FEEDBACK_SCREEN mark view error: ');
        });
  }

  Future<void> _handleInitialSubmit(BuildContext context, AppUser? user) async {
    final message = _initialMessageController.text.trim();
    if (message.isEmpty) {
      return;
    }

    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final successColor = Theme.of(context).colorScheme.primary;
    final errorColor = Theme.of(context).colorScheme.error;

    setState(() => _submittingInitial = true);

    try {
      final service = ref.read(feedbackServiceProvider);
      await service.submitFeedback(message, user);
      _initialMessageController.clear();
      if (!mounted) return;
      if (navigator.canPop()) {
        navigator.pop(true);
      } else {
        messenger.showSnackBar(
          SnackBar(
            content: const Text('Thanks for your feedback!'),
            backgroundColor: successColor,
          ),
        );
      }
    } catch (e) {
      AppLogger.warn('FEEDBACK_SCREEN submit error: ${e.toString()}');
      try {
        final analytics = ref.read(analyticsServiceProvider);
        analytics.logErrorFeedbackSubmit(
          errorMessage: 'feedback_submit_failed',
        );
      } catch (_) {}
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(
          content: const Text('Failed to submit feedback'),
          backgroundColor: errorColor,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _submittingInitial = false);
      }
    }
  }

  Future<void> _handleSendMessage(BuildContext context, String docId) async {
    final text = _composerController.text.trim();
    if (text.isEmpty) {
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    final errorColor = Theme.of(context).colorScheme.error;

    setState(() => _sendingMessage = true);

    try {
      final service = ref.read(feedbackServiceProvider);
      await service.addConversationMessage(docId, text, SpeakerType.user);
      _composerController.clear();
    } catch (e) {
      AppLogger.warn('FEEDBACK_SCREEN send message error: ${e.toString()}');
      try {
        final analytics = ref.read(analyticsServiceProvider);
        analytics.logErrorFeedbackSubmit(
          errorMessage: 'feedback_message_failed',
        );
      } catch (_) {}
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(
          content: const Text('Failed to send message'),
          backgroundColor: errorColor,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _sendingMessage = false);
      }
    }
  }
}

class _InitialFeedbackView extends StatelessWidget {
  const _InitialFeedbackView({
    required this.controller,
    required this.submitting,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool submitting;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Help Us Perfect the Recipe!',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          const Text(
            'Our mission is to brighten your day, one joke at a time. How are we doing?\n\n'
            "Whether you have a joke you'd like to submit, a feature request, found a pesky bug, or just want to say hello, "
            'we read every message and appreciate you helping us improve!',
          ),
          const SizedBox(height: 16),
          TextField(
            key: const Key('feedback_screen-initial-message-field'),
            controller: controller,
            autofocus: true,
            maxLines: 5,
            minLines: 3,
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              BouncingButton(
                buttonKey: const Key('feedback_screen-cancel-button'),
                isPositive: false,
                onPressed: submitting
                    ? null
                    : () {
                        if (Navigator.of(context).canPop()) {
                          Navigator.of(context).pop();
                        }
                      },
                child: const Text('Cancel'),
              ),
              const SizedBox(width: 12),
              BouncingButton(
                buttonKey: const Key('feedback_screen-submit-button'),
                isPositive: true,
                onPressed: submitting ? null : onSubmit,
                child: submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Submit'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ConversationView extends StatelessWidget {
  const _ConversationView({
    required this.entry,
    required this.controller,
    required this.sending,
    required this.onSend,
  });

  final FeedbackEntry entry;
  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final messages = entry.conversation;

    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            reverse: true,
            itemCount: messages.length,
            itemBuilder: (context, index) {
              final message = messages[messages.length - 1 - index];
              final isUser = message.speaker == SpeakerType.user;
              final alignment = isUser
                  ? Alignment.centerRight
                  : Alignment.centerLeft;
              final colorScheme = Theme.of(context).colorScheme;
              final bubbleColor = isUser
                  ? colorScheme.primaryContainer
                  : colorScheme.surfaceContainerHighest;

              return Align(
                alignment: alignment,
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 6),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: bubbleColor,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: SelectableText(message.text),
                ),
              );
            },
          ),
        ),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('feedback_screen-message-field'),
                  controller: controller,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.newline,
                  decoration: const InputDecoration(
                    hintText: 'Type your message...',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) {
                    if (!sending) onSend();
                  },
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                key: const Key('feedback_screen-send-button'),
                icon: sending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send),
                onPressed: sending ? null : onSend,
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
      ],
    );
  }
}
