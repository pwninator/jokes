import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_categories_screen.dart';
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
        ),
        const JokeCategory(
          id: 'seasonal',
          displayName: 'Seasonal',
          jokeDescriptionQuery: 'season',
          imageUrl: null,
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
  });

  testWidgets('navigates to category editor when tile is tapped', (tester) async {
    final repo = _MockJokeCategoryRepository();
    final imageService = _MockImageService();
    final analyticsService = _MockAnalyticsService();
    final mockGoRouter = MockGoRouter();

    when(() => repo.watchCategories()).thenAnswer(
      (_) => Stream.value([
        const JokeCategory(
          id: 'test_category',
          displayName: 'Test Category',
          jokeDescriptionQuery: 'test',
          imageUrl: null,
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

    // Force portrait so AdaptiveAppBarScreen shows the title
    final originalSize = tester.view.physicalSize;
    tester.view.physicalSize = const Size(600, 800);
    addTearDown(() => tester.view.physicalSize = originalSize);

    // Stub pushNamed to return a Future
    when(
      () => mockGoRouter.pushNamed<Object?>(
        'adminCategoryEditor',
        pathParameters: {'categoryId': 'test_category'},
        queryParameters: any(named: 'queryParameters'),
        extra: any(named: 'extra'),
      ),
    ).thenAnswer((_) async => null);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: InheritedGoRouter(
            goRouter: mockGoRouter,
            child: const JokeCategoriesScreen(),
          ),
        ),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    // Find and tap the category tile
    final categoryTile = find.byType(InkWell);
    expect(categoryTile, findsOneWidget);
    
    await tester.tap(categoryTile);
    await tester.pump();

    // Verify navigation was called with correct parameters
    verify(
      () => mockGoRouter.pushNamed<Object?>(
        'adminCategoryEditor',
        pathParameters: {'categoryId': 'test_category'},
        queryParameters: any(named: 'queryParameters'),
        extra: any(named: 'extra'),
      ),
    ).called(1);
  });
}

class MockGoRouter extends Mock implements GoRouter {}
