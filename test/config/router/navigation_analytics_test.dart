import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:riverpod/riverpod.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';

class _MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  late _MockAnalyticsService mockAnalyticsService;

  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  setUp(() {
    mockAnalyticsService = _MockAnalyticsService();
  });

  test('NavigationAnalytics maps feed route to joke feed tab', () {
    final container = ProviderContainer(
      overrides: [
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
      ],
    );
    addTearDown(container.dispose);

    final navigationAnalytics = container.read(navigationAnalyticsProvider);

    navigationAnalytics.trackRouteChange(
      AppRoutes.feed,
      AppRoutes.discover,
      'tap',
    );

    verify(
      () => mockAnalyticsService.logTabChanged(
        AppTab.jokeFeed,
        AppTab.discover,
        method: 'tap',
      ),
    ).called(1);
  });
}
