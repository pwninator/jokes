import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
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
        // Allow all main routes whether authenticated or not.
        // Only guard admin routes.
        if (currentPath.isAdminRoute) {
          if (user == null || !user.isAdmin) {
            AppLogger.warn(
              'ROUTER: Blocking admin route for non-admin/unauthenticated: $currentPath',
            );
            return AppRoutes.jokes;
          }
        }

        return null;
      },
      loading: () {
        // While loading, do not block. Let UI proceed; admin routes will be re-evaluated once loaded.
        return null;
      },
      error: (error, stackTrace) {
        // On error, be permissive on main routes but block admin.
        if (currentPath.isAdminRoute) {
          AppLogger.warn(
            'ROUTER: Auth error on admin route, redirecting: $error',
          );
          return AppRoutes.jokes;
        }
        return null;
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
      AppLogger.debug('ROUTER: Auth state changed, refreshing routes');
      notifyListeners();
    });
  }

  final Ref _ref;
}

/// Provider for route refresh notifier
final routeRefreshNotifierProvider = Provider<RouteRefreshNotifier>((ref) {
  return RouteRefreshNotifier(ref);
});
