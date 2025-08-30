import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/features/admin/application/deep_research_composer.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart'
    show MatchMode;

/// Dummy template with placeholders; replace later
const String kDeepResearchTemplate = """\
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

class DeepResearchScreen extends ConsumerStatefulWidget {
  const DeepResearchScreen({super.key});

  @override
  ConsumerState<DeepResearchScreen> createState() => _DeepResearchScreenState();
}

class _DeepResearchScreenState extends ConsumerState<DeepResearchScreen> {
  final TextEditingController _topicController = TextEditingController();
  String? _composedPrompt;
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _topicController.dispose();
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
        searchQueryProvider(SearchScope.jokeManagementSearch),
      );
      ref
          .read(searchQueryProvider(SearchScope.jokeManagementSearch).notifier)
          .state = current.copyWith(
        query: topic,
        maxResults: 100,
        publicOnly: false,
        matchMode: MatchMode.tight,
      );

      // Await the ids result
      final ids = await ref.read(
        searchResultIdsProvider(SearchScope.jokeManagementSearch).future,
      );
      if (!mounted) return;

      if (ids.isEmpty) {
        setState(() {
          _composedPrompt = composeDeepResearchPrompt(
            jokes: const [],
            template: kDeepResearchTemplate,
            topic: topic,
          );
          _isLoading = false;
        });
        return;
      }

      // Fetch jokes by ids directly to avoid relying on stream timing in tests
      final repo = ref.read(jokeRepositoryProvider);
      final jokes = await repo.getJokesByIds(ids.map((e) => e.id).toList());

      setState(() {
        _composedPrompt = composeDeepResearchPrompt(
          jokes: jokes,
          template: kDeepResearchTemplate,
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

  @override
  Widget build(BuildContext context) {
    return AdaptiveAppBarScreen(
      title: 'Deep Research',
      body: Padding(
        padding: const EdgeInsets.all(16.0),
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
            Expanded(
              child: SingleChildScrollView(
                child: _composedPrompt == null || _composedPrompt!.isEmpty
                    ? const Text('')
                    : SelectableText(_composedPrompt!),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
