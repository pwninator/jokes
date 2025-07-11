import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

/// Auth guard that handles authentication state and redirects
class AuthGuard {
  const AuthGuard._();

  /// Determine redirect based on authentication state
  static String? redirect(BuildContext context, GoRouterState state) {
    final container = ProviderScope.containerOf(context);
    final authState = container.read(authStateProvider);
    final currentPath = state.uri.path;

    return authState.when(
      data: (user) {
        // User is authenticated
        if (user != null) {
          // If user is on auth route but authenticated, redirect to main app
          if (currentPath == AppRoutes.auth) {
            return AppRoutes.jokes;
          }

          // Check admin access for admin routes
          if (currentPath.isAdminRoute && !user.isAdmin) {
            debugPrint(
              'ROUTER: Non-admin user attempted to access admin route: $currentPath',
            );
            // Redirect non-admin users away from admin routes
            return AppRoutes.jokes;
          }

          // User is authenticated and has proper access
          return null;
        } else {
          // User is not authenticated
          if (currentPath != AppRoutes.auth) {
            debugPrint(
              'ROUTER: Unauthenticated user redirected to auth from: $currentPath',
            );
            return AppRoutes.auth;
          }
          return null;
        }
      },
      loading: () {
        // While auth state is loading, redirect to auth unless already there
        if (currentPath != AppRoutes.auth) {
          return AppRoutes.auth;
        }
        return null;
      },
      error: (error, stackTrace) {
        // On auth error, redirect to auth
        debugPrint('ROUTER: Auth error, redirecting to auth: $error');
        return AppRoutes.auth;
      },
    );
  }

  /// Check if user has admin access
  static bool hasAdminAccess(BuildContext context) {
    final container = ProviderScope.containerOf(context);
    return container.read(isAdminProvider);
  }

  /// Check if user is authenticated
  static bool isAuthenticated(BuildContext context) {
    final container = ProviderScope.containerOf(context);
    return container.read(isAuthenticatedProvider);
  }
}

/// Route refresh notifier that rebuilds router when auth state changes
class RouteRefreshNotifier extends ChangeNotifier {
  RouteRefreshNotifier(this._ref) {
    // Listen to auth state changes and refresh routes
    _ref.listen(authStateProvider, (previous, next) {
      debugPrint('ROUTER: Auth state changed, refreshing routes');
      notifyListeners();
    });
  }

  final Ref _ref;
}

/// Provider for route refresh notifier
final routeRefreshNotifierProvider = Provider<RouteRefreshNotifier>((ref) {
  return RouteRefreshNotifier(ref);
});
