import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

/// Context object for passing additional data to eligibility strategies
class EligibilityContext {
  final String scheduleId;
  final List<JokeScheduleBatch> existingBatches;
  final DateTime targetMonth;
  final Map<String, dynamic> additionalFilters;
  
  const EligibilityContext({
    required this.scheduleId,
    required this.existingBatches,
    required this.targetMonth,
    this.additionalFilters = const {},
  });
}

/// Base strategy interface for determining joke eligibility
abstract class JokeEligibilityStrategy {
  /// Unique identifier for this strategy
  String get name;
  
  /// Human-readable description of this strategy
  String get description;
  
  /// Get eligible jokes based on this strategy's criteria
  Future<List<Joke>> getEligibleJokes(List<Joke> allJokes, EligibilityContext context);
}

/// Mixin providing common functionality for eligibility strategies
mixin JokeEligibilityHelpers {
  /// Check if a joke is already scheduled in any month for this schedule
  bool isJokeAlreadyScheduled(String jokeId, EligibilityContext context) {
    for (final batch in context.existingBatches) {
      if (batch.jokes.values.any((joke) => joke.id == jokeId)) {
        return true;
      }
    }
    return false;
  }
}

/// Individual rule interface for fine-grained eligibility control
abstract class JokeEligibilityRule {
  /// Unique identifier for this rule
  String get name;
  
  /// Human-readable description of this rule
  String get description;
  
  /// Evaluate whether a joke meets this rule's criteria
  bool evaluate(Joke joke, EligibilityContext context);
} 