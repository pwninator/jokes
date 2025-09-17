import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class FeedbackDetailsScreen extends ConsumerStatefulWidget {
  const FeedbackDetailsScreen({
    super.key,
    required this.feedback,
  });

  final FeedbackEntry feedback;

  @override
  ConsumerState<ConsumerStatefulWidget> createState() =>
      _FeedbackDetailsScreenState();
}

class _FeedbackDetailsScreenState extends ConsumerState<FeedbackDetailsScreen> {
  final _textController = TextEditingController();
  bool _isSending = false;

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  Future<void> _sendMessage() async {
    if (_textController.text.isEmpty) {
      return;
    }
    setState(() {
      _isSending = true;
    });

    try {
      await ref.read(feedbackServiceProvider).addConversationMessage(
            widget.feedback.id,
            _textController.text,
            'ADMIN',
          );
      _textController.clear();
    } catch (e) {
      // TODO: show error
    } finally {
      if (mounted) {
        setState(() {
          _isSending = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final feedback = widget.feedback;
    return Scaffold(
      appBar: AppBar(
        title: Text('Feedback from ${feedback.userId}'),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(8),
              itemCount: feedback.conversation.length,
              itemBuilder: (context, index) {
                final message = feedback.conversation[index];
                final isUser = message.speaker == 'USER';
                return Align(
                  alignment:
                      isUser ? Alignment.centerLeft : Alignment.centerRight,
                  child: Card(
                    color: isUser
                        ? Theme.of(context).colorScheme.surfaceVariant
                        : Theme.of(context).colorScheme.primaryContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            message.text,
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${message.speaker} - ${message.timestamp}',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
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
                    controller: _textController,
                    decoration: const InputDecoration(
                      hintText: 'Type your reply...',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send),
                  onPressed: _isSending ? null : _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
