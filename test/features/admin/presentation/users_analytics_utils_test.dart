import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

void main() {
  group('UsersAnalyticsUtils', () {
    group('calculateInverseColor', () {
      test('returns white for dark backgrounds', () {
        expect(calculateInverseColor(Colors.black), Colors.white);
        expect(calculateInverseColor(Colors.grey.shade800), Colors.white);
        expect(
          calculateInverseColor(Color.fromARGB(255, 0, 89, 255)),
          Colors.white,
        );
        expect(
          calculateInverseColor(Color.fromARGB(255, 255, 70, 57)),
          Colors.white,
        );
      });

      test('returns black for light backgrounds', () {
        expect(calculateInverseColor(Colors.white), Colors.black);
        expect(calculateInverseColor(Colors.grey), Colors.black);
        expect(calculateInverseColor(Colors.yellow), Colors.black);
        expect(calculateInverseColor(Colors.orange), Colors.black);
        expect(calculateInverseColor(Colors.lightBlue), Colors.black);
      });

      test('handles edge case colors correctly', () {
        // Test with a medium gray that should be close to the threshold
        expect(calculateInverseColor(Colors.grey.shade500), Colors.black);
        expect(calculateInverseColor(Colors.grey.shade600), Colors.white);
      });
    });

    group('getBackgroundColorForBucket', () {
      final colorStops = {
        1: Colors.grey,
        2: const Color.fromARGB(255, 0, 89, 255),
        4: Colors.yellow,
        7: Colors.orange,
        10: const Color.fromARGB(255, 255, 70, 57),
      };

      test('returns correct colors for defined buckets', () {
        expect(getBackgroundColorForBucket(1, colorStops), colorStops[1]!);
        expect(getBackgroundColorForBucket(2, colorStops), colorStops[2]!);
        expect(getBackgroundColorForBucket(4, colorStops), colorStops[4]!);
        expect(getBackgroundColorForBucket(7, colorStops), colorStops[7]!);
        expect(getBackgroundColorForBucket(10, colorStops), colorStops[10]!);
      });

      test('interpolates colors for undefined buckets', () {
        // Test interpolation between 2 and 4
        final color3 = getBackgroundColorForBucket(3, colorStops);
        expect(color3, Color.lerp(colorStops[2]!, colorStops[4]!, 0.5));

        // Test interpolation between 7 and 10
        final color8 = getBackgroundColorForBucket(8, colorStops);
        expect(color8, Color.lerp(colorStops[7]!, colorStops[10]!, 1 / 3));
      });
    });

    group('buildUsersAnalyticsTooltip', () {
      final colorStops = {
        1: Colors.grey,
        2: const Color.fromARGB(255, 0, 89, 255),
      };

      test('builds tooltip correctly', () {
        final date = DateTime.utc(2025, 1, 10, 12);
        final buckets = {1: 1, 2: 1};
        final textStyle = const TextStyle(fontSize: 12, color: Colors.black);

        final tooltipItem = buildUsersAnalyticsTooltip(
          date: date,
          buckets: buckets,
          textStyle: textStyle,
          colorStops: colorStops,
        );

        expect(tooltipItem.text, '');
        final children = tooltipItem.children;
        expect(children, isNotNull);
        children!;
        expect(children.length, 4);

        // Date
        expect(children[0].text, 'Jan 10\n');
        expect(children[0].style?.fontWeight, FontWeight.bold);

        // Total
        expect(children[1].text, 'Total: 2\n');
        expect(children[1].style?.color, textStyle.color);

        // Bucket 1
        final bucket1Span = children[2];
        expect(bucket1Span.text, '1: 1\n');
        expect(bucket1Span.style?.color, calculateInverseColor(colorStops[1]!));
        expect(bucket1Span.style?.backgroundColor, colorStops[1]!);

        // Bucket 2
        final bucket2Span = children[3];
        expect(bucket2Span.text, '2: 1');
        expect(bucket2Span.style?.color, calculateInverseColor(colorStops[2]!));
        expect(bucket2Span.style?.backgroundColor, colorStops[2]!);
      });
    });
  });
}
