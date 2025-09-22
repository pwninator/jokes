import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

void main() {
  group('buildUsersTooltipLines', () {
    test('produces total and ascending bucket lines', () {
      final buckets = {1: 2, 3: 1, 10: 5};
      final lines = buildUsersTooltipLines(buckets);
      expect(lines, [
        ('Total: 8', -1),
        ('1: 2', 1),
        ('3: 1', 3),
        ('10+: 5', 10),
      ]);
    });

    test('handles empty buckets', () {
      final buckets = <int, int>{};
      final lines = buildUsersTooltipLines(buckets);
      expect(lines, [('Total: 0', -1)]);
    });
  });

  group('colorForBucket', () {
    final blue = const Color.fromARGB(255, 0, 89, 255);
    final yellow = Colors.yellow;
    final orange = Colors.orange;
    final red = const Color.fromARGB(255, 255, 70, 57);

    test('returns correct colors for buckets', () {
      expect(colorForBucket(1, blue: blue, yellow: yellow, orange: orange, red: red).value, Colors.grey.value);
      expect(colorForBucket(2, blue: blue, yellow: yellow, orange: orange, red: red).value, blue.value);
      expect(colorForBucket(4, blue: blue, yellow: yellow, orange: orange, red: red).value, yellow.value);
      expect(colorForBucket(7, blue: blue, yellow: yellow, orange: orange, red: red).value, orange.value);
      expect(colorForBucket(10, blue: blue, yellow: yellow, orange: orange, red: red).value, red.value);
    });
  });

  group('formatShortDate', () {
    test('formats date correctly', () {
      final date = DateTime.utc(2025, 1, 10, 12);
      expect(formatShortDate(date), 'Jan 10');
    });
  });

  group('buildUsersAnalyticsTooltip', () {
    final blue = const Color.fromARGB(255, 0, 89, 255);
    final yellow = Colors.yellow;
    final orange = Colors.orange;
    final red = const Color.fromARGB(255, 255, 70, 57);

    test('builds tooltip correctly', () {
      final date = DateTime.utc(2025, 1, 10, 12);
      final buckets = {1: 1, 2: 1};
      final textStyle = const TextStyle(fontSize: 12, color: Colors.black);

      final tooltipItem = buildUsersAnalyticsTooltip(
        date: date,
        buckets: buckets,
        textStyle: textStyle,
        blue: blue,
        yellow: yellow,
        orange: orange,
        red: red,
      );

      expect(tooltipItem.text, '');
      final children = tooltipItem.children;
      expect(children, isNotNull);
      children!;
      expect(children.length, 4);

      // Date
      expect((children[0] as TextSpan).text, 'Jan 10\n');
      expect((children[0] as TextSpan).style?.fontWeight, FontWeight.bold);

      // Total
      expect((children[1] as TextSpan).text, 'Total: 2\n');

      // Bucket 1
      final bucket1Span = children[2] as TextSpan;
      expect(bucket1Span.text, '1: 1\n');
      expect(bucket1Span.style?.color, colorForBucket(1, blue: blue, yellow: yellow, orange: orange, red: red));

      // Bucket 2
      final bucket2Span = children[3] as TextSpan;
      expect(bucket2Span.text, '2: 1');
      expect(bucket2Span.style?.color, colorForBucket(2, blue: blue, yellow: yellow, orange: orange, red: red));
    });
  });
}
