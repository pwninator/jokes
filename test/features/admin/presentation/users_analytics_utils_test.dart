import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

void main() {
  group('UsersAnalyticsUtils', () {
    group('getColorsForBucket', () {
      final colorStops = {
        1: const ColorStop(
            background: Colors.grey, foreground: Colors.white),
        2: const ColorStop(
            background: Color.fromARGB(255, 0, 89, 255),
            foreground: Colors.white),
        4: const ColorStop(
            background: Colors.yellow, foreground: Colors.black),
        7: const ColorStop(
            background: Colors.orange, foreground: Colors.black),
        10: const ColorStop(
            background: Color.fromARGB(255, 255, 70, 57),
            foreground: Colors.white),
      };

      test('returns correct colors for defined buckets', () {
        expect(
            getColorsForBucket(1, colorStops).background.value, colorStops[1]!.background.value);
        expect(
            getColorsForBucket(2, colorStops).background.value, colorStops[2]!.background.value);
        expect(
            getColorsForBucket(4, colorStops).background.value, colorStops[4]!.background.value);
        expect(
            getColorsForBucket(7, colorStops).background.value, colorStops[7]!.background.value);
        expect(
            getColorsForBucket(10, colorStops).background.value, colorStops[10]!.background.value);
      });

      test('interpolates colors for undefined buckets', () {
        // Test interpolation between 2 and 4
        final color3 = getColorsForBucket(3, colorStops);
        expect(color3.background,
            Color.lerp(colorStops[2]!.background, colorStops[4]!.background, 0.5));
        expect(color3.foreground,
            Color.lerp(colorStops[2]!.foreground, colorStops[4]!.foreground, 0.5));

        // Test interpolation between 7 and 10
        final color8 = getColorsForBucket(8, colorStops);
        expect(color8.background,
            Color.lerp(colorStops[7]!.background, colorStops[10]!.background, 1/3));
        expect(color8.foreground,
            Color.lerp(colorStops[7]!.foreground, colorStops[10]!.foreground, 1/3));
      });
    });

    group('buildUsersAnalyticsTooltip', () {
      final colorStops = {
        1: const ColorStop(
            background: Colors.grey, foreground: Colors.white),
        2: const ColorStop(
            background: Color.fromARGB(255, 0, 89, 255),
            foreground: Colors.white),
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
        expect((children[0] as TextSpan).text, 'Jan 10\n');
        expect((children[0] as TextSpan).style?.fontWeight, FontWeight.bold);

        // Total
        expect((children[1] as TextSpan).text, 'Total: 2\n');
        expect((children[1] as TextSpan).style?.color, textStyle.color);

        // Bucket 1
        final bucket1Span = children[2] as TextSpan;
        expect(bucket1Span.text, '1: 1\n');
        expect(bucket1Span.style?.color, colorStops[1]!.foreground);
        expect(bucket1Span.style?.backgroundColor, colorStops[1]!.background);

        // Bucket 2
        final bucket2Span = children[3] as TextSpan;
        expect(bucket2Span.text, '2: 1');
        expect(bucket2Span.style?.color, colorStops[2]!.foreground);
        expect(bucket2Span.style?.backgroundColor, colorStops[2]!.background);
      });
    });
  });
}
