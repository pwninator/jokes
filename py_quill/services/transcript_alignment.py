"""Transcript-based mouth shape alignment for improved lip-sync animation.

This module aligns text-derived mouth shapes with audio-detected segments using
dynamic programming to produce more accurate lip-sync than audio-only detection.
"""

from __future__ import annotations

from typing import Sequence

from common.mouth_events import MouthEvent
from common.posable_character import MouthState
from g2p_en import G2p

# Initialize G2P converter (lazy-loaded singleton)
_g2p: G2p | None = None


def _get_g2p() -> G2p:
  """Get or create the G2P converter singleton."""
  global _g2p
  if _g2p is None:
    _g2p = G2p()
  return _g2p


# ARPABET vowel to MouthState mapping.
# Diphthongs are mapped to their component shapes.
_VOWEL_TO_SHAPES: dict[str, list[MouthState]] = {
  # Monophthongs - OPEN (wide/spread)
  "AA": [MouthState.OPEN],  # odd, father
  "AE": [MouthState.OPEN],  # at, bat
  "AH": [MouthState.OPEN],  # hut, butter
  "EH": [MouthState.OPEN],  # bet, dress
  "ER": [MouthState.OPEN],  # bird, turn
  "IH": [MouthState.OPEN],  # bit, kit
  "IY": [MouthState.OPEN],  # beat, fleece
  # Monophthongs - O (rounded)
  "AO": [MouthState.O],  # caught, all
  "UH": [MouthState.O],  # book, put
  "UW": [MouthState.O],  # boot, goose
  # Diphthongs
  "AW": [MouthState.OPEN,
         MouthState.O],  # cow, how (starts open, ends rounded)
  "AY": [MouthState.OPEN],  # my, bite (stays open)
  "EY": [MouthState.OPEN],  # say, bait (stays spread)
  "OW": [MouthState.O],  # go, boat (stays rounded)
  "OY": [MouthState.O, MouthState.OPEN],  # boy, coin (rounded to spread)
}

# DP alignment cost parameters
_COST_MATCH = 0.0
_COST_MISMATCH_BASE = 1.0
_COST_SKIP_TEXT = 0.8  # Cost to skip a text shape (should be high - prefer matching)
_COST_SKIP_AUDIO = 0.6  # Cost to skip an audio segment (noise/filler)

# Confidence thresholds for DP decisions
_HIGH_CONFIDENCE_THRESHOLD = 0.7
_LOW_CONFIDENCE_THRESHOLD = 0.3


def _get_confidence(segment: MouthEvent) -> float:
  confidence = segment.confidence
  if confidence is None:
    return 0.5
  return float(confidence)


def text_to_shapes(text: str) -> list[MouthState]:
  """Convert text to a sequence of expected mouth shapes.

  Uses grapheme-to-phoneme conversion to extract vowels, then maps each vowel
  to its corresponding mouth shape(s). Diphthongs are expanded into their
  component shapes.

  Args:
    text: Input text to convert.

  Returns:
    List of MouthState values representing expected mouth shapes in order.
  """
  if not text or not text.strip():
    return []

  g2p = _get_g2p()
  phonemes = g2p(text)

  shapes: list[MouthState] = []
  for phoneme in phonemes:
    # Strip stress markers (0, 1, 2) from vowels
    base_phoneme = phoneme.rstrip("012")
    if base_phoneme in _VOWEL_TO_SHAPES:
      shapes.extend(_VOWEL_TO_SHAPES[base_phoneme])

  return shapes


def align_shapes(
  text_shapes: Sequence[MouthState],
  audio_segments: Sequence[MouthEvent],
) -> list[MouthEvent]:
  """Align text-derived shapes with audio-detected segments using DP.

  Uses dynamic programming to find the optimal alignment between the expected
  text shapes and the detected audio segments. The alignment minimizes total
  cost while respecting confidence scores.

  Args:
    text_shapes: Sequence of expected mouth shapes from text.
    audio_segments: Sequence of audio-detected segments with confidence.

  Returns:
    List of MouthEvent objects with final mouth shapes and timing.
  """
  if not audio_segments:
    return []

  if not text_shapes:
    # No text shapes - fall back to audio shapes
    return [
      MouthEvent(
        start_time=seg.start_time,
        end_time=seg.end_time,
        mouth_shape=seg.mouth_shape,
        confidence=seg.confidence,
        mean_centroid=seg.mean_centroid,
        mean_rms=seg.mean_rms,
      ) for seg in audio_segments
    ]

  # Use the internal function that preserves text_shapes for result building
  return _align_shapes_with_text_list(list(text_shapes), list(audio_segments))


def _dp_align(
  text_shapes: list[MouthState],
  audio_segments: list[MouthEvent],
) -> list[tuple[int, int | None]]:
  """Run dynamic programming to find optimal alignment.

  Returns a list of (audio_index, text_index_or_none) pairs indicating which
  text shape (if any) is assigned to each audio segment.

  The DP state is (text_idx, audio_idx) representing "we've consumed text_idx
  text shapes and audio_idx audio segments". We want to minimize total cost
  to reach (len(text), len(audio)).

  Args:
    text_shapes: List of expected mouth shapes from text.
    audio_segments: List of audio-detected segments.

  Returns:
    List of (audio_index, text_index_or_none) pairs.
  """
  n_text = len(text_shapes)
  n_audio = len(audio_segments)

  # dp[t][a] = minimum cost to consume t text shapes and a audio segments
  # Using infinity for unreachable states
  inf = float("inf")
  dp = [[inf] * (n_audio + 1) for _ in range(n_text + 1)]
  dp[0][0] = 0.0

  # parent[t][a] = (prev_t, prev_a, action) where action is:
  # "match" - consumed both text[t-1] and audio[a-1]
  # "skip_text" - skipped text[t-1]
  # "skip_audio" - skipped audio[a-1]
  parent: list[list[tuple[int, int, str] | None]] = [[None] * (n_audio + 1)
                                                     for _ in range(n_text + 1)
                                                     ]

  for t in range(n_text + 1):
    for a in range(n_audio + 1):
      if dp[t][a] == inf:
        continue

      current_cost = dp[t][a]

      # Option 1: Match text[t] with audio[a] (if both available)
      if t < n_text and a < n_audio:
        match_cost = _compute_match_cost(text_shapes[t], audio_segments[a])
        new_cost = current_cost + match_cost
        if new_cost < dp[t + 1][a + 1]:
          dp[t + 1][a + 1] = new_cost
          parent[t + 1][a + 1] = (t, a, "match")

      # Option 2: Skip text shape (text vowel not pronounced distinctly)
      if t < n_text:
        new_cost = current_cost + _COST_SKIP_TEXT
        if new_cost < dp[t + 1][a]:
          dp[t + 1][a] = new_cost
          parent[t + 1][a] = (t, a, "skip_text")

      # Option 3: Skip audio segment (noise/filler, use audio's own shape)
      if a < n_audio:
        skip_cost = _compute_skip_audio_cost(audio_segments[a])
        new_cost = current_cost + skip_cost
        if new_cost < dp[t][a + 1]:
          dp[t][a + 1] = new_cost
          parent[t][a + 1] = (t, a, "skip_audio")

  # Find the best ending state (must consume all audio, may have leftover text)
  best_t = 0
  best_cost = inf
  for t in range(n_text + 1):
    if dp[t][n_audio] < best_cost:
      best_cost = dp[t][n_audio]
      best_t = t

  # Backtrack to reconstruct alignment
  alignment: list[tuple[int, int | None]] = []
  t, a = best_t, n_audio

  while parent[t][a] is not None:
    prev_t, prev_a, action = parent[t][a]
    if action == "match":
      # audio[prev_a] matched with text[prev_t]
      alignment.append((prev_a, prev_t))
    elif action == "skip_audio":
      # audio[prev_a] was skipped (use its own shape)
      alignment.append((prev_a, None))
    # skip_text doesn't produce an alignment entry (text shape dropped)
    t, a = prev_t, prev_a

  alignment.reverse()
  return alignment


def _compute_match_cost(
  text_shape: MouthState,
  audio_segment: MouthEvent,
) -> float:
  """Compute the cost of matching a text shape with an audio segment.

  When shapes agree, cost is zero. When they disagree, cost depends on
  audio confidence - high confidence disagreement is more costly.

  Args:
    text_shape: Expected shape from text.
    audio_segment: Detected audio segment with shape and confidence.

  Returns:
    Cost value (lower is better).
  """
  if text_shape == audio_segment.mouth_shape:
    return _COST_MATCH

  # Shapes disagree - cost depends on audio confidence
  # High confidence audio that disagrees = high cost (audio is probably right)
  # Low confidence audio that disagrees = low cost (text is probably right)
  return _COST_MISMATCH_BASE * _get_confidence(audio_segment)


def _compute_skip_audio_cost(audio_segment: MouthEvent) -> float:
  """Compute the cost of skipping an audio segment (treating it as noise).

  High confidence segments are more costly to skip (they're likely real speech).
  Low confidence segments are cheap to skip (likely noise/filler).

  Args:
    audio_segment: The audio segment to potentially skip.

  Returns:
    Cost value (lower is better).
  """
  # Base skip cost adjusted by confidence
  return _COST_SKIP_AUDIO + (0.5 * _get_confidence(audio_segment))


def align_with_text(
  text: str,
  audio_segments: Sequence[MouthEvent],
) -> list[MouthEvent]:
  """Convenience function to align text directly with audio segments.

  Combines text_to_shapes() and align_shapes() into a single call.

  Args:
    text: Input text (e.g., "Hey, want to hear a joke?").
    audio_segments: Audio-detected segments with confidence scores.

  Returns:
    List of MouthEvent objects with refined mouth shapes.
  """
  text_shapes = text_to_shapes(text)
  return _align_shapes_with_text_list(text_shapes, list(audio_segments))


def _align_shapes_with_text_list(
  text_shapes: list[MouthState],
  audio_segments: list[MouthEvent],
) -> list[MouthEvent]:
  """Internal alignment that preserves text_shapes for result building.

  Args:
    text_shapes: List of expected mouth shapes from text.
    audio_segments: List of audio-detected segments.

  Returns:
    List of MouthEvent objects with final mouth shapes.
  """
  if not audio_segments:
    return []

  if not text_shapes:
    return [
      MouthEvent(
        start_time=seg.start_time,
        end_time=seg.end_time,
        mouth_shape=seg.mouth_shape,
        confidence=seg.confidence,
        mean_centroid=seg.mean_centroid,
        mean_rms=seg.mean_rms,
      ) for seg in audio_segments
    ]

  alignment = _dp_align(text_shapes, audio_segments)

  # Build result with correct shapes
  result: list[MouthEvent] = []
  for audio_idx, text_idx in alignment:
    audio_seg = audio_segments[audio_idx]

    if text_idx is not None:
      # Matched - use text shape
      result.append(
        MouthEvent(
          start_time=audio_seg.start_time,
          end_time=audio_seg.end_time,
          mouth_shape=text_shapes[text_idx],
          confidence=audio_seg.confidence,
          mean_centroid=audio_seg.mean_centroid,
          mean_rms=audio_seg.mean_rms,
        ))
    else:
      # Skipped - use audio shape
      result.append(
        MouthEvent(
          start_time=audio_seg.start_time,
          end_time=audio_seg.end_time,
          mouth_shape=audio_seg.mouth_shape,
          confidence=audio_seg.confidence,
          mean_centroid=audio_seg.mean_centroid,
          mean_rms=audio_seg.mean_rms,
        ))

  return result
