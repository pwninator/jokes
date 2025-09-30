import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/features/admin/application/deep_research_composer.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart'
    show MatchMode;

/// Dummy template with placeholders; replace later
const String kDeepResearchPromptTemplate = """\
Search the internet to compile the best, funniest, most clever and witty punny jokes for this topic: "{topic}". Each joke should be a 2 liner with a setup and punchline, and must contain at least one pun.

Criteria for high quality punny jokes:
  * The punchline is grammatically correct AND makes sense in the context of the joke for BOTH meanings of the pun word.
    * Positive example: "What do you call an aquarium event with only one animal on display? A single porpoise exhibit!" This joke is excellent because "a single purpose exhibit" (its sole purpose is to show the porpoise) and "a single porpoise exhibit" (it only has one porpoise) both make sense within the context of the joke. 
    * Negative example: "What did the wise dolphin say to the fish? You must find your porpoise in life!" This joke is just ok because while "find your purpose in life" makes sense, telling a fish to "find your porpoise in life" does not make sense. The joke's setup does not give the fish any reason to look for a porpoise.
  * If the joke incorporates some well known attribute or behavior of the animal, that's even better
  * The joke should wholesome, positive, and evoke a silly, charming, and fun mental picture. It must contain NO negative imagery, conflicts, or sad emotions.
  * The joke should sound smooth, casual, and natural.
  * Puns that use real words are usually preferable over made up words
  * All jokes should be appropriate for all ages, and should not involve political, religious, inappropriate, or other controversial topics.
  * Sufficiently different from the examples provided.

{positive_examples}

{negative_examples}

Find the top new 20 jokes for the given topic that best fit the above criteria. All new jokes MUST be sufficiently different from the examples provided. If you find a joke that is witty and clever but fails some of the criteria above in a way that is fixable, you can edit the pun to improve it. For example, if a pun is clever and witty but the joke is adult themed, you can change it to a child friendly version of the joke that uses the same pun instead.
""";

const String kResponsePromptTemplate = """\
List each of the jokes you found on a separate line, with the setup and punchlines separated by "###" (3 hashes). ONLY include the setup line, punchline, and separator "###", NOTHING ELSE (e.g. no comments, citations, links, etc.)

Example:
What do you call an aquarium event with only one animal on display?###A single porpoise exhibit!
What is the salad green's friendship pledge?###Lettuce always stick together!
What did the dog say to the tree?###Bark!
""";

class DeepResearchScreen extends ConsumerStatefulWidget {
  const DeepResearchScreen({super.key});

  @override
  ConsumerState<DeepResearchScreen> createState() => _DeepResearchScreenState();
}

class _DeepResearchScreenState extends ConsumerState<DeepResearchScreen> {
  final TextEditingController _topicController = TextEditingController();
  final TextEditingController _responseController = TextEditingController();
  String? _composedPrompt;
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _topicController.dispose();
    _responseController.dispose();
    super.dispose();
  }

  Future<void> _createPrompt() async {
    final topic = _topicController.text.trim();
    if (topic.isEmpty) {
      setState(() {
        _error = 'Please enter a joke topic';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _composedPrompt = null;
    });

    try {
      // Trigger search
      final current = ref.read(
        searchQueryProvider(SearchScope.jokeDeepResearch),
      );
      ref
          .read(searchQueryProvider(SearchScope.jokeDeepResearch).notifier)
          .state = current.copyWith(
        query: topic,
        maxResults: 100,
        publicOnly: false,
        matchMode: MatchMode.tight,
        logTrace: false,
      );

      // Await the ids result
      final ids = await ref.read(
        searchResultIdsProvider(SearchScope.jokeDeepResearch).future,
      );
      if (!mounted) return;

      // Determine jokes to use for prompt composition
      final List<Joke> jokes;
      if (ids.isEmpty) {
        jokes = const [];
      } else {
        // Fetch jokes by ids directly to avoid relying on stream timing in tests
        final repo = ref.read(jokeRepositoryProvider);
        jokes = await repo.getJokesByIds(ids.map((e) => e.id).toList());
      }

      setState(() {
        _composedPrompt = composeDeepResearchPrompt(
          jokes: jokes,
          template: kDeepResearchPromptTemplate,
          topic: topic,
        );
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to create prompt: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _copyToClipboard() async {
    final text = _composedPrompt;
    if (text == null || text.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Prompt copied to clipboard')));
  }

  Future<void> _copyFormatPrompt() async {
    await Clipboard.setData(const ClipboardData(text: kResponsePromptTemplate));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Formatting prompt copied to clipboard')),
    );
  }

  // Parse pasted text into list of (setup, punchline) pairs
  // Expected format: one joke per line as "<setup>###<punchline>"
  List<({String setup, String punchline})> _parsePastedJokes(String raw) {
    if (raw.trim().isEmpty) return const [];

    final text = raw.replaceAll('\r\n', '\n').trim();
    final lines = text
        .split('\n')
        .map((l) => l.trim())
        .where((l) => l.isNotEmpty)
        .toList();

    final parsed = <({String setup, String punchline})>[];
    for (final line in lines) {
      final idx = line.indexOf('###');
      if (idx <= 0 || idx >= line.length - 3) {
        continue; // skip lines without proper delimiter
      }
      final setup = line
          .substring(0, idx)
          .trim()
          .replaceAll(RegExp(r'\.+$'), '');
      final punchline = line
          .substring(idx + 3)
          .trim()
          .replaceAll(RegExp(r'\.+$'), '');
      if (setup.isEmpty || punchline.isEmpty) continue;
      parsed.add((setup: setup, punchline: punchline));
    }
    return parsed;
  }

  Future<void> _onSubmitPressed() async {
    final pasted = _responseController.text;
    final jokes = _parsePastedJokes(pasted);
    if (jokes.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('No jokes found to submit')));
      return;
    }

    await _showConfirmDialog(jokes);
  }

  Future<void> _showConfirmDialog(
    List<({String setup, String punchline})> jokes,
  ) async {
    if (!mounted) return;

    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return _CreateJokesDialog(
          jokes: jokes,
          onAllDone: () {
            if (!mounted) return;
            setState(() {
              _topicController.clear();
              _responseController.clear();
            });
          },
          ref: ref,
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return AdaptiveAppBarScreen(
      title: 'Deep Research',
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: SingleChildScrollView(
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextFormField(
                controller: _topicController,
                decoration: const InputDecoration(
                  labelText: 'joke topic',
                  border: OutlineInputBorder(),
                ),
                onFieldSubmitted: (_) => _createPrompt(),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  ElevatedButton(
                    onPressed: _isLoading ? null : _createPrompt,
                    child: const Text('Create prompt'),
                  ),
                  const SizedBox(width: 12),
                  if (_composedPrompt != null && _composedPrompt!.isNotEmpty)
                    OutlinedButton.icon(
                      onPressed: _copyToClipboard,
                      icon: const Icon(Icons.copy),
                      label: const Text('Copy'),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              if (_isLoading) const LinearProgressIndicator(),
              if (_error != null) ...[
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
                const SizedBox(height: 8),
              ],
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 80),
                child: SingleChildScrollView(
                  child: _composedPrompt == null || _composedPrompt!.isEmpty
                      ? const Text('')
                      : SelectableText(_composedPrompt!),
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _responseController,
                minLines: 3,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Paste LLM response here',
                  border: OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  ElevatedButton(
                    onPressed: _onSubmitPressed,
                    child: const Text('Submit'),
                  ),
                  const SizedBox(width: 12),
                  OutlinedButton.icon(
                    onPressed: _copyFormatPrompt,
                    icon: const Icon(Icons.copy_all),
                    label: const Text('Copy Response Prompt'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CreateJokesDialog extends StatefulWidget {
  final List<({String setup, String punchline})> jokes;
  final VoidCallback onAllDone;
  final WidgetRef ref;
  const _CreateJokesDialog({
    required this.jokes,
    required this.onAllDone,
    required this.ref,
  });

  @override
  State<_CreateJokesDialog> createState() => _CreateJokesDialogState();
}

class _CreateJokesDialogState extends State<_CreateJokesDialog> {
  late final List<bool> _created;
  bool _isRunning = false;

  @override
  void initState() {
    super.initState();
    _created = List<bool>.filled(widget.jokes.length, false);
  }

  Future<void> _runCreation() async {
    if (_isRunning) return;
    setState(() {
      _isRunning = true;
    });
    final service = widget.ref.read(jokeCloudFunctionServiceProvider);
    for (int i = 0; i < widget.jokes.length; i++) {
      final j = widget.jokes[i];
      try {
        await service.createJokeWithResponse(
          setupText: j.setup,
          punchlineText: j.punchline,
          adminOwned: true,
        );
        setState(() {
          _created[i] = true;
        });
      } catch (_) {
        // Leave as false on failure; continue
      }
    }

    if (!mounted) return;
    Navigator.of(context).pop();
    widget.onAllDone();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Confirm jokes to create'),
      content: SizedBox(
        width: 600,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 400),
          child: Scrollbar(
            child: ListView.builder(
              itemCount: widget.jokes.length,
              itemBuilder: (context, index) {
                final j = widget.jokes[index];
                final isDone = _created[index];
                return ListTile(
                  dense: true,
                  leading: isDone
                      ? const Icon(Icons.check_circle, color: Colors.green)
                      : const Icon(Icons.radio_button_unchecked),
                  title: Text(j.setup),
                  subtitle: Text(j.punchline),
                );
              },
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _isRunning
              ? null
              : () {
                  Navigator.of(context).pop();
                },
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isRunning ? null : _runCreation,
          child: const Text('Confirm'),
        ),
      ],
    );
  }
}
