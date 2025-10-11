import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';

import '../../test_helpers/firebase_mocks.dart';

void main() {
  group('FirebaseAnalyticsObserver integration', () {
    testWidgets('logs screen_view on initial route and after navigation', (
      tester,
    ) async {
      final mockAnalytics = FirebaseMocks.mockFirebaseAnalytics;

      final router = GoRouter(
        initialLocation: '/home',
        routes: [
          // Shell with tabs including admin
          ShellRoute(
            observers: [FirebaseAnalyticsObserver(analytics: mockAnalytics)],
            builder: (context, state, child) => Scaffold(body: child),
            routes: [
              GoRoute(
                path: '/home',
                name: RouteNames.jokes,
                builder: (context, state) => const Scaffold(body: Text('Home')),
              ),
              GoRoute(
                path: '/saved',
                name: RouteNames.saved,
                builder: (context, state) =>
                    const Scaffold(body: Text('Saved')),
              ),
              GoRoute(
                path: '/admin',
                name: RouteNames.admin,
                builder: (context, state) =>
                    const Scaffold(body: Text('Admin')),
              ),
              GoRoute(
                path: '/admin/management',
                name: RouteNames.adminManagement,
                builder: (context, state) =>
                    const Scaffold(body: Text('Admin Management')),
              ),
            ],
          ),
        ],
        observers: [FirebaseAnalyticsObserver(analytics: mockAnalytics)],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...FirebaseMocks.getFirebaseProviderOverrides(),
            // Ensure our mock is used by the observer through provider
            firebaseAnalyticsProvider.overrideWithValue(mockAnalytics),
          ],
          child: MaterialApp.router(theme: lightTheme, routerConfig: router),
        ),
      );

      await tester.pumpAndSettle();

      // Initial screen view
      verify(
        () => mockAnalytics.logScreenView(
          screenName: any(named: 'screenName'),
          screenClass: any(named: 'screenClass'),
          parameters: any(named: 'parameters'),
        ),
      ).called(greaterThan(0));

      // Navigate to saved
      router.go('/saved');
      await tester.pumpAndSettle();

      verify(
        () => mockAnalytics.logScreenView(
          screenName: any(named: 'screenName'),
          screenClass: any(named: 'screenClass'),
          parameters: any(named: 'parameters'),
        ),
      ).called(greaterThan(0));

      // Navigate to admin root
      router.go('/admin');
      await tester.pumpAndSettle();
      verify(
        () => mockAnalytics.logScreenView(
          screenName: any(named: 'screenName'),
          screenClass: any(named: 'screenClass'),
          parameters: any(named: 'parameters'),
        ),
      ).called(greaterThan(0));

      // Navigate to admin sub-screen
      router.go('/admin/management');
      await tester.pumpAndSettle();
      verify(
        () => mockAnalytics.logScreenView(
          screenName: any(named: 'screenName'),
          screenClass: any(named: 'screenClass'),
          parameters: any(named: 'parameters'),
        ),
      ).called(greaterThan(0));
    });
  });
}
