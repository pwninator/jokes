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

// Color ramp helper: 1 -> grey, 2 -> blue, 4 -> yellow, 7 -> orange, 10+ -> red
Color colorForBucket(
  int bucket, {
  required Color blue,
  required Color yellow,
  required Color orange,
  required Color red,
}) {
  if (bucket <= 1) return Colors.grey;
  if (bucket >= 10) return red;
  if (bucket <= 4) {
    // 2,3,4 -> blue to yellow
    final t = (bucket - 2) / (4 - 2);
    return Color.lerp(blue, yellow, t)!;
  }
  if (bucket <= 7) {
    final t = (bucket - 4) / (7 - 4); // 0..1
    return Color.lerp(yellow, orange, t)!;
  }
  // 8..9 -> orange->red
  final t = (bucket - 7) / (10 - 7); // 0..1 for 8..9
  return Color.lerp(orange, red, t)!;
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
  required Color blue,
  required Color yellow,
  required Color orange,
  required Color red,
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
    final color = bucket == -1
        ? textStyle.color
        : colorForBucket(
            bucket,
            blue: blue,
            yellow: yellow,
            orange: orange,
            red: red,
          );
    children.add(
      TextSpan(text: '$label\n', style: textStyle.copyWith(color: color)),
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
