import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';

void main() {
  group('SeasonalCategoryFeed.isActiveOn', () {
    test('halloween is active inclusively between start and end month/day', () {
      expect(
        SeasonalCategoryFeed.halloween.isActiveOn(DateTime(2025, 10, 24)),
        isFalse,
      );
      expect(
        SeasonalCategoryFeed.halloween.isActiveOn(DateTime(2025, 10, 25)),
        isTrue,
      );
      expect(
        SeasonalCategoryFeed.halloween.isActiveOn(DateTime(2025, 10, 31)),
        isTrue,
      );
      expect(
        SeasonalCategoryFeed.halloween.isActiveOn(DateTime(2025, 11, 1)),
        isTrue,
      );
      expect(
        SeasonalCategoryFeed.halloween.isActiveOn(DateTime(2025, 11, 2)),
        isFalse,
      );
    });
  });
}
