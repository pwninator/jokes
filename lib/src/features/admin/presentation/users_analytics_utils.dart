/// Build tooltip lines for a stacked bar that represents users per days-used bucket.
/// First line is the total, followed by one line per non-zero bucket in ascending
/// order (1 up to 10+), so higher days-used appears at the bottom like the stack.
List<String> buildUsersTooltipLines(Map<int, int> buckets) {
  final total = buckets.values.fold<int>(0, (a, b) => a + b);
  final lines = <String>['Total: $total'];
  for (int bucket = 1; bucket <= 10; bucket++) {
    final count = buckets[bucket] ?? 0;
    if (count <= 0) continue;
    final label = bucket == 10 ? '10+' : '$bucket';
    lines.add('$label: $count');
  }
  return lines;
}
