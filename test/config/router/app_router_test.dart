import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart';

void main() {
  group('NavigationState.shouldResetDiscoverOnNavigation', () {
    testWidgets('returns true when navigating to discover tab', (tester) async {
      final container = ProviderContainer();

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

              final discoverIndex = navState.visibleTabs.indexWhere(
                (tab) => tab.id == TabId.discover,
              );
              expect(discoverIndex, greaterThanOrEqualTo(0));
              expect(
                navState.shouldResetDiscoverOnNavigation(discoverIndex),
                isTrue,
              );

              return const SizedBox.shrink();
            },
          ),
        ),
      );

      container.dispose();
    });

    testWidgets('returns false when navigating to non-discover tab', (
      tester,
    ) async {
      final container = ProviderContainer();

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

              expect(navState.shouldResetDiscoverOnNavigation(0), isFalse);

              return const SizedBox.shrink();
            },
          ),
        ),
      );

      container.dispose();
    });

    testWidgets('returns false for out-of-range tab index', (tester) async {
      final container = ProviderContainer();

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

              expect(navState.shouldResetDiscoverOnNavigation(99), isFalse);
              expect(navState.shouldResetDiscoverOnNavigation(-1), isFalse);

              return const SizedBox.shrink();
            },
          ),
        ),
      );

      container.dispose();
    });

    testWidgets(
      'returns true when navigating to discover tab with admin mode',
      (tester) async {
        final container = ProviderContainer();

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

                final discoverIndex = navState.visibleTabs.indexWhere(
                  (tab) => tab.id == TabId.discover,
                );
                expect(discoverIndex, greaterThanOrEqualTo(0));
                expect(
                  navState.shouldResetDiscoverOnNavigation(discoverIndex),
                  isTrue,
                );

                return const SizedBox.shrink();
              },
            ),
          ),
        );

        container.dispose();
      },
    );
  });
}
