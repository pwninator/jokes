import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';

void main() {
  group('discoverCategoriesProvider', () {
    test(
      'includes popular, Halloween seasonal, and approved categories',
      () async {
        final container = ProviderContainer(
          overrides: [
            // Mock feed screen status to false (daily jokes tile won't appear)
            feedScreenStatusProvider.overrideWithValue(false),
            // Provide some approved categories from Firestore
            jokeCategoriesProvider.overrideWith(
              (ref) => Stream.value([
                JokeCategory(
                  id: '${JokeCategory.firestorePrefix}1',
                  displayName: 'Cats',
                  type: CategoryType.search,
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

        // Expect 3 categories: popular + halloween + cats (no daily)
        expect(categories.length, 3);
        // Daily should NOT be present when feed is enabled
        expect(
          categories.any((category) => category.type == CategoryType.daily),
          isFalse,
        );
        // Popular should be present
        expect(
          categories.any((category) => category.type == CategoryType.popular),
          isTrue,
        );
        // Halloween should be present
        expect(
          categories.any(
            (category) =>
                category.type == CategoryType.seasonal &&
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

    test('includes daily jokes tile when feed screen is enabled', () async {
      final container = ProviderContainer(
        overrides: [
          // Mock feed screen status to true (daily jokes tile will appear)
          feedScreenStatusProvider.overrideWithValue(true),
          // Provide some approved categories from Firestore
          jokeCategoriesProvider.overrideWith(
            (ref) => Stream.value([
              JokeCategory(
                id: '${JokeCategory.firestorePrefix}1',
                displayName: 'Cats',
                type: CategoryType.search,
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

      // Expect all 4 categories: daily + popular + halloween + cats
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
              category.type == CategoryType.seasonal &&
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
    });
  });
}
