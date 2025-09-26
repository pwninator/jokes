import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';

enum FeedbackConversationRole { admin, user }

class FeedbackConversationScreen extends ConsumerStatefulWidget {
  const FeedbackConversationScreen._({
    super.key,
    required this.feedbackId,
    required this.role,
    this.title,
  });

  const FeedbackConversationScreen.admin({
    Key? key,
    required String feedbackId,
    String? title,
  }) : this._(
         key: key,
         feedbackId: feedbackId,
         role: FeedbackConversationRole.admin,
         title: title,
       );

  const FeedbackConversationScreen.user({
    Key? key,
    required String feedbackId,
    String? title,
  }) : this._(
         key: key,
         feedbackId: feedbackId,
         role: FeedbackConversationRole.user,
         title: title,
       );

  final String feedbackId;
  final FeedbackConversationRole role;
  final String? title;

  @override
  ConsumerState<FeedbackConversationScreen> createState() =>
      _FeedbackConversationScreenState();
}

class _FeedbackConversationScreenState
    extends ConsumerState<FeedbackConversationScreen> {
  final TextEditingController _composerController = TextEditingController();
  bool _sending = false;
  DateTime? _lastMarkedAdminMessage;
  late final StateController<bool> _keyboardResizeController;

  bool get _isAdmin => widget.role == FeedbackConversationRole.admin;

  @override
  void initState() {
    super.initState();
    _keyboardResizeController = ref.read(keyboardResizeProvider.notifier);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_keyboardResizeController.mounted) {
        _keyboardResizeController.state = true;
      }
      if (_isAdmin) {
        ref
            .read(feedbackRepositoryProvider)
            .updateLastAdminViewTime(widget.feedbackId);
      }
    });
  }

  @override
  void dispose() {
    Future.microtask(() {
      if (_keyboardResizeController.mounted) {
        _keyboardResizeController.state = false;
      }
    });
    _composerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final feedbackAsync = ref.watch(feedbackProvider(widget.feedbackId));

    return feedbackAsync.when(
      loading: () => Scaffold(
        appBar: AppBar(title: Text(_title)),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) => Scaffold(
        appBar: AppBar(title: Text(_title)),
        body: Center(child: Text('Error: ${_formatError(error)}')),
      ),
      data: (entry) {
        if (entry == null) {
          return Scaffold(
            appBar: AppBar(title: Text(_title)),
            body: const Center(child: Text('Feedback not found.')),
          );
        }

        if (!_isAdmin) {
          _maybeMarkConversationViewed(entry);
        }

        final resolvedTitle =
            widget.title ??
            (_isAdmin ? 'Feedback from ${entry.userId}' : 'Feedback');

        final content = Column(
          children: [
            Expanded(
              child: _ConversationList(entry: entry, isAdminView: _isAdmin),
            ),
            _ComposerRow(
              controller: _composerController,
              sending: _sending,
              onSend: _handleSend,
              isAdminView: _isAdmin,
            ),
          ],
        );

        return Scaffold(
          appBar: AppBar(title: Text(resolvedTitle)),
          body: SafeArea(child: content),
        );
      },
    );
  }

  String get _title =>
      widget.title ?? (_isAdmin ? 'Feedback Details' : 'Feedback');

  Future<void> _handleSend() async {
    final text = _composerController.text.trim();
    if (text.isEmpty) {
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    final errorColor = Theme.of(context).colorScheme.error;

    setState(() => _sending = true);

    try {
      final service = ref.read(feedbackServiceProvider);
      final speaker = _isAdmin ? SpeakerType.admin : SpeakerType.user;
      await service.addConversationMessage(widget.feedbackId, text, speaker);
      _composerController.clear();
    } catch (error) {
      AppLogger.warn('FEEDBACK_CONVERSATION send error: ');
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(
            content: const Text('Failed to send message'),
            backgroundColor: errorColor,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
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
          AppLogger.warn('FEEDBACK_CONVERSATION mark view error: ');
        });
  }

  String _formatError(Object error) {
    final message = error.toString();
    const prefix = 'Exception: ';
    if (message.startsWith(prefix)) {
      return message.substring(prefix.length);
    }
    return message;
  }
}

class _ConversationList extends StatelessWidget {
  const _ConversationList({required this.entry, required this.isAdminView});

  final FeedbackEntry entry;
  final bool isAdminView;

  @override
  Widget build(BuildContext context) {
    final messages = entry.conversation;
    final colorScheme = Theme.of(context).colorScheme;

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      reverse: true,
      itemCount: messages.length,
      itemBuilder: (context, index) {
        final message = messages[messages.length - 1 - index];
        final isSelf = isAdminView
            ? message.speaker == SpeakerType.admin
            : message.speaker == SpeakerType.user;

        final alignment = isSelf ? Alignment.centerRight : Alignment.centerLeft;
        final bubbleColor = isSelf
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
    );
  }
}

class _ComposerRow extends StatelessWidget {
  const _ComposerRow({
    required this.controller,
    required this.sending,
    required this.onSend,
    required this.isAdminView,
  });

  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;
  final bool isAdminView;

  @override
  Widget build(BuildContext context) {
    final buttonKey = isAdminView
        ? const Key('feedback_conversation-send-button-admin')
        : const Key('feedback_conversation-send-button-user');
    final fieldKey = isAdminView
        ? const Key('feedback_conversation-message-field-admin')
        : const Key('feedback_conversation-message-field-user');

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              key: fieldKey,
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
            key: buttonKey,
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
    );
  }
}
