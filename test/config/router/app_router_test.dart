import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart';

void main() {
  group('AppRouter.shouldResetDiscoverOnNavigation', () {
    test('returns true for Discover tab index', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(
          newIndex: 1, // discover is index 1 when feed is enabled
          isAdmin: false,
          feedEnabled: true,
        ),
        isTrue,
      );
    });

    test('returns false for non Discover tab index', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(
          newIndex: 0, // feed index when feed is enabled
          isAdmin: false,
          feedEnabled: true,
        ),
        isFalse,
      );
    });

    test('returns false for out-of-range index', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(
          newIndex: 99,
          isAdmin: false,
          feedEnabled: true,
        ),
        isFalse,
      );
    });

    test('still returns true for Discover when admin tabs visible', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(
          newIndex: 1, // discover remains index 1
          isAdmin: true,
          feedEnabled: true,
        ),
        isTrue,
      );
    });
  });
}
