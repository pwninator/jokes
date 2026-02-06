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
_MIN_EVENT_SEC = 0.04
_MIN_SHAPE_SEC = 0.04


def detect_mouth_events_tts_timing(
  word_timings: list[audio_timing.WordTiming], ) -> list[MouthEvent]:
  """Generate mouth events from word timings."""
  events: list[tuple[MouthState, float, float]] = []

  for timing in word_timings:
    word = (timing.word or "").strip()
    if not word:
      continue

    word_t0 = float(timing.start_time)
    word_t1 = float(timing.end_time)

    shape_tokens = transcript_alignment.text_to_weighted_shapes(
      word.replace("-", " "))
    if not shape_tokens:
      continue

    tokens_with_windows = _allocate_weighted_windows(
      word_t0,
      word_t1,
      shape_tokens,
      min_shape_sec=_MIN_SHAPE_SEC,
    )
    word_events = [(shape, float(t0), float(t1))
                   for (shape, _w), (t0, t1) in tokens_with_windows if t1 > t0]
    logger.info(f"Events for word: {word}: {word_events}")
    events.extend(word_events)

  return _to_mouth_events(_postprocess(events))


def _allocate_weighted_windows(
  t0: float,
  t1: float,
  tokens: list[tuple[MouthState, float]],
  *,
  min_shape_sec: float,
) -> list[tuple[tuple[MouthState, float], tuple[float, float]]]:
  """Allocate contiguous windows for weighted shape tokens.

  Enforces a minimum duration per token by dropping lowest-weight tokens when
  needed.
  """
  t0 = float(t0)
  t1 = float(t1)
  min_shape_sec = float(min_shape_sec)
  duration = float(t1 - t0)
  if duration <= 0.0:
    return []
  if duration < min_shape_sec:
    return []

  normalized = [(shape, float(weight)) for shape, weight in tokens
                if float(weight) > 0.0]
  if not normalized:
    return []

  def _drop_one(entries: list[tuple[MouthState, float]]) -> None:
    drop_index = min(
      range(len(entries)),
      key=lambda idx: (float(entries[idx][1]), -int(idx)),
    )
    entries.pop(drop_index)

  while normalized and duration < (len(normalized) * min_shape_sec):
    _drop_one(normalized)

  if not normalized:
    return []

  base = float(len(normalized)) * min_shape_sec
  remaining = max(0.0, duration - base)
  total_weight = float(sum(w for _, w in normalized))
  if total_weight <= 0.0:
    total_weight = float(len(normalized))

  cursor = float(t0)
  out: list[tuple[tuple[MouthState, float], tuple[float, float]]] = []
  for shape, weight in normalized:
    w = float(weight)
    portion = (remaining * (w / total_weight)) if total_weight > 0 else 0.0
    seg = min_shape_sec + float(portion)
    start = float(cursor)
    end = float(cursor) + float(seg)
    out.append(((shape, weight), (start, end)))
    cursor = end

  # Ensure last boundary is exact.
  if out:
    last_token, (start, _end) = out[-1]
    out[-1] = (last_token, (float(start), float(t1)))
  return out


def _postprocess(
  events: list[tuple[MouthState, float, float]],
) -> list[tuple[MouthState, float, float]]:
  """Fill gaps with CLOSED events."""
  if not events:
    return []

  events_sorted = sorted(events, key=lambda e: (e[1], e[2]))

  filled: list[tuple[MouthState, float, float]] = []
  for state, t0, t1 in events_sorted:
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
