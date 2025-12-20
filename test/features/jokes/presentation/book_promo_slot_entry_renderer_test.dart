import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entry_renderers.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockAppUsageService extends Mock implements AppUsageService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockAnalyticsService mockAnalyticsService;
  late MockAppUsageService mockAppUsageService;
  final fixedNow = DateTime(2025, 2, 1);

  setUp(() {
    mockAnalyticsService = MockAnalyticsService();
    mockAppUsageService = MockAppUsageService();
  });

  testWidgets('renders placeholder card and logs analytics once', (
    tester,
  ) async {
    when(
      () => mockAnalyticsService.logBookPromoCardViewed(
        jokeContext: any(named: 'jokeContext'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockAppUsageService.setBookPromoCardLastShown(any()),
    ).thenAnswer((_) async {});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
          clockProvider.overrideWithValue(() => fixedNow),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: Consumer(
              builder: (context, ref, _) {
                final renderer = const BookPromoSlotEntryRenderer();
                final config = SlotEntryViewConfig(
                  context: context,
                  ref: ref,
                  index: 0,
                  isLandscape: false,
                  jokeContext: 'joke_feed',
                  showSimilarSearchButton: false,
                );
                return SingleChildScrollView(
                  child: renderer.build(
                    entry: const BookPromoSlotEntry(),
                    config: config,
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );

    // Allow microtask logging to complete.
    await tester.pump();

    expect(find.text('Book Promo Card'), findsOneWidget);
    verify(
      () =>
          mockAnalyticsService.logBookPromoCardViewed(jokeContext: 'joke_feed'),
    ).called(1);
    verify(
      () => mockAppUsageService.setBookPromoCardLastShown(fixedNow),
    ).called(1);
  });
}
