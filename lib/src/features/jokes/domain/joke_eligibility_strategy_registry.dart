import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategies.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';

/// Registry for managing and creating joke eligibility strategies
class JokeEligibilityStrategyRegistry {
  static final Map<String, JokeEligibilityStrategy> _strategies = {
    'approved': const ApprovedStrategy(),
  };

  /// Get a strategy by name, returns default if not found
  static JokeEligibilityStrategy getStrategy(String name) {
    return _strategies[name] ?? const ApprovedStrategy();
  }

  /// Get all available strategies
  static List<JokeEligibilityStrategy> getAllStrategies() {
    return _strategies.values.toList();
  }

  /// Get all strategy names
  static List<String> getAllStrategyNames() {
    return _strategies.keys.toList();
  }

  /// Check if a strategy exists
  static bool hasStrategy(String name) {
    return _strategies.containsKey(name);
  }
}
