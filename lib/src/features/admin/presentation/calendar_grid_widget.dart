import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_widgets.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

class CalendarGridWidget extends ConsumerStatefulWidget {
  final JokeScheduleBatch? batch; // null means no batch exists for this month
  final DateTime monthDate; // The month this calendar represents

  const CalendarGridWidget({
    super.key,
    required this.batch,
    required this.monthDate,
  });

  @override
  ConsumerState<CalendarGridWidget> createState() => _CalendarGridWidgetState();
}

class _CalendarGridWidgetState extends ConsumerState<CalendarGridWidget> {
  static const weekdayHeaders = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  OverlayEntry? _popupOverlay;

  @override
  void dispose() {
    _hidePopup();
    super.dispose();
  }

  void _showPopup(BuildContext cellContext, String dayKey) {
    final joke = widget.batch?.jokes[dayKey];
    if (joke == null) return;

    final RenderBox cellRenderBox = cellContext.findRenderObject() as RenderBox;
    final cellPosition = cellRenderBox.localToGlobal(Offset.zero);
    final cellSize = cellRenderBox.size;

    _popupOverlay = OverlayEntry(
      builder:
          (context) => GestureDetector(
            onTap: _hidePopup,
            behavior: HitTestBehavior.translucent,
            child: Material(
              color: Colors.transparent,
              child: Stack(
                children: [
                  CalendarCellPopup(
                    joke: joke,
                    dayLabel: dayKey,
                    cellPosition: cellPosition,
                    cellSize: cellSize,
                  ),
                ],
              ),
            ),
          ),
    );

    Overlay.of(context).insert(_popupOverlay!);
  }

  void _hidePopup() {
    _popupOverlay?.remove();
    _popupOverlay = null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final daysInMonth =
        DateTime(widget.monthDate.year, widget.monthDate.month + 1, 0).day;
    final firstWeekday =
        DateTime(widget.monthDate.year, widget.monthDate.month, 1).weekday %
        7; // 0=Sunday

    return Column(
      children: [
        // Weekday headers
        SizedBox(
          height: 32,
          child: Row(
            children:
                weekdayHeaders
                    .map(
                      (day) => Expanded(
                        child: Center(
                          child: Text(
                            day,
                            style: theme.textTheme.labelSmall?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: theme.colorScheme.onSurface.withValues(
                                alpha: 0.7,
                              ),
                            ),
                          ),
                        ),
                      ),
                    )
                    .toList(),
          ),
        ),

        const SizedBox(height: 4),

        // Calendar grid
        AspectRatio(
          aspectRatio: 7 / 6, // 7 columns, up to 6 rows
          child: GridView.builder(
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              childAspectRatio: 1.0,
              crossAxisSpacing: 2,
              mainAxisSpacing: 2,
            ),
            itemCount: 42, // 6 weeks maximum
            itemBuilder: (context, index) {
              final dayNumber = index - firstWeekday + 1;
              if (dayNumber < 1 || dayNumber > daysInMonth) {
                return const SizedBox.shrink();
              }

              return _buildCalendarCell(context, dayNumber);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildCalendarCell(BuildContext context, int dayNumber) {
    final dayKey = dayNumber.toString().padLeft(2, '0');
    final joke = widget.batch?.jokes[dayKey];
    final hasJoke = joke != null;
    final theme = Theme.of(context);

    // Check if this cell represents today's date
    final now = DateTime.now();
    final isToday =
        widget.monthDate.year == now.year &&
        widget.monthDate.month == now.month &&
        dayNumber == now.day;

    return Builder(
      builder: (cellContext) {
        return GestureDetector(
          onLongPressStart:
              hasJoke ? (_) => _showPopup(cellContext, dayKey) : null,
          onLongPressEnd: (_) => _hidePopup(),
          child: Container(
            decoration: BoxDecoration(
              color:
                  hasJoke
                      ? theme.colorScheme.primary.withValues(alpha: 1.0)
                      : theme.colorScheme.primary.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(6),
              border:
                  isToday
                      ? Border.all(color: Colors.blue, width: 5)
                      : Border.all(width: 0),
            ),
            child: Center(
              child: Text(
                dayNumber.toString(),
                style: TextStyle(
                  color:
                      hasJoke
                          ? theme.colorScheme.onPrimary
                          : theme.colorScheme.onPrimaryContainer.withValues(
                            alpha: 0.3,
                          ),
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
