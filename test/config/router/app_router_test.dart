import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';

void main() {
  group('NavigationState.shouldResetDiscoverOnNavigation', () {
    testWidgets(
      'returns true when navigating to discover tab with feed enabled',
      (tester) async {
        // Arrange: Feed enabled
        final container = ProviderContainer(
          overrides: [feedScreenStatusProvider.overrideWithValue(true)],
        );

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: Consumer(
              builder: (context, ref, _) {
                final navState = NavigationState.create(
                  isAdmin: false,
                  currentLocation: '/feed',
                  ref: ref,
                );

                // Act & Assert: Find discover tab index and verify it returns true
                final discoverIndex = navState.visibleTabs.indexWhere(
                  (tab) => tab.id == TabId.discover,
                );
                expect(discoverIndex, greaterThanOrEqualTo(0));
                expect(
                  navState.shouldResetDiscoverOnNavigation(discoverIndex),
                  isTrue,
                );

                return MaterialApp(home: Container());
              },
            ),
          ),
        );

        container.dispose();
      },
    );

    testWidgets('returns false when navigating to non-discover tab', (
      tester,
    ) async {
      // Arrange: Feed enabled
      final container = ProviderContainer(
        overrides: [feedScreenStatusProvider.overrideWithValue(true)],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: Consumer(
            builder: (context, ref, _) {
              final navState = NavigationState.create(
                isAdmin: false,
                currentLocation: '/feed',
                ref: ref,
              );

              // Act & Assert: Feed tab (first tab) should not reset discover
              expect(navState.shouldResetDiscoverOnNavigation(0), isFalse);

              return MaterialApp(home: Container());
            },
          ),
        ),
      );

      container.dispose();
    });

    testWidgets('returns false for out-of-range tab index', (tester) async {
      // Arrange
      final container = ProviderContainer(
        overrides: [feedScreenStatusProvider.overrideWithValue(true)],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: Consumer(
            builder: (context, ref, _) {
              final navState = NavigationState.create(
                isAdmin: false,
                currentLocation: '/feed',
                ref: ref,
              );

              // Act & Assert
              expect(navState.shouldResetDiscoverOnNavigation(99), isFalse);
              expect(navState.shouldResetDiscoverOnNavigation(-1), isFalse);

              return MaterialApp(home: Container());
            },
          ),
        ),
      );

      container.dispose();
    });

    testWidgets('returns true when navigating to discover tab with admin mode', (
      tester,
    ) async {
      // Arrange: Admin mode with feed enabled
      final container = ProviderContainer(
        overrides: [feedScreenStatusProvider.overrideWithValue(true)],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: Consumer(
            builder: (context, ref, _) {
              final navState = NavigationState.create(
                isAdmin: true,
                currentLocation: '/feed',
                ref: ref,
              );

              // Act & Assert: Find discover tab index and verify it returns true
              final discoverIndex = navState.visibleTabs.indexWhere(
                (tab) => tab.id == TabId.discover,
              );
              expect(discoverIndex, greaterThanOrEqualTo(0));
              expect(
                navState.shouldResetDiscoverOnNavigation(discoverIndex),
                isTrue,
              );

              return MaterialApp(home: Container());
            },
          ),
        ),
      );

      container.dispose();
    });

    testWidgets(
      'returns true when navigating to discover tab with feed disabled',
      (tester) async {
        // Arrange: Feed disabled, daily shown instead
        final container = ProviderContainer(
          overrides: [feedScreenStatusProvider.overrideWithValue(false)],
        );

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: Consumer(
              builder: (context, ref, _) {
                final navState = NavigationState.create(
                  isAdmin: false,
                  currentLocation: '/jokes',
                  ref: ref,
                );

                // Act & Assert: Find discover tab index and verify it returns true
                final discoverIndex = navState.visibleTabs.indexWhere(
                  (tab) => tab.id == TabId.discover,
                );
                expect(discoverIndex, greaterThanOrEqualTo(0));
                expect(
                  navState.shouldResetDiscoverOnNavigation(discoverIndex),
                  isTrue,
                );

                return MaterialApp(home: Container());
              },
            ),
          ),
        );

        container.dispose();
      },
    );

    testWidgets(
      'returns false for all non-discover tabs regardless of feed status',
      (tester) async {
        // Test both feed enabled and disabled scenarios
        for (final feedEnabled in [true, false]) {
          final container = ProviderContainer(
            overrides: [
              feedScreenStatusProvider.overrideWithValue(feedEnabled),
            ],
          );

          await tester.pumpWidget(
            UncontrolledProviderScope(
              container: container,
              child: Consumer(
                builder: (context, ref, _) {
                  final navState = NavigationState.create(
                    isAdmin: false,
                    currentLocation: feedEnabled ? '/feed' : '/jokes',
                    ref: ref,
                  );

                  // Check all tabs except discover
                  for (int i = 0; i < navState.visibleTabs.length; i++) {
                    if (navState.visibleTabs[i].id != TabId.discover) {
                      expect(
                        navState.shouldResetDiscoverOnNavigation(i),
                        isFalse,
                        reason:
                            'Tab ${navState.visibleTabs[i].id} should not reset discover',
                      );
                    }
                  }

                  return MaterialApp(home: Container());
                },
              ),
            ),
          );

          container.dispose();
        }
      },
    );
  });
}
