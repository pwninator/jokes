import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_categories_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

class MockJokeCategoryRepository extends Mock
    implements JokeCategoryRepository {}

class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockPerformanceService extends Mock implements PerformanceService {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(CategoryType.firestore);
    registerFallbackValue(TraceName.fsRead);
    registerFallbackValue(<String, String>{});
  });

  late MockJokeCategoryRepository mockRepository;
  late MockImageService mockImageService;
  late MockAnalyticsService mockAnalyticsService;
  late MockPerformanceService mockPerformanceService;

  setUp(() {
    // Create fresh mocks per test
    mockRepository = MockJokeCategoryRepository();
    mockImageService = MockImageService();
    mockAnalyticsService = MockAnalyticsService();
    mockPerformanceService = MockPerformanceService();

    // Stub default behavior
    when(
      () => mockRepository.watchCategories(),
    ).thenAnswer((_) => Stream.value([]));
    when(
      () => mockImageService.getProcessedJokeImageUrl(
        any(),
        width: any(named: 'width'),
      ),
    ).thenReturn(null);
    when(() => mockImageService.isValidImageUrl(any())).thenReturn(false);
    when(
      () => mockAnalyticsService.logErrorImageLoad(
        jokeId: any(named: 'jokeId'),
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    // Stub performance service methods
    when(
      () => mockPerformanceService.startNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerformanceService.putNamedTraceAttributes(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerformanceService.stopNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerformanceService.dropNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenReturn(null);
  });

  testWidgets('renders categories with and without images', (tester) async {
    // Arrange: Create test categories
    when(() => mockRepository.watchCategories()).thenAnswer(
      (_) => Stream.value([
        JokeCategory(
          id: 'animal_jokes',
          displayName: 'Animal Jokes',
          jokeDescriptionQuery: 'animal',
          imageUrl: 'https://example.com/image.jpg',
          type: CategoryType.firestore,
        ),
        JokeCategory(
          id: 'seasonal',
          displayName: 'Seasonal',
          jokeDescriptionQuery: 'season',
          imageUrl: null,
          type: CategoryType.firestore,
        ),
      ]),
    );
    // Force portrait so AdaptiveAppBarScreen shows the title
    final originalSize = tester.view.physicalSize;
    addTearDown(() => tester.view.physicalSize = originalSize);
    tester.view.physicalSize = const Size(600, 800);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          jokeCategoryRepositoryProvider.overrideWithValue(mockRepository),
          imageServiceProvider.overrideWithValue(mockImageService),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          performanceServiceProvider.overrideWithValue(mockPerformanceService),
        ],
        child: const MaterialApp(home: Scaffold(body: JokeCategoriesScreen())),
      ),
    );

    await tester.pumpAndSettle();

    // Assert: Should display categories (title is rendered by global AppBar outside this test)
    expect(find.text('Animal Jokes'), findsOneWidget);

    // Scroll to build the next item lazily (grid is scrollable)
    final scrollable = find.byType(Scrollable);
    await tester.drag(scrollable, const Offset(0, -400));
    await tester.pumpAndSettle();

    expect(find.text('Seasonal'), findsOneWidget);
  });

  testWidgets('navigates to category editor when tile is tapped', (
    tester,
  ) async {
    // Arrange: Create test category and mock router
    final mockGoRouter = MockGoRouter();

    when(() => mockRepository.watchCategories()).thenAnswer(
      (_) => Stream.value([
        JokeCategory(
          id: 'test_category',
          displayName: 'Test Category',
          jokeDescriptionQuery: 'test',
          imageUrl: null,
          type: CategoryType.firestore,
        ),
      ]),
    );

    // Stub pushNamed to return a Future
    when(
      () => mockGoRouter.pushNamed<Object?>(
        'adminCategoryEditor',
        pathParameters: {'categoryId': 'test_category'},
        queryParameters: any(named: 'queryParameters'),
        extra: any(named: 'extra'),
      ),
    ).thenAnswer((_) async => null);

    // Force portrait so AdaptiveAppBarScreen shows the title
    final originalSize = tester.view.physicalSize;
    addTearDown(() => tester.view.physicalSize = originalSize);
    tester.view.physicalSize = const Size(600, 800);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          jokeCategoryRepositoryProvider.overrideWithValue(mockRepository),
          imageServiceProvider.overrideWithValue(mockImageService),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          performanceServiceProvider.overrideWithValue(mockPerformanceService),
        ],
        child: MaterialApp(
          home: InheritedGoRouter(
            goRouter: mockGoRouter,
            child: const Scaffold(body: JokeCategoriesScreen()),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Act: Find and tap the category tile
    final categoryTile = find.byType(InkWell);
    expect(categoryTile, findsOneWidget);

    await tester.tap(categoryTile);
    await tester.pump();

    // Assert: Verify navigation was called with correct parameters
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
