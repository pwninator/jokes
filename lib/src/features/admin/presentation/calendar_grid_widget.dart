import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_schedule_widgets.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
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

    // Get the scheduleId from the ref
    final scheduleId = ref.read(selectedScheduleProvider);

    _popupOverlay = OverlayEntry(
      builder: (context) => Material(
        color: Colors.transparent,
        child: Stack(
          children: [
            // Semi-transparent background to capture taps outside the popup
            Positioned.fill(
              child: GestureDetector(
                onTap: _hidePopup,
                behavior: HitTestBehavior.translucent,
                child: Container(color: Colors.black.withValues(alpha: 0.5)),
              ),
            ),
            CalendarCellPopup(
              joke: joke,
              dayLabel: dayKey,
              cellPosition: cellPosition,
              cellSize: cellSize,
              onClose: _hidePopup,
              batch: widget.batch,
              scheduleId: scheduleId,
            ),
          ],
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
    final daysInMonth = DateTime(
      widget.monthDate.year,
      widget.monthDate.month + 1,
      0,
    ).day;
    final firstWeekday =
        DateTime(widget.monthDate.year, widget.monthDate.month, 1).weekday %
        7; // 0=Sunday

    // Calculate the actual number of rows needed for this month
    final totalCells = firstWeekday + daysInMonth;
    final numberOfRows = (totalCells / 7).ceil();
    final itemCount = numberOfRows * 7;

    return Column(
      children: [
        // Weekday headers
        SizedBox(
          height: 32,
          child: Row(
            children: weekdayHeaders
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
          aspectRatio:
              7 /
              numberOfRows, // Dynamic aspect ratio based on actual rows needed
          child: GridView.builder(
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              childAspectRatio: 1.0,
              crossAxisSpacing: 2,
              mainAxisSpacing: 2,
            ),
            itemCount:
                itemCount, // Dynamic item count based on actual rows needed
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
          onTap: hasJoke ? () => _showPopup(cellContext, dayKey) : null,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(6),
              border: isToday ? Border.all(color: Colors.blue, width: 3) : null,
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Stack(
                children: [
                  // Background - either image thumbnail or solid color
                  if (hasJoke && joke.setupImageUrl != null)
                    // Show thumbnail image
                    CachedJokeImage(
                      imageUrl: joke.setupImageUrl,
                      width: double.infinity,
                      height: double.infinity,
                      fit: BoxFit.cover,
                      showLoadingIndicator: false,
                      showErrorIcon: false,
                    )
                  else
                    // Show solid color background for empty dates or jokes without images
                    Container(
                      width: double.infinity,
                      height: double.infinity,
                      color: hasJoke
                          ? theme.colorScheme.primary.withValues(alpha: 1.0)
                          : theme.colorScheme.primary.withValues(alpha: 0.2),
                    ),

                  // Semi-transparent overlay for better text readability on images
                  if (hasJoke && joke.setupImageUrl != null)
                    Container(
                      width: double.infinity,
                      height: double.infinity,
                      color: Colors.black.withValues(alpha: 0.3),
                    ),

                  // Day number text
                  Center(
                    child: Text(
                      dayNumber.toString(),
                      style: TextStyle(
                        color: hasJoke && joke.setupImageUrl != null
                            ? Colors
                                  .white // White text on image with dark overlay
                            : hasJoke
                            ? theme.colorScheme.onPrimary
                            : theme.colorScheme.onPrimaryContainer.withValues(
                                alpha: 0.3,
                              ),
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        shadows: hasJoke && joke.setupImageUrl != null
                            ? [
                                Shadow(
                                  offset: const Offset(1, 1),
                                  blurRadius: 2,
                                  color: Colors.black.withValues(alpha: 0.8),
                                ),
                              ]
                            : null,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
