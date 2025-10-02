import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart';

void main() {
  group('AppRouter.shouldResetDiscoverOnNavigation', () {
    test('returns true for Discover tab index', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(newIndex: 1, isAdmin: false),
        isTrue,
      );
    });

    test('returns false for non Discover tab index', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(newIndex: 2, isAdmin: false),
        isFalse,
      );
    });

    test('returns false for out-of-range index', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(newIndex: 99, isAdmin: false),
        isFalse,
      );
    });

    test('still returns true for Discover when admin tabs visible', () {
      expect(
        AppRouter.shouldResetDiscoverOnNavigation(newIndex: 1, isAdmin: true),
        isTrue,
      );
    });
  });
}
