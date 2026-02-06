"""Mouth event detection using librosa audio features."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from common.mouth_events import MouthEvent
from common.posable_character import MouthState
from services.mouth_event_detection_utils import (
  _BOUNDARY_MERGE_SEC,
  _CONFIDENCE_FULL_DURATION_SEC,
  _CONFIDENCE_MIN_DURATION_SEC,
  _FALLBACK_FLAP_SEC,
  _FRAME_MS,
  _HOP_MS,
  _MAX_SYLLABLE_SEC,
  _MIN_RMS_PERCENTILE,
  _MIN_SYLLABLE_SEC,
  _SYLLABLE_PRE_ROLL_SEC,
  _detect_state_transitions,
  _find_runs,
  _load_audio,
)

# Onset detection settings
_ONSET_WAIT_MS = 80
_ONSET_DELTA = 0.2

# Centroid threshold settings
_O_CENTROID_PERCENTILE = 35
_MIN_CENTROID_SPREAD_HZ = 500.0
_ABSOLUTE_O_CENTROID_HZ = 1200.0
_HYSTERESIS_HZ = 200.0

# Smoothing settings
_CENTROID_SMOOTH_FRAMES = 3

# Confidence scoring settings
_CONFIDENCE_CENTROID_AMBIGUOUS_HZ = 1200.0  # Center of ambiguous zone
_CONFIDENCE_CENTROID_CLEAR_DISTANCE_HZ = 600.0  # Distance for full confidence


@dataclass
class _AudioFeatures:
  """Extracted audio features for syllable detection."""

  centroid: np.ndarray
  rms: np.ndarray
  onset_env: np.ndarray
  sr: int
  hop_length: int


@dataclass
class _Thresholds:
  """Computed thresholds for syllable detection."""

  rms_threshold: float
  centroid_threshold_to_o: float
  centroid_threshold_to_open: float


def detect_mouth_events_librosa(wav_bytes: bytes) -> list[MouthEvent]:
  return _detect_segments_with_confidence(wav_bytes)


def _detect_segments_with_confidence(wav_bytes: bytes) -> list[MouthEvent]:
  """Detect mouth events with confidence scores for transcript alignment."""
  y, sr = _load_audio(wav_bytes)
  if y.size == 0 or sr <= 0:
    return []

  features = _compute_features(y, sr)
  if float(features.rms.max()) <= 1e-6:
    return []

  thresholds = _compute_thresholds(features)
  frame_states = _compute_frame_states(features, thresholds)
  boundary_frames = _find_all_boundaries(features, thresholds, frame_states)

  return _create_segments_with_confidence(boundary_frames, frame_states,
                                          features, thresholds)


def _compute_features(y: np.ndarray, sr: int) -> _AudioFeatures:
  """Extract spectral centroid, RMS, and onset envelope from audio."""
  frame_length = max(1, int(round(sr * (_FRAME_MS / 1000.0))))
  hop_length = max(1, int(round(sr * (_HOP_MS / 1000.0))))

  onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

  centroid = librosa.feature.spectral_centroid(
    y=y,
    sr=sr,
    hop_length=hop_length,
    n_fft=frame_length,
  )[0]

  rms = librosa.feature.rms(
    y=y,
    frame_length=frame_length,
    hop_length=hop_length,
  )[0]

  # Smooth centroid to reduce noise
  if centroid.size >= _CENTROID_SMOOTH_FRAMES:
    kernel = np.ones(_CENTROID_SMOOTH_FRAMES) / _CENTROID_SMOOTH_FRAMES
    centroid = np.convolve(centroid, kernel, mode="same")

  return _AudioFeatures(
    centroid=centroid,
    rms=rms,
    onset_env=onset_env,
    sr=sr,
    hop_length=hop_length,
  )


def _compute_thresholds(features: _AudioFeatures) -> _Thresholds:
  """Compute RMS and centroid thresholds with hysteresis."""
  # Ensure minimum RMS threshold to filter out true silence
  rms_percentile = float(np.percentile(features.rms, _MIN_RMS_PERCENTILE))
  rms_max = float(features.rms.max())
  # Use at least 1% of max RMS as threshold to avoid treating noise as voice
  rms_threshold = max(rms_percentile, rms_max * 0.01)

  # Only use voiced frames for centroid statistics
  voiced_mask = features.rms >= rms_threshold
  centroid_source = (features.centroid[voiced_mask]
                     if np.any(voiced_mask) else features.centroid)

  # Check if centroid has enough spread for relative thresholding
  centroid_low = np.percentile(centroid_source, 10)
  centroid_high = np.percentile(centroid_source, 90)

  if (centroid_high - centroid_low) < _MIN_CENTROID_SPREAD_HZ:
    # Low spread: use absolute classification
    median_centroid = np.median(centroid_source)
    if median_centroid < _ABSOLUTE_O_CENTROID_HZ:
      # Deep/dull sound (like "hohoho") -> all O
      base_threshold = float("inf")
    else:
      # Bright sound (like "hahaha") -> all OPEN
      base_threshold = -1.0
  else:
    base_threshold = float(
      np.percentile(centroid_source, _O_CENTROID_PERCENTILE))

  # Apply hysteresis: two thresholds to prevent jitter
  half_hysteresis = _HYSTERESIS_HZ / 2.0
  return _Thresholds(
    rms_threshold=rms_threshold,
    centroid_threshold_to_o=base_threshold - half_hysteresis,
    centroid_threshold_to_open=base_threshold + half_hysteresis,
  )


def _compute_frame_states(
  features: _AudioFeatures,
  thresholds: _Thresholds,
) -> np.ndarray:
  """Compute per-frame mouth state with hysteresis.

  Returns:
    Array of MouthState values (as objects), one per frame.
    Unvoiced frames are marked as CLOSED.
  """
  n_frames = features.rms.size
  # Use object dtype to store MouthState enum values
  states = np.empty(n_frames, dtype=object)

  # Midpoint threshold for when entering from silence (no hysteresis needed)
  midpoint = (thresholds.centroid_threshold_to_o +
              thresholds.centroid_threshold_to_open) / 2.0

  current_state = MouthState.CLOSED

  for i in range(n_frames):
    if features.rms[i] < thresholds.rms_threshold:
      states[i] = MouthState.CLOSED
      current_state = MouthState.CLOSED
      continue

    centroid = float(features.centroid[i])

    if current_state == MouthState.CLOSED:
      # From silence: use midpoint
      current_state = (MouthState.O if centroid <= midpoint else MouthState.OPEN)
    elif current_state == MouthState.O:
      # Stay O until we exceed the "to open" threshold
      if centroid > thresholds.centroid_threshold_to_open:
        current_state = MouthState.OPEN
    else:
      # Stay OPEN until we drop below the "to o" threshold
      if centroid < thresholds.centroid_threshold_to_o:
        current_state = MouthState.O

    states[i] = current_state

  return states


def _find_all_boundaries(
  features: _AudioFeatures,
  thresholds: _Thresholds,
  frame_states: np.ndarray,
) -> list[int]:
  """Find all syllable boundary frames from onsets, transitions, and rhythm."""
  onset_frames = _detect_onset_frames(features)
  transition_frames = _detect_state_transitions(frame_states)
  rhythmic_frames = _build_rhythmic_frames(features, thresholds)

  return _merge_boundary_frames(onset_frames, transition_frames,
                                rhythmic_frames, features)


def _detect_onset_frames(features: _AudioFeatures) -> np.ndarray:
  """Detect onset frames using librosa."""
  if features.onset_env.size == 0 or float(features.onset_env.max()) <= 0:
    return np.array([], dtype=int)

  wait_frames = max(
    1,
    int(round((_ONSET_WAIT_MS / 1000.0) * features.sr / features.hop_length)),
  )
  return librosa.onset.onset_detect(
    onset_envelope=features.onset_env,
    sr=features.sr,
    hop_length=features.hop_length,
    units="frames",
    wait=wait_frames,
    delta=_ONSET_DELTA,
  )


def _build_rhythmic_frames(
  features: _AudioFeatures,
  thresholds: _Thresholds,
) -> list[int]:
  """Build fallback rhythmic boundary frames for sustained voiced segments."""
  voiced_mask = features.rms >= thresholds.rms_threshold
  segments = _find_runs(voiced_mask)

  flap_frames = int(
    round(_FALLBACK_FLAP_SEC * features.sr / features.hop_length))
  candidates: list[int] = []

  for start_frame, end_frame in segments:
    if end_frame <= start_frame:
      continue
    frame = start_frame
    while frame < end_frame:
      candidates.append(frame)
      frame += flap_frames

  return candidates


def _merge_boundary_frames(
  onset_frames: np.ndarray,
  transition_frames: list[int],
  rhythmic_frames: list[int],
  features: _AudioFeatures,
) -> list[int]:
  """Merge all boundary candidates, removing duplicates within merge window."""
  merge_frames = int(
    round(_BOUNDARY_MERGE_SEC * features.sr / features.hop_length))

  # Combine all candidates
  all_frames: list[int] = []
  all_frames.extend(onset_frames.tolist())
  all_frames.extend(transition_frames)
  all_frames.extend(rhythmic_frames)

  if not all_frames:
    return []

  all_frames.sort()

  # Merge nearby boundaries, prioritizing earlier ones
  merged: list[int] = [all_frames[0]]
  for frame in all_frames[1:]:
    if frame - merged[-1] >= merge_frames:
      merged.append(frame)

  return merged


def _create_segments_with_confidence(
  boundary_frames: list[int],
  frame_states: np.ndarray,
  features: _AudioFeatures,
  thresholds: _Thresholds,
) -> list[MouthEvent]:
  """Create MouthEvent objects with confidence scores from boundary frames."""
  if not boundary_frames:
    return []

  segments: list[MouthEvent] = []
  n_frames = features.rms.size
  rms_max = float(features.rms.max())

  for i, start_frame in enumerate(boundary_frames):
    if start_frame >= n_frames:
      continue
    if features.rms[start_frame] < thresholds.rms_threshold:
      continue

    mouth_shape = frame_states[start_frame]
    if mouth_shape == MouthState.CLOSED:
      continue

    # Determine end frame (same logic as _create_syllables)
    next_boundary = (boundary_frames[i + 1] if i +
                     1 < len(boundary_frames) else n_frames)
    end_frame = start_frame
    max_search_frames = int(
      round(_MAX_SYLLABLE_SEC * features.sr / features.hop_length))

    for j in range(start_frame,
                   min(next_boundary, start_frame + max_search_frames)):
      if j >= n_frames:
        break
      if features.rms[j] < thresholds.rms_threshold:
        break
      end_frame = j + 1

    if end_frame < next_boundary and end_frame < start_frame + max_search_frames:
      pass
    else:
      end_frame = min(next_boundary, start_frame + max_search_frames)

    # Compute segment statistics
    segment_centroid = features.centroid[start_frame:end_frame]
    segment_rms = features.rms[start_frame:end_frame]

    mean_centroid = (float(np.mean(segment_centroid))
                     if segment_centroid.size > 0 else 0.0)
    mean_rms = (float(np.mean(segment_rms)) if segment_rms.size > 0 else 0.0)

    # Convert to times
    start_time = max(
      0.0,
      librosa.frames_to_time(
        start_frame, sr=features.sr, hop_length=features.hop_length) -
      _SYLLABLE_PRE_ROLL_SEC,
    )
    end_time = librosa.frames_to_time(end_frame,
                                      sr=features.sr,
                                      hop_length=features.hop_length)

    if end_time - start_time < _MIN_SYLLABLE_SEC:
      end_time = start_time + _MIN_SYLLABLE_SEC

    duration = end_time - start_time

    # Compute confidence score
    confidence = _compute_segment_confidence(
      mean_centroid=mean_centroid,
      mean_rms=mean_rms,
      rms_max=rms_max,
      duration=duration,
    )

    segments.append(
      MouthEvent(
        start_time=start_time,
        end_time=end_time,
        mouth_shape=mouth_shape,
        confidence=confidence,
        mean_centroid=mean_centroid,
        mean_rms=mean_rms,
      ))

  return segments


def _compute_segment_confidence(
  *,
  mean_centroid: float,
  mean_rms: float,
  rms_max: float,
  duration: float,
) -> float:
  """Compute confidence score for a segment based on audio characteristics."""
  # Centroid extremity: distance from ambiguous zone
  centroid_distance = abs(mean_centroid - _CONFIDENCE_CENTROID_AMBIGUOUS_HZ)
  centroid_score = min(
    1.0, centroid_distance / _CONFIDENCE_CENTROID_CLEAR_DISTANCE_HZ)

  # Energy: normalized RMS
  energy_score = min(1.0, mean_rms / rms_max) if rms_max > 0 else 0.0

  # Duration: short segments are less reliable
  if duration < _CONFIDENCE_MIN_DURATION_SEC:
    duration_score = duration / _CONFIDENCE_MIN_DURATION_SEC
  elif duration < _CONFIDENCE_FULL_DURATION_SEC:
    duration_score = 0.5 + 0.5 * (
      (duration - _CONFIDENCE_MIN_DURATION_SEC) /
      (_CONFIDENCE_FULL_DURATION_SEC - _CONFIDENCE_MIN_DURATION_SEC))
  else:
    duration_score = 1.0

  # Weighted combination (centroid is most important for shape classification)
  confidence = (0.5 * centroid_score + 0.3 * energy_score +
                0.2 * duration_score)

  return min(1.0, max(0.0, confidence))
