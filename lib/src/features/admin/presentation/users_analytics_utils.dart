import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

/// Build tooltip lines for a stacked bar that represents users per days-used bucket.
/// First line is the total, followed by one line per non-zero bucket in ascending
/// order (1 up to 10+), so higher days-used appears at the bottom like the stack.
/// Returns a list of (label, bucket) tuples.
List<(String, int)> buildUsersTooltipLines(Map<int, int> buckets) {
  final total = buckets.values.fold<int>(0, (a, b) => a + b);
  final lines = <(String, int)>[('Total: $total', -1)];
  for (int bucket = 1; bucket <= 10; bucket++) {
    final count = buckets[bucket] ?? 0;
    if (count <= 0) continue;
    final label = bucket == 10 ? '10+' : '$bucket';
    lines.add(('$label: $count', bucket));
  }
  return lines;
}

class ColorStop {
  final Color background;
  final Color foreground;
  const ColorStop({required this.background, required this.foreground});

  static ColorStop lerp(
      ColorStop a, ColorStop b, double t) {
    return ColorStop(
      background: Color.lerp(a.background, b.background, t)!,
      foreground: Color.lerp(a.foreground, b.foreground, t)!,
    );
  }
}

ColorStop getColorsForBucket(
  int bucket,
  Map<int, ColorStop> colorStops,
) {
  if (colorStops.containsKey(bucket)) {
    return colorStops[bucket]!;
  }

  final sortedKeys = colorStops.keys.toList()..sort();
  if (bucket < sortedKeys.first) return colorStops[sortedKeys.first]!;
  if (bucket > sortedKeys.last) return colorStops[sortedKeys.last]!;

  int p = 0;
  while (p < sortedKeys.length && sortedKeys[p] < bucket) {
    p++;
  }
  final prevKey = sortedKeys[p - 1];
  final nextKey = sortedKeys[p];
  final t = (bucket - prevKey) / (nextKey - prevKey);
  return ColorStop.lerp(colorStops[prevKey]!, colorStops[nextKey]!, t);
}

String formatShortDate(DateTime utcDay) {
  final d = utcDay.toLocal();
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return '${months[d.month - 1]} ${d.day}';
}

BarTooltipItem buildUsersAnalyticsTooltip({
  required DateTime date,
  required Map<int, int> buckets,
  required TextStyle textStyle,
  required Map<int, ColorStop> colorStops,
}) {
  final lines = buildUsersTooltipLines(buckets);

  // Date at top
  final dateText = formatShortDate(date);
  final children = <TextSpan>[
    TextSpan(
      text: '$dateText\n',
      style: textStyle.copyWith(fontWeight: FontWeight.bold),
    )
  ];

  // Total and color-coded bucket counts
  for (final lineData in lines) {
    final label = lineData.$1;
    final bucket = lineData.$2;
    final colors = bucket == -1
        ? ColorStop(
            background: Colors.transparent,
            foreground: textStyle.color ?? Colors.black)
        : getColorsForBucket(
            bucket,
            colorStops,
          );
    children.add(
      TextSpan(
          text: '$label\n',
          style: textStyle.copyWith(
            color: colors.foreground,
            backgroundColor: colors.background,
          )),
    );
  }
  if (children.isNotEmpty) {
    final last = children.last;
    children[children.length - 1] = TextSpan(
      text: last.text!.trimRight(),
      style: last.style,
    );
  }

  return BarTooltipItem(
    '',
    textStyle,
    children: children,
    textAlign: TextAlign.left,
  );
}

class Legend extends StatelessWidget {
  final Map<int, ColorStop> colorStops;
  const Legend({required this.colorStops});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final items = List.generate(10, (i) => i + 1);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final b in items)
          LegendChip(
            colors: getColorsForBucket(b, colorStops),
            label: b == 10 ? '10+' : '$b',
            textStyle: theme.textTheme.bodySmall,
          ),
      ],
    );
  }
}

class LegendChip extends StatelessWidget {
  final String label;
  final TextStyle? textStyle;
  final ColorStop colors;

  const LegendChip(
      {required this.label, required this.colors, this.textStyle});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: colors.background,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(label, style: textStyle?.copyWith(color: colors.foreground)),
    );
  }
}
