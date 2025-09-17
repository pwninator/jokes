import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_categories_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_tile.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';
import '../../../test_helpers/firebase_mocks.dart';

class _MockJokeCategoryRepository extends Mock
    implements JokeCategoryRepository {}

class _MockImageService extends Mock implements ImageService {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  testWidgets('renders categories with and without images', (tester) async {
    final repo = _MockJokeCategoryRepository();
    final imageService = _MockImageService();
    final analyticsService = _MockAnalyticsService();

    when(() => repo.watchCategories()).thenAnswer(
      (_) => Stream.value([
        const JokeCategory(
          id: 'animal_jokes',
          displayName: 'Animal Jokes',
          jokeDescriptionQuery: 'animal',
          imageUrl: 'https://example.com/image.jpg',
          state: JokeCategoryState.APPROVED,
        ),
        const JokeCategory(
          id: 'seasonal',
          displayName: 'Seasonal',
          jokeDescriptionQuery: 'season',
          imageUrl: null,
          state: JokeCategoryState.REJECTED,
        ),
      ]),
    );

    // Prevent real network image loads by making processed URL null
    when(() => imageService.getProcessedJokeImageUrl(any())).thenReturn(null);
    when(() => imageService.isValidImageUrl(any())).thenReturn(false);
    when(
      () => analyticsService.logErrorImageLoad(
        jokeId: any(named: 'jokeId'),
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    final container = ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeCategoryRepositoryProvider.overrideWithValue(repo),
        imageServiceProvider.overrideWithValue(imageService),
        analyticsServiceProvider.overrideWithValue(analyticsService),
      ],
    );
    addTearDown(container.dispose);

    // Force portrait so AdaptiveAppBarScreen shows the title
    final originalSize = tester.view.physicalSize;
    tester.view.physicalSize = const Size(600, 800);
    addTearDown(() => tester.view.physicalSize = originalSize);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: JokeCategoriesScreen()),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Joke Categories'), findsOneWidget);
    expect(find.text('Animal Jokes'), findsOneWidget);

    // Scroll to build the next item lazily (grid is scrollable)
    final scrollable = find.byType(Scrollable);
    await tester.drag(scrollable, const Offset(0, -400));
    await tester.pump();

    expect(find.text('Seasonal'), findsOneWidget);

    final approvedTile = find.widgetWithText(JokeCategoryTile, 'Animal Jokes');
    final rejectedTile = find.widgetWithText(JokeCategoryTile, 'Seasonal');

    final approvedBorder = tester.widget<Container>(find.descendant(
      of: approvedTile,
      matching: find.byKey(const Key('joke_category_tile_container')),
    ));
    final rejectedBorder = tester.widget<Container>(find.descendant(
      of: rejectedTile,
      matching: find.byKey(const Key('joke_category_tile_container')),
    ));

    expect(
        (approvedBorder.decoration as BoxDecoration).border?.top.color,
        Colors.green);
    expect(
        (rejectedBorder.decoration as BoxDecoration).border?.top.color,
        Colors.red);
  });

  testWidgets('tapping a category navigates to the editor', (tester) async {
    final repo = _MockJokeCategoryRepository();
    final imageService = _MockImageService();
    final analyticsService = _MockAnalyticsService();
    final mockGoRouter = MockGoRouter();

    when(() => repo.watchCategories()).thenAnswer(
      (_) => Stream.value([
        const JokeCategory(
          id: 'animal_jokes',
          displayName: 'Animal Jokes',
          jokeDescriptionQuery: 'animal',
          imageUrl: 'https://example.com/image.jpg',
        ),
      ]),
    );

    when(() => imageService.getProcessedJokeImageUrl(any())).thenReturn(null);
    when(() => imageService.isValidImageUrl(any())).thenReturn(false);
    when(
      () => analyticsService.logErrorImageLoad(
        jokeId: any(named: 'jokeId'),
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    final container = ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeCategoryRepositoryProvider.overrideWithValue(repo),
        imageServiceProvider.overrideWithValue(imageService),
        analyticsServiceProvider.overrideWithValue(analyticsService),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: MockGoRouterProvider(
            goRouter: mockGoRouter,
            child: const JokeCategoriesScreen(),
          ),
        ),
      ),
    );

    await tester.pump();

    await tester.tap(find.text('Animal Jokes'));
    await tester.pumpAndSettle();

    verify(() => mockGoRouter.go(any(), extra: any(named: 'extra'))).called(1);
  });
}

class MockGoRouter extends Mock implements GoRouter {}

class MockGoRouterProvider extends StatelessWidget {
  const MockGoRouterProvider({
    required this.goRouter,
    required this.child,
    super.key,
  });

  final MockGoRouter goRouter;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return InheritedGoRouter(
      goRouter: goRouter,
      child: child,
    );
  }
}
