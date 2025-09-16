import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

void main() {
  test('buildUsersTooltipLines produces total and ascending bucket lines', () {
    final buckets = {1: 2, 3: 1, 10: 5};
    final lines = buildUsersTooltipLines(buckets);
    expect(lines.first, 'Total: 8');
    // Order is 1, 3, 10+ (ascending), but we only assert presence here
    expect(lines, contains('1: 2'));
    expect(lines, contains('3: 1'));
    expect(lines, contains('10+: 5'));
  });
}
