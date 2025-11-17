import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart'
    show SearchLabel;
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart'
    show MatchMode;

class JokeConstants {
  JokeConstants._();

  // Settings keys
  static const String compositeJokeCursorPrefsKey = 'composite_joke_cursor';

  static const String iconCookie01TransparentDark300 =
      'assets/images/icon_cookie_01_transparent_dark2_300.png';

  static const String defaultJokeScheduleId = 'daily_jokes';
  static const int subscriptionPromptJokesViewedThreshold = 5;

  // Search constants
  static const String searchQueryPrefix = 'jokes about ';
  static const int userSearchMaxResults = 50;
  static const bool userSearchPublicOnly = true;
  static const MatchMode userSearchMatchMode = MatchMode.tight;
  static const SearchLabel userSearchLabel = SearchLabel.none;
  static const SearchLabel similarJokesLabel = SearchLabel.similarJokes;

  static const int adminSearchMaxResults = 50;
  static const bool adminSearchPublicOnly = false;
  static const MatchMode adminSearchMatchMode = MatchMode.loose;
  static const SearchLabel adminSearchLabel = SearchLabel.none;

  // Viewer incremental loading
  static const int viewerLoadMoreThreshold = 5; // trigger when <= N remaining
  static const int searchPageDefaultBatchSize = 3; // CF page size
}
