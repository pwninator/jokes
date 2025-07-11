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
  static const String settings = '/settings';
  static const String admin = '/admin';

  // Admin sub-routes
  static const String adminCreator = '/admin/creator';
  static const String adminManagement = '/admin/management';
  static const String adminScheduler = '/admin/scheduler';
  static const String adminEditor = '/admin/editor';
  static const String adminEditorWithJoke = '/admin/editor/:jokeId';
}

/// Route names for analytics and debugging
class RouteNames {
  RouteNames._();

  static const String auth = 'auth';
  static const String jokes = 'jokes';
  static const String saved = 'saved';
  static const String settings = 'settings';
  static const String admin = 'admin';
  static const String adminCreator = 'adminCreator';
  static const String adminManagement = 'adminManagement';
  static const String adminScheduler = 'adminScheduler';
  static const String adminEditor = 'adminEditor';
  static const String adminEditorWithJoke = 'adminEditorWithJoke';
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
      case AppRoutes.settings:
        return RouteNames.settings;
      case AppRoutes.admin:
        return RouteNames.admin;
      case AppRoutes.adminCreator:
        return RouteNames.adminCreator;
      case AppRoutes.adminManagement:
        return RouteNames.adminManagement;
      case AppRoutes.adminScheduler:
        return RouteNames.adminScheduler;
      case AppRoutes.adminEditor:
        return RouteNames.adminEditor;
      default:
        return 'unknown';
    }
  }
}
