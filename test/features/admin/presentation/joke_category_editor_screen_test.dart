import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_editor_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

class MockJokeCategoryRepository extends Mock
    implements JokeCategoryRepository {}

class FakeJokeCategory extends Fake implements JokeCategory {}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeJokeCategory());
  });
  group('JokeCategoryEditorView', () {
    late MockJokeCategoryRepository mockJokeCategoryRepository;

    final testCategory = JokeCategory(
      id: '${JokeCategory.firestorePrefix}1',
      displayName: 'Test Category',
      jokeDescriptionQuery: 'test query',
      state: JokeCategoryState.proposed,
      type: CategoryType.firestore,
    );

    setUp(() {
      mockJokeCategoryRepository = MockJokeCategoryRepository();
      when(
        () => mockJokeCategoryRepository.watchCategoryImages(any()),
      ).thenAnswer((_) => Stream.value([]));
      when(
        () => mockJokeCategoryRepository.deleteCategory(any()),
      ).thenAnswer((_) async => {});
      when(
        () => mockJokeCategoryRepository.upsertCategory(any()),
      ).thenAnswer((_) async => {});
    });

    testWidgets('renders correctly', (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCategoryRepositoryProvider.overrideWithValue(
              mockJokeCategoryRepository,
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeCategoryEditorView(category: testCategory),
            ),
          ),
        ),
      );

      // One TextFormField: editable image description
      expect(find.byType(TextFormField), findsNWidgets(1));
      expect(find.text('Proposed'), findsOneWidget);
    });

    testWidgets('can update state', (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCategoryRepositoryProvider.overrideWithValue(
              mockJokeCategoryRepository,
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeCategoryEditorView(category: testCategory),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(DropdownButtonFormField<JokeCategoryState>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Approved').last);
      await tester.pumpAndSettle();

      expect(find.text('Approved'), findsOneWidget);
    });

    testWidgets('update button calls upsertCategory', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCategoryRepositoryProvider.overrideWithValue(
              mockJokeCategoryRepository,
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeCategoryEditorView(category: testCategory),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Update Category'));
      await tester.pumpAndSettle();

      verify(() => mockJokeCategoryRepository.upsertCategory(any())).called(1);
    });

    testWidgets('delete button calls deleteCategory', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCategoryRepositoryProvider.overrideWithValue(
              mockJokeCategoryRepository,
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeCategoryEditorView(category: testCategory),
            ),
          ),
        ),
      );

      final deleteButton = find.byKey(const Key('delete_category_button'));
      await tester.press(deleteButton);
      await tester.pumpAndSettle(const Duration(seconds: 4));

      verify(
        () => mockJokeCategoryRepository.deleteCategory(testCategory.id),
      ).called(1);
    });
  });
}
