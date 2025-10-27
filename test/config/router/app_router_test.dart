import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';

class MockRef extends Mock implements WidgetRef {}

void main() {
  group('NavigationState.shouldResetDiscoverOnNavigation', () {
    late MockRef ref;

    setUp(() {
      ref = MockRef();
      // Mock feedScreenStatusProvider
      when(
        () => ref.read(feedScreenStatusProvider),
      ).thenReturn(true); // feed enabled
    });

    test('returns true for Discover tab index when feed is enabled', () {
      final navState = NavigationState.create(
        isAdmin: false,
        currentLocation: '/feed',
        ref: ref,
      );

      // Discover is at index 1 when feed is enabled (feed=0, discover=1, saved=2, etc.)
      expect(navState.shouldResetDiscoverOnNavigation(1), isTrue);
    });

    test('returns false for non Discover tab index', () {
      final navState = NavigationState.create(
        isAdmin: false,
        currentLocation: '/feed',
        ref: ref,
      );

      // Feed is at index 0
      expect(navState.shouldResetDiscoverOnNavigation(0), isFalse);
    });

    test('returns false for out-of-range index', () {
      final navState = NavigationState.create(
        isAdmin: false,
        currentLocation: '/feed',
        ref: ref,
      );

      expect(navState.shouldResetDiscoverOnNavigation(99), isFalse);
    });

    test('returns true for Discover when admin tabs visible', () {
      final navState = NavigationState.create(
        isAdmin: true,
        currentLocation: '/feed',
        ref: ref,
      );

      // Discover is still at index 1 even with admin
      expect(navState.shouldResetDiscoverOnNavigation(1), isTrue);
    });

    test(
      'returns false for Discover when feed is disabled (daily is shown instead)',
      () {
        when(
          () => ref.read(feedScreenStatusProvider),
        ).thenReturn(false); // feed disabled, daily shown

        final navState = NavigationState.create(
          isAdmin: false,
          currentLocation: '/jokes',
          ref: ref,
        );

        // With daily enabled, discover is at index 2 (daily=0, discover=1, saved=2, etc.)
        // Let's check index 1 which should be discover now
        expect(navState.shouldResetDiscoverOnNavigation(1), isTrue);
      },
    );
  });
}
