import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';

/// Current strategy: Jokes with thumbs up > 0 and thumbs up > thumbs down
class ThumbsUpStrategy with JokeEligibilityHelpers implements JokeEligibilityStrategy {
  const ThumbsUpStrategy();

  @override
  String get name => 'thumbs_up';
  
  @override
  String get description => 'Jokes with more thumbs up than down';
  
  @override
  Future<List<Joke>> getEligibleJokes(List<Joke> allJokes, EligibilityContext context) async {
    return allJokes.where((joke) => 
      joke.numThumbsUp > 0 && 
      joke.numThumbsUp > joke.numThumbsDown &&
      !isJokeAlreadyScheduled(joke.id, context)
    ).toList();
  }
}

/// Strategy for highly rated jokes with configurable thresholds
class HighlyRatedStrategy with JokeEligibilityHelpers implements JokeEligibilityStrategy {
  final int minThumbsUp;
  final double minRatio;
  
  const HighlyRatedStrategy({this.minThumbsUp = 5, this.minRatio = 2.0});
  
  @override
  String get name => 'highly_rated_${minThumbsUp}_${minRatio.toStringAsFixed(1)}';
  
  @override
  String get description => 'Jokes with $minThumbsUp+ thumbs up and ${minRatio}x ratio';
  
  @override
  Future<List<Joke>> getEligibleJokes(List<Joke> allJokes, EligibilityContext context) async {
    return allJokes.where((joke) => 
      joke.numThumbsUp >= minThumbsUp &&
      (joke.numThumbsDown == 0 || joke.numThumbsUp / joke.numThumbsDown >= minRatio) &&
      !isJokeAlreadyScheduled(joke.id, context)
    ).toList();
  }
}

/// Flexible rule-based strategy for complex combinations
class RuleBasedStrategy with JokeEligibilityHelpers implements JokeEligibilityStrategy {
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
  Future<List<Joke>> getEligibleJokes(List<Joke> allJokes, EligibilityContext context) async {
    return allJokes.where((joke) => 
      rules.every((rule) => rule.evaluate(joke, context)) &&
      !isJokeAlreadyScheduled(joke.id, context)
    ).toList();
  }
}

// ============================================================================
// Individual Rules for Composition
// ============================================================================

/// Rule: Minimum number of thumbs up
class MinThumbsUpRule implements JokeEligibilityRule {
  final int minThumbsUp;
  
  const MinThumbsUpRule(this.minThumbsUp);
  
  @override
  String get name => 'min_thumbs_up_$minThumbsUp';
  
  @override
  String get description => 'At least $minThumbsUp thumbs up';
  
  @override
  bool evaluate(Joke joke, EligibilityContext context) {
    return joke.numThumbsUp >= minThumbsUp;
  }
}

/// Rule: Minimum thumbs up to thumbs down ratio
class ThumbsRatioRule implements JokeEligibilityRule {
  final double minRatio;
  
  const ThumbsRatioRule(this.minRatio);
  
  @override
  String get name => 'thumbs_ratio_${minRatio.toStringAsFixed(1)}';
  
  @override
  String get description => 'Thumbs up ratio of at least ${minRatio.toStringAsFixed(1)}:1';
  
  @override
  bool evaluate(Joke joke, EligibilityContext context) {
    return joke.numThumbsDown == 0 || 
           joke.numThumbsUp / joke.numThumbsDown >= minRatio;
  }
}

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

/// Rule: More thumbs up than thumbs down
class PositiveRatioRule implements JokeEligibilityRule {
  const PositiveRatioRule();

  @override
  String get name => 'positive_ratio';
  
  @override
  String get description => 'More thumbs up than thumbs down';
  
  @override
  bool evaluate(Joke joke, EligibilityContext context) {
    return joke.numThumbsUp > joke.numThumbsDown;
  }
}

/// Rule: Has any thumbs up
class AnyThumbsUpRule implements JokeEligibilityRule {
  const AnyThumbsUpRule();

  @override
  String get name => 'any_thumbs_up';
  
  @override
  String get description => 'Has at least one thumbs up';
  
  @override
  bool evaluate(Joke joke, EligibilityContext context) {
    return joke.numThumbsUp > 0;
  }
} 