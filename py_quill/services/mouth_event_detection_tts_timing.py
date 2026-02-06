"""Mouth event detection using character-level timing data.

This implementation uses provider-supplied character timings to derive word
windows, then evenly distributes g2p-derived mouth shapes across each word
window.

Expected input:
- Alignment characters should already be sanitized (no bracket directives, and
  only in-word punctuation like apostrophes/hyphens when applicable).
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
  timing: audio_timing.CharacterAlignment, ) -> list[MouthEvent]:
  """Generate mouth events from character alignment timings."""
  chars = timing.characters
  starts = timing.character_start_times_seconds
  ends = timing.character_end_times_seconds

  if (len(chars) != len(starts)) or (len(chars) != len(ends)):
    return []

  events: list[tuple[MouthState, float, float]] = []

  word_spans = _iter_word_spans(chars)
  if not word_spans:
    return _to_mouth_events(_postprocess(events))

  for word_start, word_end in word_spans:
    word = "".join(chars[word_start:word_end]).strip()
    if not word:
      continue

    word_t0 = float(starts[word_start])
    word_t1 = float(ends[word_end - 1])

    shapes = transcript_alignment.text_to_shapes(word.replace("-", " "))
    if not shapes:
      continue

    windows = _split_window_even(word_t0, word_t1, len(shapes))
    word_events = [(shape, float(t0), float(t1))
                   for shape, (t0, t1) in zip(shapes, windows) if t1 > t0]
    logger.info(f"Events for word: {word}: {word_events}")
    events.extend(word_events)

  return _to_mouth_events(_postprocess(events))

def _iter_word_spans(characters: list[str]) -> list[tuple[int, int]]:
  """Return `(start, end)` character index spans for word-like runs.

  A "word" here is a contiguous run of `isalnum()` characters, apostrophes, and
  hyphens. Leading/trailing punctuation is trimmed off the span.
  """
  spans: list[tuple[int, int]] = []
  n = len(characters)
  i = 0
  while i < n:
    if not _is_word_char(characters[i]):
      i += 1
      continue

    start = i
    while i < n and _is_word_char(characters[i]):
      i += 1
    end = i

    while start < end and characters[start] in ("'", "-"):
      start += 1
    while start < end and characters[end - 1] in ("'", "-"):
      end -= 1
    if start < end:
      spans.append((start, end))

  return spans


def _is_word_char(ch: str) -> bool:
  if not ch:
    return False
  if ch.isalnum():
    return True
  return ch in ("'", "-")


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
