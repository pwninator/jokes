import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

/// Strategy: Jokes explicitly approved by admins/state
class ApprovedStrategy
    with JokeEligibilityHelpers
    implements JokeEligibilityStrategy {
  const ApprovedStrategy();

  @override
  String get name => 'approved';

  @override
  String get description => 'Jokes with state APPROVED';

  @override
  Future<List<Joke>> getEligibleJokes(
    List<Joke> allJokes,
    EligibilityContext context,
  ) async {
    return allJokes
        .where(
          (joke) =>
              joke.state == JokeState.approved &&
              !isJokeAlreadyScheduled(joke.id, context),
        )
        .toList();
  }
}

/// Flexible rule-based strategy for complex combinations
class RuleBasedStrategy
    with JokeEligibilityHelpers
    implements JokeEligibilityStrategy {
  final List<JokeEligibilityRule> rules;
  final String customName;
  final String customDescription;

  const RuleBasedStrategy({
    required this.rules,
    required this.customName,
    required this.customDescription,
  });

  @override
  String get name => customName;

  @override
  String get description => customDescription;

  @override
  Future<List<Joke>> getEligibleJokes(
    List<Joke> allJokes,
    EligibilityContext context,
  ) async {
    return allJokes
        .where(
          (joke) =>
              rules.every((rule) => rule.evaluate(joke, context)) &&
              !isJokeAlreadyScheduled(joke.id, context),
        )
        .toList();
  }
}

// ============================================================================
// Individual Rules for Composition
// ============================================================================

/// Rule: Must have both setup and punchline images
class HasImagesRule implements JokeEligibilityRule {
  const HasImagesRule();

  @override
  String get name => 'has_images';

  @override
  String get description => 'Has both setup and punchline images';

  @override
  bool evaluate(Joke joke, EligibilityContext context) {
    return joke.setupImageUrl != null &&
        joke.setupImageUrl!.trim().isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.trim().isNotEmpty;
  }
}
