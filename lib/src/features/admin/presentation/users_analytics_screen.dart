import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/providers/user_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_utils.dart';

class UsersAnalyticsScreen extends ConsumerWidget implements TitledScreen {
  const UsersAnalyticsScreen({super.key});

  @override
  String get title => 'Users';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final histogramAsync = ref.watch(usersLoginHistogramProvider);

    return AdaptiveAppBarScreen(
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
            final blue = const Color.fromARGB(255, 0, 89, 255);
            final yellow = Colors.yellow;
            final orange = Colors.orange;
            final red = const Color.fromARGB(255, 255, 70, 57);

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
                final color = colorForBucket(
                  bucket,
                  blue: blue,
                  yellow: yellow,
                  orange: orange,
                  red: red,
                );
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
                      final textStyle = Theme.of(context).textTheme.bodySmall ??
                          const TextStyle();

                      return buildUsersAnalyticsTooltip(
                        date: date,
                        buckets: buckets,
                        textStyle: textStyle,
                        blue: blue,
                        yellow: yellow,
                        orange: orange,
                        red: red,
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

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Legend(blue: blue, yellow: yellow, orange: orange, red: red),
                const SizedBox(height: 12),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SizedBox(width: width, height: 260, child: chart),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  final Color blue;
  final Color yellow;
  final Color orange;
  final Color red;
  const _Legend({
    required this.blue,
    required this.yellow,
    required this.orange,
    required this.red,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final items = List.generate(10, (i) => i + 1);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final b in items)
          _LegendChip(
            color: colorForBucket(
              b,
              blue: blue,
              yellow: yellow,
              orange: orange,
              red: red,
            ),
            label: b == 10 ? '10+' : '$b',
            textStyle: theme.textTheme.bodySmall,
          ),
      ],
    );
  }
}

class _LegendChip extends StatelessWidget {
  final Color color;
  final String label;
  final TextStyle? textStyle;
  const _LegendChip({required this.color, required this.label, this.textStyle});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha((255 * 0.8).round()),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(label, style: textStyle?.copyWith(color: Colors.black)),
    );
  }
}
