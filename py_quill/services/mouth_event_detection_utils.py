"""Shared helpers for mouth event detection methodologies."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from common.posable_character import MouthState

# Frame and hop settings
_FRAME_MS = 25
_HOP_MS = 10

# Syllable timing settings
_MIN_SYLLABLE_SEC = 0.04
_MAX_SYLLABLE_SEC = 0.18
_SYLLABLE_PRE_ROLL_SEC = 0.02

# Voice detection settings
_MIN_RMS_PERCENTILE = 20

# Fallback and merging settings
_FALLBACK_FLAP_SEC = 0.12
_BOUNDARY_MERGE_SEC = 0.06

# Confidence scoring settings
_CONFIDENCE_MIN_DURATION_SEC = 0.03  # Below this, confidence drops
_CONFIDENCE_FULL_DURATION_SEC = 0.08  # Above this, duration doesn't help


def _load_audio(wav_bytes: bytes) -> tuple[np.ndarray, int]:
  """Load audio from WAV bytes, converting to mono float32."""
  with sf.SoundFile(io.BytesIO(wav_bytes)) as sound_file:
    y = sound_file.read(dtype="float32", always_2d=True)
    sr = int(sound_file.samplerate)
  if y.size == 0:
    return np.zeros((0, ), dtype=np.float32), sr
  if y.shape[1] > 1:
    y = np.mean(y, axis=1, keepdims=True)
  return y[:, 0], sr


def _find_runs(mask: np.ndarray) -> list[tuple[int, int]]:
  """Find contiguous runs of True values in a boolean mask.

  Returns:
    List of (start_frame, end_frame) tuples where end_frame is exclusive.
  """
  runs: list[tuple[int, int]] = []
  i = 0
  n = mask.size
  while i < n:
    if not mask[i]:
      i += 1
      continue
    start = i
    while i < n and mask[i]:
      i += 1
    runs.append((start, i))
  return runs


def _detect_state_transitions(frame_states: np.ndarray) -> list[int]:
  """Find frames where mouth state transitions within voiced segments.

  Only detects O <-> OPEN transitions (not CLOSED transitions, which are
  handled by voiced segment boundaries).
  """
  transitions: list[int] = []
  prev_voiced_state: MouthState | None = None

  for i, state in enumerate(frame_states):
    if state == MouthState.CLOSED:
      prev_voiced_state = None
      continue

    if prev_voiced_state is None:
      # Entering voiced segment - not a transition, handled elsewhere
      prev_voiced_state = state
      continue

    if state != prev_voiced_state:
      # State changed within voiced segment
      transitions.append(i)
      prev_voiced_state = state
    else:
      prev_voiced_state = state

  return transitions


def _compute_rms_threshold(rms: np.ndarray) -> float:
  rms_percentile = float(np.percentile(rms, _MIN_RMS_PERCENTILE))
  rms_max = float(rms.max())
  return max(rms_percentile, rms_max * 0.01)


def _frame_times(
  n_frames: int,
  *,
  hop_sec: float,
  sr: int,
  frame_length: int,
) -> np.ndarray:
  center_offset = (frame_length / 2.0) / float(sr) if sr > 0 else 0.0
  return (np.arange(n_frames, dtype=np.float64) * hop_sec) + center_offset


def _fill_nans_with_median(
  values: np.ndarray,
  *,
  mask: np.ndarray | None = None,
) -> np.ndarray:
  if values.size == 0:
    return values
  finite_mask = np.isfinite(values)
  if mask is not None:
    finite_mask = finite_mask & mask
  if not np.any(finite_mask):
    return np.nan_to_num(values, nan=0.0)
  median = float(np.median(values[finite_mask]))
  filled = values.copy()
  filled[~np.isfinite(filled)] = median
  return filled


def _build_rhythmic_frames_simple(
  *,
  voiced_mask: np.ndarray,
  sr: int,
  hop_length: int,
) -> list[int]:
  segments = _find_runs(voiced_mask)
  flap_frames = int(round(_FALLBACK_FLAP_SEC * sr / hop_length))
  flap_frames = max(1, flap_frames)
  candidates: list[int] = []
  for start_frame, end_frame in segments:
    frame = start_frame
    while frame < end_frame:
      candidates.append(frame)
      frame += flap_frames
  return candidates


def _merge_boundary_candidates(
  *,
  candidates: list[int],
  sr: int,
  hop_length: int,
) -> list[int]:
  if not candidates:
    return []
  merge_frames = int(round(_BOUNDARY_MERGE_SEC * sr / hop_length))
  merge_frames = max(1, merge_frames)
  sorted_frames = sorted(set(int(f) for f in candidates if f >= 0))
  if not sorted_frames:
    return []
  merged: list[int] = [sorted_frames[0]]
  for frame in sorted_frames[1:]:
    if frame - merged[-1] >= merge_frames:
      merged.append(frame)
  return merged

