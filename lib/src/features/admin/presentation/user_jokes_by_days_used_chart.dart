import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/admin/application/user_stats_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

import 'user_jokes_chart.dart';

class UserJokesByDaysUsedChart extends ConsumerWidget {
  const UserJokesByDaysUsedChart({super.key});

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

          double runningTotal = 0;
          final stacks = <BarChartRodStackItem>[];
          final sortedJokeBuckets = buckets.keys.toList()..sort();

          for (final jokeBucket in sortedJokeBuckets) {
            final count = buckets[jokeBucket]!.toDouble();
            final color = getBackgroundColorForBucket(jokeBucket, colorStops);
            stacks.add(
              BarChartRodStackItem(
                runningTotal,
                runningTotal + count,
                color,
              ),
            );
            runningTotal += count;
          }

          groups.add(
            BarChartGroupData(
              x: i,
              barRods: [
                BarChartRodData(
                  toY: runningTotal,
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
            maxY: (hist.maxUsersInADaysUsedBucket * 1.1)
                .clamp(1, double.infinity),
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
                  return buildUsersJokesCountTooltip(
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
                sideTitles: SideTitles(showTitles: true, reservedSize: 48),
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
              'User Distribution by Jokes Viewed',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Absolute number of users, grouped by days used.',
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