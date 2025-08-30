import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategies.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_eligibility_strategy.dart';

/// Registry for managing and creating joke eligibility strategies
class JokeEligibilityStrategyRegistry {
  static final Map<String, JokeEligibilityStrategy> _strategies = {
    'approved': const ApprovedStrategy(),
    'highly_rated': const HighlyRatedStrategy(),
    'highly_rated_strict': const HighlyRatedStrategy(
      minThumbsUp: 10,
      minRatio: 3.0,
    ),
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

  /// Register a new strategy
  static void registerStrategy(String name, JokeEligibilityStrategy strategy) {
    _strategies[name] = strategy;
  }

  /// Check if a strategy exists
  static bool hasStrategy(String name) {
    return _strategies.containsKey(name);
  }

  /// Factory method for creating rule-based strategies
  static JokeEligibilityStrategy createRuleBased(
    List<JokeEligibilityRule> rules, {
    String? customName,
    String? customDescription,
  }) {
    final name = customName ?? 'custom_${rules.map((r) => r.name).join('_')}';
    final description =
        customDescription ??
        'Custom rules: ${rules.map((r) => r.description).join(', ')}';

    return RuleBasedStrategy(
      rules: rules,
      customName: name,
      customDescription: description,
    );
  }

  /// Factory method for creating common rule combinations
  static JokeEligibilityStrategy createCommonStrategy(String type) {
    switch (type) {
      case 'basic':
        return createRuleBased(
          [const AnyThumbsUpRule(), const PositiveRatioRule()],
          customName: 'basic',
          customDescription: 'Basic quality jokes',
        );

      case 'quality':
        return createRuleBased(
          [
            const MinThumbsUpRule(3),
            const ThumbsRatioRule(1.5),
            const HasImagesRule(),
          ],
          customName: 'quality',
          customDescription: 'Quality jokes with images',
        );

      case 'premium':
        return createRuleBased(
          [
            const MinThumbsUpRule(5),
            const ThumbsRatioRule(2.0),
            const HasImagesRule(),
          ],
          customName: 'premium',
          customDescription: 'Premium quality jokes',
        );

      default:
        return const ApprovedStrategy();
    }
  }

  /// Initialize default strategies
  static void initializeDefaultStrategies() {
    // Add common strategies to registry
    registerStrategy('basic', createCommonStrategy('basic'));
    registerStrategy('quality', createCommonStrategy('quality'));
    registerStrategy('premium', createCommonStrategy('premium'));
  }
}
