import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

/// Build the final Deep Research prompt by injecting positive and negative
/// examples into the provided template.
///
/// Rules:
/// - Positive examples: state is high quality
/// - Negative examples: state is low quality
/// - Only include jokes where both setup and punchline are non-empty
/// - Each example is a single line: "{trimmed setup} {trimmed punchline}"
/// - Section headers are included only if the section has examples
/// - Placeholders: {positive_examples} and {negative_examples}
String composeDeepResearchPrompt({
  required List<Joke> jokes,
  required String template,
  required String topic,
}) {
  final positive = <String>[];
  final negative = <String>[];

  for (final joke in jokes) {
    final setup = joke.setupText.trim();
    final punchline = joke.punchlineText.trim();
    if (setup.isEmpty || punchline.isEmpty) continue;

    final state = joke.state;
    if (state?.isHighQuality ?? false) {
      positive.add('$setup $punchline');
    } else if (state?.isLowQuality ?? false) {
      negative.add('$setup $punchline');
    }
  }

  String positiveBlock = '';
  if (positive.isNotEmpty) {
    positiveBlock =
        """\
Here are some examples of good jokes. They may not all fit the criteria perfectly, but are considered witty and clever enough to be included:
${positive.join('\n')}
"""
            .trim();
  }

  String negativeBlock = '';
  if (negative.isNotEmpty) {
    negativeBlock =
        """\
Here are some examples of bad jokes that are NOT witty or clever, are too commonplace or predictable, contain negative imagery, conflicts, or sad emotions, sound unnatural, have ineffective puns, or other flaws that make them unacceptable:
${negative.join('\n')}
"""
            .trim();
  }

  return template
      .replaceAll('{topic}', topic.trim())
      .replaceAll('{positive_examples}', positiveBlock)
      .replaceAll('{negative_examples}', negativeBlock);
}
