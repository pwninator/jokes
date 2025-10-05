import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/admin/application/user_stats_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

class UserJokesChart extends ConsumerWidget {
  const UserJokesChart({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final histogramAsync = ref.watch(usersJokesHistogramProvider);
    return histogramAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, st) => Center(child: Text('Error: $e')),
      data: (hist) {
        if (hist.orderedDaysUsed.isEmpty) {
          return const Center(child: Text('No users matching criteria'));
        }

        final theme = Theme.of(context);
        final colorStops = {
          0: Colors.grey,
          1: Colors.red,
          5: Colors.orange,
          10: Colors.yellow,
          20: Colors.green,
          50: Colors.cyan,
          100: Colors.blue,
          101: Colors.purple,
        };

        final groups = <BarChartGroupData>[];
        for (int i = 0; i < hist.orderedDaysUsed.length; i++) {
          final daysUsed = hist.orderedDaysUsed[i];
          final buckets = hist.countsByDaysUsed[daysUsed]!;
          final totalUsers = buckets.values.fold(0, (a, b) => a + b);

          double runningPercentage = 0;
          final stacks = <BarChartRodStackItem>[];
          final sortedJokeBuckets = buckets.keys.toList()..sort();

          for (final jokeBucket in sortedJokeBuckets) {
            final count = buckets[jokeBucket]!;
            final percentage = (count / totalUsers) * 100;
            final color = getBackgroundColorForBucket(jokeBucket, colorStops);
            stacks.add(
              BarChartRodStackItem(
                runningPercentage,
                runningPercentage + percentage,
                color,
              ),
            );
            runningPercentage += percentage;
          }

          groups.add(
            BarChartGroupData(
              x: i,
              barRods: [
                BarChartRodData(
                  toY: runningPercentage,
                  rodStackItems: stacks,
                  width: 20,
                  borderRadius: BorderRadius.zero,
                ),
              ],
            ),
          );
        }

        final chart = BarChart(
          BarChartData(
            maxY: 100,
            gridData: FlGridData(show: true, drawVerticalLine: false),
            borderData: FlBorderData(show: false),
            barTouchData: BarTouchData(
              enabled: true,
              touchTooltipData: BarTouchTooltipData(
                tooltipPadding: const EdgeInsets.all(8),
                fitInsideVertically: true,
                fitInsideHorizontally: true,
                getTooltipItem: (group, groupIndex, rod, rodIndex) {
                  final daysUsed = hist.orderedDaysUsed[group.x];
                  final buckets = hist.countsByDaysUsed[daysUsed]!;
                  final textStyle =
                      Theme.of(context).textTheme.bodySmall ??
                      const TextStyle();
                  return buildUsersJokesTooltip(
                    daysUsed: daysUsed,
                    buckets: buckets,
                    textStyle: textStyle,
                    colorStops: colorStops,
                  );
                },
              ),
            ),
            titlesData: FlTitlesData(
              leftTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 48,
                  getTitlesWidget: (value, meta) {
                    if (value % 20 != 0) return const SizedBox.shrink();
                    return SideTitleWidget(
                      axisSide: meta.axisSide,
                      child: Text('${value.toInt()}%'),
                    );
                  },
                ),
              ),
              rightTitles: const AxisTitles(
                sideTitles: SideTitles(showTitles: false),
              ),
              topTitles: const AxisTitles(
                sideTitles: SideTitles(showTitles: false),
              ),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  getTitlesWidget: (value, meta) {
                    final index = value.toInt();
                    if (index >= hist.orderedDaysUsed.length) {
                      return const SizedBox.shrink();
                    }
                    final daysUsed = hist.orderedDaysUsed[index];
                    return SideTitleWidget(
                      axisSide: meta.axisSide,
                      space: 8,
                      child: Text(
                        daysUsed.toString(),
                        style: theme.textTheme.bodySmall,
                      ),
                    );
                  },
                ),
              ),
            ),
            barGroups: groups,
          ),
        );

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'User Activity: Jokes Viewed vs. Days Used',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Users who last used the app before yesterday.',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 12),
            JokesLegend(colorStops: colorStops),
            const SizedBox(height: 12),
            SizedBox(height: 300, child: chart),
          ],
        );
      },
    );
  }
}

class JokesLegend extends StatelessWidget {
  final Map<int, Color> colorStops;
  const JokesLegend({super.key, required this.colorStops});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final labels = {
      0: '0',
      1: '1',
      5: '5',
      10: '10',
      20: '20',
      30: '30',
      40: '40',
      50: '50',
      70: '70',
      100: '100',
      101: '101+',
    };
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final b in [...jokeViewBuckets, 101])
          LegendChip(
            backgroundColor: getBackgroundColorForBucket(b, colorStops),
            label: labels[b]!,
            textStyle: theme.textTheme.bodySmall,
          ),
      ],
    );
  }
}

BarTooltipItem buildUsersJokesTooltip({
  required int daysUsed,
  required Map<int, int> buckets,
  required TextStyle textStyle,
  required Map<int, Color> colorStops,
}) {
  final totalUsers = buckets.values.fold(0, (a, b) => a + b);
  final children = <TextSpan>[
    TextSpan(
      text: 'Days Used: $daysUsed\n',
      style: textStyle.copyWith(fontWeight: FontWeight.bold),
    ),
    TextSpan(
      text: 'Total Users: $totalUsers\n',
      style: textStyle.copyWith(fontWeight: FontWeight.bold),
    ),
  ];

  final labels = {
    0: '0',
    1: '1',
    5: '2-5',
    10: '6-10',
    20: '11-20',
    30: '21-30',
    40: '31-40',
    50: '41-50',
    70: '51-70',
    100: '71-100',
    101: '101+',
  };

  final sortedBuckets = buckets.keys.toList()..sort();
  for (final bucket in sortedBuckets) {
    final count = buckets[bucket]!;
    final percentage = ((count / totalUsers) * 100).toStringAsFixed(1);
    final label = labels[bucket]!;
    final background = getBackgroundColorForBucket(bucket, colorStops);
    final foreground = calculateInverseColor(background);
    children.add(
      TextSpan(
        text: '$label: $count ($percentage%)\n',
        style: textStyle.copyWith(
          color: foreground,
          backgroundColor: background,
        ),
      ),
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
