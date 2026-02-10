"""Discrete timelines for scriptable video rendering.

Phase 1 focuses on segment-based (stepwise) timelines, which cover:
- mouth state over time
- eye open/closed over time (future)
- active image selection over time
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Generic, Iterable, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Segment(Generic[T]):
  """A half-open value span used by `SegmentTimeline`.

  The rendering code treats each segment as active from `start_time` through
  `end_time` inclusively for sampling stability at exact frame boundaries.
  """
  start_time: float
  end_time: float
  value: T

  def __post_init__(self) -> None:
    """Validate normalized segment bounds."""
    if float(self.end_time) < float(self.start_time):
      raise ValueError("Segment end_time must be >= start_time")


class SegmentTimeline(Generic[T]):
  """A piecewise-constant timeline of `(value, start, end)` segments."""

  def __init__(self, segments: Sequence[Segment[T]] | None = None):
    """Store segments sorted by start/end to support binary search queries."""
    self._segments: list[Segment[T]] = list(segments or [])
    self._segments.sort(key=lambda s: (float(s.start_time), float(s.end_time)))
    self._starts: list[float] = [float(s.start_time) for s in self._segments]

  @property
  def segments(self) -> list[Segment[T]]:
    """Return a defensive copy of timeline segments."""
    return list(self._segments)

  def is_empty(self) -> bool:
    """Return `True` when the timeline has no segments."""
    return not self._segments

  def value_at(self, time_sec: float, *, default: T) -> T:
    """Resolve the active value at `time_sec`.

    The call is O(log n): it bisects segment starts, then validates whether the
    candidate segment still covers the requested time.
    """
    time_sec = float(time_sec)
    if not self._segments:
      return default

    idx = bisect_right(self._starts, time_sec) - 1
    if idx < 0:
      return default

    seg = self._segments[idx]
    if time_sec <= float(seg.end_time):
      return seg.value
    return default

  @staticmethod
  def from_value_segments(
    segments: Iterable[tuple[T, float, float]], ) -> "SegmentTimeline[T]":
    """Build a timeline from simple `(value, start, end)` tuples."""
    out: list[Segment[T]] = []
    for value, start, end in segments:
      out.append(
        Segment(start_time=float(start), end_time=float(end), value=value))
    return SegmentTimeline(out)
