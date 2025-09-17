import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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
    final message = Message(
      text: _messageController.text.trim(),
      timestamp: DateTime.now(),
      isFromAdmin: true,
    );
    ref.read(feedbackRepositoryProvider).addMessage(widget.feedbackId, message);
    _messageController.clear();
  }

  @override
  Widget build(BuildContext context) {
    final feedbackAsync = ref.watch(feedbackProvider(widget.feedbackId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Feedback Details'),
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
                  itemCount: feedback.messages.length,
                  itemBuilder: (context, index) {
                    final message = feedback.messages.reversed.toList()[index];
                    return Align(
                      alignment: message.isFromAdmin
                          ? Alignment.centerRight
                          : Alignment.centerLeft,
                      child: Card(
                        color: message.isFromAdmin
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
