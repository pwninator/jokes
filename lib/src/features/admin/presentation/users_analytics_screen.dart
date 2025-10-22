import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/user_jokes_chart.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

class UsersAnalyticsScreen extends ConsumerWidget implements TitledScreen {
  const UsersAnalyticsScreen({super.key});

  @override
  String get title => 'Users';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final histogramAsync = ref.watch(usersLoginHistogramProvider);

    return AppBarConfiguredScreen(
      title: title,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: histogramAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => Center(child: Text('Error: $e')),
          data: (hist) {
            if (hist.orderedDates.isEmpty) {
              return const Center(child: Text('No users'));
            }

            final theme = Theme.of(context);
            final colorStops = {
              1: Colors.grey,
              2: Colors.blue,
              5: Colors.yellow,
              7: Colors.orange,
              10: Colors.red,
            };

            // Build chart groups
            final groups = <BarChartGroupData>[];
            final labels = <int, String>{};
            final dateCount = hist.orderedDates.length;

            for (int i = 0; i < dateCount; i++) {
              final d = hist.orderedDates[i];
              final buckets = hist.countsByDateThenBucket[d]!;
              // Build stacked segments bottom->top with higher buckets at bottom.
              // Iterate 10..1 but still stack from current bottom 'running'.
              double running = 0;
              final stacks = <BarChartRodStackItem>[];
              for (int bucket = 10; bucket >= 1; bucket--) {
                final value = (buckets[bucket] ?? 0).toDouble();
                if (value <= 0) continue;
                final color = getBackgroundColorForBucket(bucket, colorStops);
                stacks.add(
                  BarChartRodStackItem(running, running + value, color),
                );
                running += value;
              }
              groups.add(
                BarChartGroupData(
                  x: i,
                  barRods: [
                    BarChartRodData(
                      toY: running,
                      rodStackItems: stacks,
                      width: 10,
                      borderRadius: BorderRadius.zero,
                      color: theme.colorScheme.primary, // fallback
                    ),
                  ],
                ),
              );

              // Bottom labels for some ticks to reduce clutter
              if (i == 0 ||
                  i == dateCount - 1 ||
                  i % max(1, dateCount ~/ 8) == 0) {
                labels[i] = formatShortDate(d);
              }
            }

            final chart = BarChart(
              BarChartData(
                maxY: (hist.maxDailyTotal.toDouble() * 1.1).clamp(
                  1,
                  double.infinity,
                ),
                gridData: FlGridData(show: true, drawVerticalLine: false),
                borderData: FlBorderData(show: false),
                barTouchData: BarTouchData(
                  enabled: true,
                  touchTooltipData: BarTouchTooltipData(
                    tooltipPadding: const EdgeInsets.all(8),
                    fitInsideVertically: true,
                    fitInsideHorizontally: true,
                    getTooltipItem: (group, groupIndex, rod, rodIndex) {
                      final idx = group.x;
                      final date = hist.orderedDates[idx];
                      final buckets = hist.countsByDateThenBucket[date] ?? {};
                      final textStyle =
                          Theme.of(context).textTheme.bodySmall ??
                          const TextStyle();

                      return buildUsersAnalyticsTooltip(
                        date: date,
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
                        final idx = value.toInt();
                        final label = labels[idx];
                        if (label == null) return const SizedBox.shrink();
                        return SideTitleWidget(
                          axisSide: meta.axisSide,
                          space: 8,
                          child: Text(label, style: theme.textTheme.bodySmall),
                        );
                      },
                    ),
                  ),
                ),
                barGroups: groups,
              ),
              swapAnimationDuration: const Duration(milliseconds: 200),
            );

            // Allow horizontal scroll for many days
            final width = max(
              dateCount * 14.0,
              MediaQuery.of(context).size.width - 32,
            );

            return SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Daily Active Users (Last Login)',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  Legend(colorStops: colorStops),
                  const SizedBox(height: 12),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SizedBox(width: width, height: 260, child: chart),
                  ),
                  const SizedBox(height: 32),
                  const UserJokesChart(),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
