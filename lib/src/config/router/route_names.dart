/// Route names and paths for the application
/// This provides type-safe route navigation and centralized route management
class AppRoutes {
  // Private constructor to prevent instantiation
  AppRoutes._();

  // Auth routes
  static const String auth = '/auth';

  // Main app routes (shell route)
  static const String jokes = '/jokes';
  static const String saved = '/saved';
  static const String discover = '/discover';
  static const String discoverSearch = '/discover/search';
  static const String settings = '/settings';
  static const String feedback = '/settings/feedback';
  static const String admin = '/admin';

  // Admin sub-routes
  static const String adminBookCreator = '/admin/book-creator';
  static const String adminCreator = '/admin/creator';
  static const String adminManagement = '/admin/management';
  static const String adminScheduler = '/admin/scheduler';
  static const String adminEditor = '/admin/editor';
  static const String adminEditorWithJoke = '/admin/editor/:jokeId';
  static const String adminDeepResearch = '/admin/deep_research';
  static const String adminCategories = '/admin/categories';
  static const String adminCategoryEditor = '/admin/categories/:categoryId';
  static const String adminFeedback = '/admin/feedback';
  static const String adminFeedbackDetails = '/admin/feedback/:feedbackId';
  static const String adminUsers = '/admin/users';
}

/// Route names for analytics and debugging
class RouteNames {
  RouteNames._();

  static const String auth = 'auth';
  static const String jokes = 'jokes';
  static const String saved = 'saved';
  static const String discover = 'discover';
  static const String discoverSearch = 'discoverSearch';
  static const String settings = 'settings';
  static const String feedback = 'feedback';
  static const String admin = 'admin';
  static const String adminBookCreator = 'adminBookCreator';
  static const String adminCreator = 'adminCreator';
  static const String adminManagement = 'adminManagement';
  static const String adminScheduler = 'adminScheduler';
  static const String adminEditor = 'adminEditor';
  static const String adminEditorWithJoke = 'adminEditorWithJoke';
  static const String adminDeepResearch = 'adminDeepResearch';
  static const String adminCategories = 'adminCategories';
  static const String adminCategoryEditor = 'adminCategoryEditor';
  static const String adminFeedback = 'adminFeedback';
  static const String adminFeedbackDetails = 'adminFeedbackDetails';
  static const String adminUsers = 'adminUsers';
}

/// Extension for easy route navigation
extension AppRoutesExtension on String {
  /// Check if this route path is an admin route
  bool get isAdminRoute => startsWith('/admin');

  /// Check if this route path requires authentication
  bool get requiresAuth => this != AppRoutes.auth;

  /// Get the route name from path for analytics
  String get routeName {
    switch (this) {
      case AppRoutes.auth:
        return RouteNames.auth;
      case AppRoutes.jokes:
        return RouteNames.jokes;
      case AppRoutes.saved:
        return RouteNames.saved;
      case AppRoutes.discover:
        return RouteNames.discover;
      case AppRoutes.discoverSearch:
        return RouteNames.discoverSearch;
      case AppRoutes.settings:
        return RouteNames.settings;
      case AppRoutes.feedback:
        return RouteNames.feedback;
      case AppRoutes.admin:
        return RouteNames.admin;
      case AppRoutes.adminBookCreator:
        return RouteNames.adminBookCreator;
      case AppRoutes.adminCreator:
        return RouteNames.adminCreator;
      case AppRoutes.adminManagement:
        return RouteNames.adminManagement;
      case AppRoutes.adminScheduler:
        return RouteNames.adminScheduler;
      case AppRoutes.adminEditor:
        return RouteNames.adminEditor;
      case AppRoutes.adminCategories:
        return RouteNames.adminCategories;
      case AppRoutes.adminFeedback:
        return RouteNames.adminFeedback;
      default:
        return 'unknown';
    }
  }
}
