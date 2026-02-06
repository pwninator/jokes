"""Mouth event detection using TTS word timings.

This implementation expects a word-timed alignment (already sanitized), then
evenly distributes g2p-derived mouth shapes across each word window.
"""

from __future__ import annotations

from common import audio_timing
from common.mouth_events import MouthEvent
from common.posable_character import MouthState
from firebase_functions import logger
from services import transcript_alignment

_CLOSE_GAP_SEC = 0.08
_SMALL_GAP_HOLD_SEC = 0.035
_MIN_EVENT_SEC = 0.03


def detect_mouth_events_tts_timing(
  word_timings: list[audio_timing.WordTiming],
) -> list[MouthEvent]:
  """Generate mouth events from word timings."""
  events: list[tuple[MouthState, float, float]] = []

  for timing in word_timings:
    word = (timing.word or "").strip()
    if not word:
      continue

    word_t0 = float(timing.start_time)
    word_t1 = float(timing.end_time)

    shapes = transcript_alignment.text_to_shapes(word.replace("-", " "))
    if not shapes:
      continue

    windows = _split_window_even(word_t0, word_t1, len(shapes))
    word_events = [(shape, float(t0), float(t1))
                   for shape, (t0, t1) in zip(shapes, windows) if t1 > t0]
    logger.info(f"Events for word: {word}: {word_events}")
    events.extend(word_events)

  return _to_mouth_events(_postprocess(events))


def _split_window_even(
  t0: float,
  t1: float,
  parts: int,
) -> list[tuple[float, float]]:
  if parts <= 0:
    return []

  t0 = float(t0)
  t1 = float(t1)
  if parts == 1:
    return [(t0, t1)]

  duration = max(0.0, t1 - t0)
  if duration <= 0.0:
    return [(t0, t1) for _ in range(parts)]

  step = duration / float(parts)
  out: list[tuple[float, float]] = []
  for i in range(parts):
    a = t0 + (i * step)
    b = t0 + ((i + 1) * step)
    out.append((float(a), float(b)))
  return out


def _postprocess(
  events: list[tuple[MouthState, float, float]],
) -> list[tuple[MouthState, float, float]]:
  """Merge adjacent same-state events and fill gaps with CLOSED events."""
  if not events:
    return []

  events_sorted = sorted(events, key=lambda e: (e[1], e[2]))

  merged: list[tuple[MouthState, float, float]] = [events_sorted[0]]
  for state, t0, t1 in events_sorted[1:]:
    prev_state, prev_t0, prev_t1 = merged[-1]
    if t0 <= prev_t1 and state == prev_state:
      merged[-1] = (prev_state, prev_t0, max(prev_t1, t1))
      continue
    merged.append((state, t0, t1))

  filled: list[tuple[MouthState, float, float]] = []
  for state, t0, t1 in merged:
    if filled:
      prev_state, prev_t0, prev_t1 = filled[-1]
      gap = t0 - prev_t1
      if gap > _CLOSE_GAP_SEC:
        filled.append((MouthState.CLOSED, prev_t1, t0))
      elif gap > 0 and gap <= _SMALL_GAP_HOLD_SEC:
        filled[-1] = (prev_state, prev_t0, t0)
    filled.append((state, t0, t1))

  return [(s, t0, t1) for s, t0, t1 in filled if (t1 - t0) >= _MIN_EVENT_SEC]


def _to_mouth_events(
  events: list[tuple[MouthState, float, float]], ) -> list[MouthEvent]:
  """Convert internal `(state, t0, t1)` tuples to `MouthEvent` objects."""
  return [
    MouthEvent(
      start_time=float(t0),
      end_time=float(t1),
      mouth_shape=state,
      confidence=1.0,
      mean_centroid=None,
      mean_rms=None,
    ) for state, t0, t1 in events
  ]
