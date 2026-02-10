"""Mouth timeline helpers."""

from __future__ import annotations

from common.mouth_events import MouthEvent
from common.posable_character import MouthState


def apply_forced_closures(
  syllables: list[MouthEvent],
  *,
  min_syllable_for_closure_sec: float = 0.05,
  closure_fraction: float = 0.25,
  min_closure_sec: float = 0.015,
  max_closure_sec: float = 0.04,
  max_gap_sec: float = 0.15,
) -> list[tuple[MouthState, float, float]]:
  """Apply forced mouth closures between consecutive same-shape syllables.

  This ensures each syllable has a visible effect by inserting brief CLOSED
  states between adjacent syllables with the same mouth shape.

  Args:
    syllables: List of detected syllables.
    min_syllable_for_closure_sec: Minimum syllable duration to consider for
      forced closures. Very short syllables skip closure insertion to avoid
      strobe effects.
    closure_fraction: Closure duration as a fraction of the shorter syllable.
    min_closure_sec: Minimum closure duration.
    max_closure_sec: Maximum closure duration.
    max_gap_sec: Maximum gap to insert a closure. Larger gaps are natural
      silence and don't need forced closures.

  Returns:
    Timeline of (MouthState, start_time, end_time) tuples, sorted by start_time.
  """
  if not syllables:
    return []

  timeline: list[tuple[MouthState, float, float]] = []

  for index, syllable in enumerate(syllables):
    syl_start = float(syllable.start_time)
    syl_end = float(syllable.end_time)
    syl_duration = float(syl_end - syl_start)

    # Check if we need to insert a closure before this syllable
    if index > 0:
      prev_syllable = syllables[index - 1]
      prev_duration = float(prev_syllable.end_time - prev_syllable.start_time)
      gap = float(syl_start - prev_syllable.end_time)

      should_insert_closure = (
        syllable.mouth_shape == prev_syllable.mouth_shape
        and syl_duration >= float(min_syllable_for_closure_sec)
        and prev_duration >= float(min_syllable_for_closure_sec)
        and gap <= float(max_gap_sec)
      )

      if should_insert_closure:
        closure_duration = float(closure_fraction) * float(
          min(syl_duration, prev_duration)
        )
        closure_duration = float(
          max(float(min_closure_sec), min(float(max_closure_sec), closure_duration))
        )

        if gap > 0:
          # Use the gap (if any) for the closure, up to closure_duration.
          closure_end = syl_start
          closure_start = max(float(prev_syllable.end_time), closure_end - closure_duration)
          timeline.append((MouthState.CLOSED, float(closure_start), float(closure_end)))
        else:
          # No gap: steal time from adjacent syllables.
          steal = closure_duration / 2.0
          prev_end = max(float(prev_syllable.start_time), float(prev_syllable.end_time) - steal)
          curr_start = min(float(syl_end), float(syl_start) + steal)

          # Update the previous syllable end if it was the last timeline entry.
          if timeline and timeline[-1][0] == prev_syllable.mouth_shape:
            prev_state, prev_start, _prev_end = timeline[-1]
            timeline[-1] = (prev_state, float(prev_start), float(prev_end))

          timeline.append((MouthState.CLOSED, float(prev_end), float(curr_start)))

          # Shift the current syllable start forward.
          syl_start = curr_start

    timeline.append((syllable.mouth_shape, float(syl_start), float(syl_end)))

  # Ensure sorted by start_time.
  timeline.sort(key=lambda entry: float(entry[1]))
  return timeline

