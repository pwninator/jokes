import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class AdminFeedbackDetailsPage extends ConsumerStatefulWidget {
  final String feedbackId;

  const AdminFeedbackDetailsPage({super.key, required this.feedbackId});

  @override
  ConsumerState<AdminFeedbackDetailsPage> createState() =>
      _AdminFeedbackDetailsPageState();
}

class _AdminFeedbackDetailsPageState
    extends ConsumerState<AdminFeedbackDetailsPage> {
  final _messageController = TextEditingController();

  @override
  void initState() {
    super.initState();
    ref
        .read(feedbackRepositoryProvider)
        .updateLastAdminViewTime(widget.feedbackId);
  }

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  void _sendMessage() {
    if (_messageController.text.trim().isEmpty) {
      return;
    }
    final text = _messageController.text.trim();
    ref
        .read(feedbackRepositoryProvider)
        .addConversationMessage(widget.feedbackId, text, SpeakerType.admin);
    _messageController.clear();
  }

  @override
  Widget build(BuildContext context) {
    final feedbackAsync = ref.watch(feedbackProvider(widget.feedbackId));

    return Scaffold(
      appBar: const AppBarWidget(
        title: 'Feedback Details',
      ),
      body: feedbackAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(child: Text('Error: $err')),
        data: (feedback) {
          if (feedback == null) {
            return const Center(child: Text('Feedback not found.'));
          }
          return Column(
            children: [
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.all(8.0),
                  reverse: true,
                  itemCount: feedback.conversation.length,
                  itemBuilder: (context, index) {
                    final message =
                        feedback.conversation.reversed.toList()[index];
                    return Align(
                      alignment: (message.speaker == SpeakerType.admin)
                          ? Alignment.centerRight
                          : Alignment.centerLeft,
                      child: Card(
                        color: (message.speaker == SpeakerType.admin)
                            ? Theme.of(context).colorScheme.primaryContainer
                            : Theme.of(context).colorScheme.surfaceVariant,
                        child: Padding(
                          padding: const EdgeInsets.all(12.0),
                          child: Text(message.text),
                        ),
                      ),
                    );
                  },
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(8.0),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _messageController,
                        decoration: const InputDecoration(
                          hintText: 'Type your message...',
                          border: OutlineInputBorder(),
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.send),
                      onPressed: _sendMessage,
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
