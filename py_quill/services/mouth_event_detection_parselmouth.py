"""Mouth event detection using Praat/parselmouth formants."""

from __future__ import annotations

import math

import numpy as np
import parselmouth
from common.mouth_events import MouthEvent
from common.posable_character import MouthState
from services.mouth_event_detection_utils import (
  _CONFIDENCE_FULL_DURATION_SEC,
  _FRAME_MS,
  _HOP_MS,
  _MAX_SYLLABLE_SEC,
  _MIN_SYLLABLE_SEC,
  _SYLLABLE_PRE_ROLL_SEC,
  _build_rhythmic_frames_simple,
  _compute_rms_threshold,
  _detect_state_transitions,
  _fill_nans_with_median,
  _find_runs,
  _frame_times,
  _load_audio,
  _merge_boundary_candidates,
)

# Praat formant thresholds (mouth-shape classification)
_F1_OPEN_THRESHOLD_HZ = 650.0
_F2_O_THRESHOLD_HZ = 1400.0
_F0_MEDIAN_BASE_HZ = 170.0
_F1_OPEN_PITCH_SCALE_MAX = 1.5


def detect_mouth_events_parselmouth(wav_bytes: bytes) -> list[MouthEvent]:
  return _detect_segments_with_confidence_parselmouth(wav_bytes)


def _detect_segments_with_confidence_parselmouth(
  wav_bytes: bytes, ) -> list[MouthEvent]:
  """Detect mouth events with confidence scores using praat-parselmouth."""
  y, sr = _load_audio(wav_bytes)
  if y.size == 0 or sr <= 0:
    return []

  frame_length = max(1, int(round(sr * (_FRAME_MS / 1000.0))))
  hop_length = max(1, int(round(sr * (_HOP_MS / 1000.0))))

  hop_sec = hop_length / float(sr)
  n_samples = int(y.size)
  if n_samples <= 0:
    return []
  if n_samples < frame_length:
    n_frames = 1
  else:
    n_frames = 1 + (n_samples - frame_length) // hop_length

  frame_times = _frame_times(
    n_frames,
    hop_sec=hop_sec,
    sr=sr,
    frame_length=frame_length,
  )

  sound = parselmouth.Sound(
    y.astype(np.float64),
    sampling_frequency=float(sr),
  )

  intensity = sound.to_intensity(time_step=hop_sec)
  rms = np.zeros(n_frames, dtype=np.float64)
  for i, t in enumerate(frame_times):
    value_db = intensity.get_value(float(t))
    if value_db is None:
      continue
    try:
      db = float(value_db)
    except Exception:
      continue
    if not math.isfinite(db):
      continue
    # Convert dB-like intensity to an amplitude-like scale for percentile gating.
    rms[i] = 10.0**(db / 20.0)

  if float(rms.max()) <= 1e-12:
    return []

  rms_threshold = _compute_rms_threshold(rms)
  voiced_mask = rms >= rms_threshold
  if not np.any(voiced_mask):
    return []

  pitch = sound.to_pitch(time_step=hop_sec)
  f0 = np.full(n_frames, np.nan, dtype=np.float64)
  for i, t in enumerate(frame_times):
    value = pitch.get_value_at_time(float(t))
    if value is None:
      continue
    try:
      hz = float(value)
    except Exception:
      continue
    if hz > 0.0 and math.isfinite(hz):
      f0[i] = hz

  f1_open_threshold = _compute_f1_open_threshold_hz(
    f0,
    voiced_mask=voiced_mask,
  )

  formant = sound.to_formant_burg(time_step=hop_sec)

  f1 = np.full(n_frames, np.nan, dtype=np.float64)
  f2 = np.full(n_frames, np.nan, dtype=np.float64)
  for i, t in enumerate(frame_times):
    value_f1 = formant.get_value_at_time(1, float(t))
    if value_f1 is not None:
      try:
        f1[i] = float(value_f1)
      except Exception:
        pass

    value_f2 = formant.get_value_at_time(2, float(t))
    if value_f2 is not None:
      try:
        f2[i] = float(value_f2)
      except Exception:
        pass

  f1 = _fill_nans_with_median(f1, mask=voiced_mask)
  f2 = _fill_nans_with_median(f2, mask=voiced_mask)

  frame_states = _compute_frame_states_formants(
    f1=f1,
    f2=f2,
    rms=rms,
    rms_threshold=rms_threshold,
    f1_open_threshold=f1_open_threshold,
    f2_o_threshold=_F2_O_THRESHOLD_HZ,
  )

  boundary_frames = _find_all_boundaries_parselmouth(
    voiced_mask=voiced_mask,
    frame_states=frame_states,
    sr=sr,
    hop_length=hop_length,
  )

  return _create_segments_with_confidence_formants(
    boundary_frames=boundary_frames,
    frame_states=frame_states,
    f1=f1,
    f2=f2,
    rms=rms,
    sr=sr,
    hop_length=hop_length,
    rms_threshold=rms_threshold,
    f1_open_threshold=f1_open_threshold,
    f2_o_threshold=_F2_O_THRESHOLD_HZ,
  )


def _compute_f1_open_threshold_hz(
  f0: np.ndarray,
  *,
  voiced_mask: np.ndarray,
) -> float:
  voiced_f0 = f0[voiced_mask] if np.any(voiced_mask) else f0
  voiced_f0 = voiced_f0[np.isfinite(voiced_f0) & (voiced_f0 > 0.0)]
  if voiced_f0.size == 0:
    return _F1_OPEN_THRESHOLD_HZ

  median_f0 = float(np.median(voiced_f0))
  if median_f0 <= _F0_MEDIAN_BASE_HZ:
    return _F1_OPEN_THRESHOLD_HZ

  scale = math.sqrt(median_f0 / _F0_MEDIAN_BASE_HZ)
  scale = min(_F1_OPEN_PITCH_SCALE_MAX, max(1.0, float(scale)))
  return _F1_OPEN_THRESHOLD_HZ * scale


def _compute_frame_states_formants(
  *,
  f1: np.ndarray,
  f2: np.ndarray,
  rms: np.ndarray,
  rms_threshold: float,
  f1_open_threshold: float,
  f2_o_threshold: float,
) -> np.ndarray:
  n_frames = int(rms.size)
  states = np.empty(n_frames, dtype=object)

  for i in range(n_frames):
    if rms[i] < rms_threshold:
      states[i] = MouthState.CLOSED
      continue

    # Prioritized decision tree:
    #   1) High F1 => OPEN (jaw dropped)
    #   2) Low F2 => O (lip rounding)
    f1_val = float(f1[i])
    f2_val = float(f2[i])

    if f1_val >= f1_open_threshold:
      states[i] = MouthState.OPEN
    elif f2_val <= f2_o_threshold:
      states[i] = MouthState.O
    else:
      states[i] = MouthState.OPEN

  return states


def _find_all_boundaries_parselmouth(
  *,
  voiced_mask: np.ndarray,
  frame_states: np.ndarray,
  sr: int,
  hop_length: int,
) -> list[int]:
  segments = _find_runs(voiced_mask)
  starts = [start for start, _ in segments]
  transitions = _detect_state_transitions(frame_states)
  rhythmic = _build_rhythmic_frames_simple(
    voiced_mask=voiced_mask,
    sr=sr,
    hop_length=hop_length,
  )
  return _merge_boundary_candidates(
    candidates=starts + transitions + rhythmic,
    sr=sr,
    hop_length=hop_length,
  )


def _create_segments_with_confidence_formants(
  *,
  boundary_frames: list[int],
  frame_states: np.ndarray,
  f1: np.ndarray,
  f2: np.ndarray,
  rms: np.ndarray,
  sr: int,
  hop_length: int,
  rms_threshold: float,
  f1_open_threshold: float,
  f2_o_threshold: float,
) -> list[MouthEvent]:
  if not boundary_frames:
    return []

  segments: list[MouthEvent] = []
  n_frames = int(rms.size)
  rms_max = float(rms.max())
  hop_sec = hop_length / float(sr)
  f1_clear_distance = 350.0
  f2_clear_distance = 600.0

  for i, start_frame in enumerate(boundary_frames):
    if start_frame >= n_frames:
      continue
    if rms[start_frame] < rms_threshold:
      continue

    mouth_shape = frame_states[start_frame]
    if mouth_shape == MouthState.CLOSED:
      continue

    next_boundary = boundary_frames[i + 1] if i + 1 < len(
      boundary_frames) else n_frames
    max_search_frames = int(round(_MAX_SYLLABLE_SEC * sr / hop_length))
    end_frame = min(next_boundary, start_frame + max_search_frames)
    if end_frame <= start_frame:
      continue

    segment_f1 = f1[start_frame:end_frame]
    segment_f2 = f2[start_frame:end_frame]
    segment_rms = rms[start_frame:end_frame]
    mean_f1 = (float(np.mean(segment_f1)) if segment_f1.size > 0 else 0.0)
    mean_f2 = (float(np.mean(segment_f2)) if segment_f2.size > 0 else 0.0)
    mean_rms = (float(np.mean(segment_rms)) if segment_rms.size > 0 else 0.0)

    start_time = max(0.0, (start_frame * hop_sec) - _SYLLABLE_PRE_ROLL_SEC)
    end_time = end_frame * hop_sec
    if end_time - start_time < _MIN_SYLLABLE_SEC:
      end_time = start_time + _MIN_SYLLABLE_SEC
    duration = end_time - start_time

    if mouth_shape == MouthState.OPEN:
      if mean_f1 >= f1_open_threshold:
        formant_score = min(1.0,
                            (mean_f1 - f1_open_threshold) / f1_clear_distance)
      else:
        formant_score = min(
          1.0, max(0.0, (mean_f2 - f2_o_threshold) / f2_clear_distance))
    else:
      formant_score = min(1.0, (f2_o_threshold - mean_f2) / f2_clear_distance)

    energy_score = min(1.0, mean_rms / rms_max) if rms_max > 0 else 0.0
    duration_score = min(
      1.0,
      duration / _CONFIDENCE_FULL_DURATION_SEC,
    ) if _CONFIDENCE_FULL_DURATION_SEC > 0 else 1.0
    confidence = (0.5 * formant_score + 0.3 * energy_score +
                  0.2 * duration_score)
    confidence = min(1.0, max(0.0, float(confidence)))

    segments.append(
      MouthEvent(
        start_time=start_time,
        end_time=end_time,
        mouth_shape=mouth_shape,
        confidence=confidence,
        mean_centroid=mean_f2,
        mean_rms=mean_rms,
      ))

  return segments

