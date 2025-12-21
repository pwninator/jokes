import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';

void main() {
  group('jokeCategoriesProvider', () {
    test(
      'sorts seasonal categories first, then sorts alphabetically by displayName',
      () async {
        final repo = _FakeJokeCategoryRepository(
          categoriesStream: Stream.value([
            JokeCategory(
              id: '${JokeCategory.firestorePrefix}cats',
              displayName: 'Cats',
              type: CategoryType.firestore,
              jokeDescriptionQuery: 'cats',
              state: JokeCategoryState.approved,
            ),
            JokeCategory(
              id: '${JokeCategory.firestorePrefix}zombies',
              displayName: 'Zombies',
              type: CategoryType.firestore,
              seasonalValue: 'Halloween',
              state: JokeCategoryState.approved,
            ),
            JokeCategory(
              id: '${JokeCategory.firestorePrefix}bananas',
              displayName: 'Bananas',
              type: CategoryType.firestore,
              jokeDescriptionQuery: 'bananas',
              state: JokeCategoryState.approved,
            ),
            JokeCategory(
              id: '${JokeCategory.firestorePrefix}apples',
              displayName: 'Apples',
              type: CategoryType.firestore,
              seasonalValue: 'Spring',
              state: JokeCategoryState.approved,
            ),
          ]),
        );

        final container = ProviderContainer(
          overrides: [jokeCategoryRepositoryProvider.overrideWithValue(repo)],
        );
        addTearDown(container.dispose);

        final value = await container.read(jokeCategoriesProvider.future);
        expect(value.map((c) => c.displayName).toList(), [
          'Apples',
          'Zombies',
          'Bananas',
          'Cats',
        ]);
      },
    );
  });

  group('discoverCategoriesProvider', () {
    test(
      'includes popular, Halloween seasonal, and approved categories',
      () async {
        final adminSettings = _FakeAdminSettingsService(
          initialShowProposedCategories: false,
        );
        final container = ProviderContainer(
          overrides: [
            adminSettingsServiceProvider.overrideWithValue(adminSettings),
            // Provide some approved categories from Firestore
            jokeCategoriesProvider.overrideWith(
              (ref) => Stream.value([
                JokeCategory(
                  id: '${JokeCategory.firestorePrefix}halloween',
                  displayName: 'Halloween',
                  type: CategoryType.firestore,
                  seasonalValue: 'Halloween',
                  state: JokeCategoryState.approved,
                ),
                JokeCategory(
                  id: '${JokeCategory.firestorePrefix}1',
                  displayName: 'Cats',
                  type: CategoryType.firestore,
                  jokeDescriptionQuery: 'cats',
                  state: JokeCategoryState.approved,
                ),
              ]),
            ),
          ],
        );
        addTearDown(container.dispose);

        // Wait for discoverCategoriesProvider to have a value
        final completer = Completer<void>();
        final sub = container.listen(discoverCategoriesProvider, (_, next) {
          if (next.hasValue && !completer.isCompleted) {
            completer.complete();
          }
        }, fireImmediately: true);
        addTearDown(sub.close);
        await completer.future;

        final async = container.read(discoverCategoriesProvider);
        expect(async.hasValue, isTrue);
        final categories = async.value!;

        // Expect 4 categories: daily + popular + halloween + cats
        expect(categories.length, 4);
        // Daily tile should be first
        expect(categories.first.type, CategoryType.daily);
        expect(categories.first.id, 'programmatic:daily');
        expect(categories.first.displayName, 'Daily Jokes');
        // Popular should be present
        expect(
          categories.any((category) => category.type == CategoryType.popular),
          isTrue,
        );
        // Halloween should be present
        expect(
          categories.any(
            (category) =>
                category.id == '${JokeCategory.firestorePrefix}halloween' &&
                category.type == CategoryType.firestore &&
                category.seasonalValue == 'Halloween',
          ),
          isTrue,
        );
        // Cats from Firestore should be present
        expect(
          categories.any(
            (category) => category.id == '${JokeCategory.firestorePrefix}1',
          ),
          isTrue,
        );
      },
    );

    test('excludes proposed categories when toggle disabled', () async {
      final adminSettings = _FakeAdminSettingsService(
        initialShowProposedCategories: false,
      );
      final container = ProviderContainer(
        overrides: [
          adminSettingsServiceProvider.overrideWithValue(adminSettings),
          jokeCategoriesProvider.overrideWith(
            (ref) => Stream.value([
              JokeCategory(
                id: '${JokeCategory.firestorePrefix}approved',
                displayName: 'Approved',
                type: CategoryType.firestore,
                jokeDescriptionQuery: 'approved',
                state: JokeCategoryState.approved,
              ),
              JokeCategory(
                id: '${JokeCategory.firestorePrefix}proposed',
                displayName: 'Proposed',
                type: CategoryType.firestore,
                jokeDescriptionQuery: 'proposed',
                state: JokeCategoryState.proposed,
              ),
            ]),
          ),
        ],
      );
      addTearDown(container.dispose);

      final completer = Completer<void>();
      final sub = container.listen(discoverCategoriesProvider, (_, next) {
        if (next.hasValue && !completer.isCompleted) {
          completer.complete();
        }
      }, fireImmediately: true);
      addTearDown(sub.close);
      await completer.future;

      final value = container.read(discoverCategoriesProvider).value!;
      expect(
        value.any(
          (category) =>
              category.id == '${JokeCategory.firestorePrefix}proposed',
        ),
        isFalse,
      );
      expect(
        value.any(
          (category) =>
              category.id == '${JokeCategory.firestorePrefix}approved',
        ),
        isTrue,
      );
    });

    test('includes proposed categories when toggle enabled', () async {
      final adminSettings = _FakeAdminSettingsService(
        initialShowProposedCategories: true,
      );
      final container = ProviderContainer(
        overrides: [
          adminSettingsServiceProvider.overrideWithValue(adminSettings),
          jokeCategoriesProvider.overrideWith(
            (ref) => Stream.value([
              JokeCategory(
                id: '${JokeCategory.firestorePrefix}approved',
                displayName: 'Approved',
                type: CategoryType.firestore,
                jokeDescriptionQuery: 'approved',
                state: JokeCategoryState.approved,
              ),
              JokeCategory(
                id: '${JokeCategory.firestorePrefix}proposed',
                displayName: 'Proposed',
                type: CategoryType.firestore,
                jokeDescriptionQuery: 'proposed',
                state: JokeCategoryState.proposed,
              ),
            ]),
          ),
        ],
      );
      addTearDown(container.dispose);

      final completer = Completer<void>();
      final sub = container.listen(discoverCategoriesProvider, (_, next) {
        if (next.hasValue && !completer.isCompleted) {
          completer.complete();
        }
      }, fireImmediately: true);
      addTearDown(sub.close);
      await completer.future;

      final value = container.read(discoverCategoriesProvider).value!;
      expect(
        value.any(
          (category) =>
              category.id == '${JokeCategory.firestorePrefix}proposed',
        ),
        isTrue,
      );
    });
  });
}

class _FakeAdminSettingsService implements AdminSettingsService {
  _FakeAdminSettingsService({bool initialShowProposedCategories = false})
    : adminOverrideShowBannerAd = false,
      showJokeDataSource = false,
      showProposedCategories = initialShowProposedCategories;

  bool adminOverrideShowBannerAd;
  bool showJokeDataSource;
  bool showProposedCategories;

  @override
  bool getAdminOverrideShowBannerAd() => adminOverrideShowBannerAd;

  @override
  Future<void> setAdminOverrideShowBannerAd(bool value) async {
    adminOverrideShowBannerAd = value;
  }

  @override
  bool getAdminShowJokeDataSource() => showJokeDataSource;

  @override
  Future<void> setAdminShowJokeDataSource(bool value) async {
    showJokeDataSource = value;
  }

  @override
  bool getAdminShowProposedCategories() => showProposedCategories;

  @override
  Future<void> setAdminShowProposedCategories(bool value) async {
    showProposedCategories = value;
  }
}

class _FakeJokeCategoryRepository implements JokeCategoryRepository {
  _FakeJokeCategoryRepository({
    required Stream<List<JokeCategory>> categoriesStream,
  }) : _categoriesStream = categoriesStream;

  final Stream<List<JokeCategory>> _categoriesStream;

  @override
  Stream<List<JokeCategory>> watchCategories() => _categoriesStream;

  @override
  Stream<JokeCategory?> watchCategory(String categoryId) =>
      throw UnimplementedError();

  @override
  Future<void> upsertCategory(JokeCategory category) =>
      throw UnimplementedError();

  @override
  Future<void> deleteCategory(String categoryId) => throw UnimplementedError();

  @override
  Stream<List<String>> watchCategoryImages(String categoryId) =>
      throw UnimplementedError();

  @override
  Future<void> addImageToCategory(String categoryId, String imageUrl) =>
      throw UnimplementedError();

  @override
  Future<void> deleteImageFromCategory(String categoryId, String imageUrl) =>
      throw UnimplementedError();

  @override
  Future<List<CategoryCachedJoke>> getCachedCategoryJokes(String categoryId) =>
      throw UnimplementedError();
}
