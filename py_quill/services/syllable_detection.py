"""Syllable detection utilities for cartoon mouth animation."""

from __future__ import annotations

import io
from dataclasses import dataclass

import librosa
import numpy as np
import soundfile as sf
from common.mouth_events import MouthEvent
from common.posable_character import MouthState

# Frame and hop settings
_FRAME_MS = 25
_HOP_MS = 10

# Onset detection settings
_ONSET_WAIT_MS = 80
_ONSET_DELTA = 0.2

# Centroid threshold settings
_O_CENTROID_PERCENTILE = 35
_MIN_CENTROID_SPREAD_HZ = 500.0
_ABSOLUTE_O_CENTROID_HZ = 1200.0
_HYSTERESIS_HZ = 200.0

# Syllable timing settings
_MIN_SYLLABLE_SEC = 0.04
_MAX_SYLLABLE_SEC = 0.18
_SYLLABLE_PRE_ROLL_SEC = 0.02

# Voice detection settings
_MIN_RMS_PERCENTILE = 20

# Fallback and merging settings
_FALLBACK_FLAP_SEC = 0.12
_BOUNDARY_MERGE_SEC = 0.06

# Smoothing settings
_CENTROID_SMOOTH_FRAMES = 3

# Confidence scoring settings
_CONFIDENCE_CENTROID_AMBIGUOUS_HZ = 1200.0  # Center of ambiguous zone
_CONFIDENCE_CENTROID_CLEAR_DISTANCE_HZ = 600.0  # Distance for full confidence
_CONFIDENCE_MIN_DURATION_SEC = 0.03  # Below this, confidence drops
_CONFIDENCE_FULL_DURATION_SEC = 0.08  # Above this, duration doesn't help


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


def detect_segments_with_confidence(wav_bytes: bytes) -> list[MouthEvent]:
  """Detect mouth events with confidence scores for transcript alignment.

  Returns MouthEvent objects that include confidence scores based on audio
  characteristics. Higher confidence means we're more certain about the
  detected mouth shape.

  Confidence is computed from:
  - Centroid extremity: How far from the ambiguous 1200Hz zone
  - RMS energy: Louder segments are more reliable
  - Duration: Very short segments are less reliable

  Args:
    wav_bytes: WAV audio data.

  Returns:
    List of MouthEvent objects sorted by start_time.
  """
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


def detect_syllables_for_lip_sync(
  wav_bytes: bytes,
  *,
  transcript: str | None = None,
) -> list[MouthEvent]:
  """Detect syllables for lip-sync animation, optionally using a transcript.

  When a transcript is provided, this uses audio timing plus transcript-based
  alignment (dynamic programming) to refine mouth shapes.

  Args:
    wav_bytes: WAV audio data.
    transcript: Optional transcript for the audio clip.

  Returns:
    List of MouthEvent objects sorted by start_time.
  """
  audio_segments = detect_segments_with_confidence(wav_bytes)
  if not audio_segments:
    return []

  transcript = transcript.strip() if transcript else ""
  if not transcript:
    return audio_segments

  from services import transcript_alignment

  return transcript_alignment.align_with_text(transcript, audio_segments)


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

    centroid_val = features.centroid[i]

    if current_state == MouthState.CLOSED:
      # Just entered voiced segment - use midpoint (no hysteresis)
      if centroid_val <= midpoint:
        current_state = MouthState.O
      else:
        current_state = MouthState.OPEN
    elif current_state == MouthState.OPEN:
      # Currently OPEN - need to drop below threshold_to_o to switch to O
      if centroid_val <= thresholds.centroid_threshold_to_o:
        current_state = MouthState.O
      # else stay OPEN
    else:
      # Currently O - need to rise above threshold_to_open to switch to OPEN
      if centroid_val >= thresholds.centroid_threshold_to_open:
        current_state = MouthState.OPEN
      # else stay O

    states[i] = current_state

  return states


def _find_all_boundaries(
  features: _AudioFeatures,
  thresholds: _Thresholds,
  frame_states: np.ndarray,
) -> list[int]:
  """Find all syllable boundary frames from onsets, transitions, and rhythm.

  Combines:
  1. Onset detection (consonant attacks like "h" in "hahaha")
  2. State transitions (vowel changes like "wh" -> "aa" in "whaaa")
  3. Rhythmic fallback (long sustained sounds without clear onsets)

  Returns:
    Sorted list of unique boundary frame indices.
  """
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


def _create_segments_with_confidence(
  boundary_frames: list[int],
  frame_states: np.ndarray,
  features: _AudioFeatures,
  thresholds: _Thresholds,
) -> list[MouthEvent]:
  """Create MouthEvent objects with confidence scores from boundary frames.

  Computes confidence scores based on audio characteristics like centroid
  extremity, RMS energy, and duration.
  """
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
  """Compute confidence score for a segment based on audio characteristics.

  Confidence is derived from three factors:
  1. Centroid extremity: How far from the ambiguous 1200Hz zone (0.0-1.0)
  2. Energy: Relative loudness compared to max RMS (0.0-1.0)
  3. Duration: Longer segments are more reliable (0.0-1.0)

  Args:
    mean_centroid: Mean spectral centroid of the segment in Hz.
    mean_rms: Mean RMS energy of the segment.
    rms_max: Maximum RMS in the entire audio clip (for normalization).
    duration: Duration of the segment in seconds.

  Returns:
    Confidence score from 0.0 (low confidence) to 1.0 (high confidence).
  """
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
