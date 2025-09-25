import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart'
    show SearchLabel;
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart'
    show MatchMode;

class JokeConstants {
  JokeConstants._();

  static const String defaultJokeScheduleId = 'daily_jokes';
  static const int subscriptionPromptJokesViewedThreshold = 5;

  // Search constants
  static const String searchQueryPrefix = 'jokes about ';
  static const int userSearchMaxResults = 20;
  static const bool userSearchPublicOnly = true;
  static const MatchMode userSearchMatchMode = MatchMode.tight;
  static const SearchLabel userSearchLabel = SearchLabel.none;
  static const SearchLabel similarJokesLabel = SearchLabel.similar;

  static const int adminSearchMaxResults = 50;
  static const bool adminSearchPublicOnly = false;
  static const MatchMode adminSearchMatchMode = MatchMode.loose;
  static const SearchLabel adminSearchLabel = SearchLabel.none;
}
