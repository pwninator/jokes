"""Syllable detection utilities for cartoon mouth animation."""

from __future__ import annotations

import io
from dataclasses import dataclass

import librosa
import numpy as np
import soundfile as sf
from common.posable_character import MouthState

_FRAME_MS = 25
_HOP_MS = 10
_ONSET_WAIT_MS = 80
_ONSET_DELTA = 0.2
_O_CENTROID_PERCENTILE = 35
_MIN_SYLLABLE_SEC = 0.04
_MAX_SYLLABLE_SEC = 0.18
_SYLLABLE_PRE_ROLL_SEC = 0.02
_MIN_RMS_PERCENTILE = 20
_FALLBACK_FLAP_SEC = 0.12
_ONSET_MERGE_SEC = 0.06


@dataclass(frozen=True)
class Syllable:
  """A syllable detected in an audio clip."""

  start_time: float
  end_time: float
  mouth_shape: MouthState
  onset_strength: float


def detect_syllables(wav_bytes: bytes) -> list[Syllable]:
  """Detect syllables using librosa onset detection and spectral centroid."""
  y, sr = _load_audio(wav_bytes)
  if y.size == 0 or sr <= 0:
    return []

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
  if float(rms.max()) <= 1e-6:
    return []

  rms_threshold = np.percentile(rms, _MIN_RMS_PERCENTILE)
  voiced_mask = rms >= rms_threshold
  centroid_source = centroid[voiced_mask] if np.any(voiced_mask) else centroid
  centroid_threshold = np.percentile(centroid_source, _O_CENTROID_PERCENTILE)

  onset_frames = _detect_onset_frames(onset_env, sr=sr, hop_length=hop_length)
  onset_times = librosa.frames_to_time(onset_frames,
                                       sr=sr,
                                       hop_length=hop_length)
  rhythmic_times = _build_rhythmic_candidates(
    voiced_mask,
    sr=sr,
    hop_length=hop_length,
  )
  candidate_times = _merge_candidate_times(onset_times, rhythmic_times)

  syllables: list[Syllable] = []
  for onset_time in candidate_times:
    _append_syllable(
      syllables,
      onset_time,
      onset_env,
      rms,
      centroid,
      rms_threshold,
      centroid_threshold,
      sr,
      hop_length,
    )

  return syllables


def _load_audio(wav_bytes: bytes) -> tuple[np.ndarray, int]:
  with sf.SoundFile(io.BytesIO(wav_bytes)) as sound_file:
    y = sound_file.read(dtype="float32", always_2d=True)
    sr = int(sound_file.samplerate)
  if y.size == 0:
    return np.zeros((0, ), dtype=np.float32), sr
  if y.shape[1] > 1:
    y = np.mean(y, axis=1, keepdims=True)
  return y[:, 0], sr


def _detect_onset_frames(onset_env: np.ndarray, *, sr: int,
                         hop_length: int) -> np.ndarray:
  if onset_env.size == 0 or float(onset_env.max()) <= 0:
    return np.array([], dtype=int)
  wait_frames = max(1, int(round((_ONSET_WAIT_MS / 1000.0) * sr / hop_length)))
  return librosa.onset.onset_detect(
    onset_envelope=onset_env,
    sr=sr,
    hop_length=hop_length,
    units="frames",
    wait=wait_frames,
    delta=_ONSET_DELTA,
  )


def _append_syllable(
  syllables: list[Syllable],
  onset_time: float,
  onset_env: np.ndarray,
  rms: np.ndarray,
  centroid: np.ndarray,
  rms_threshold: float,
  centroid_threshold: float,
  sr: int,
  hop_length: int,
) -> None:
  frame_index = int(round(onset_time * sr / hop_length))
  frame_index = max(0, min(frame_index, rms.size - 1))
  if rms[frame_index] < rms_threshold:
    return

  start_time = max(0.0, onset_time - _SYLLABLE_PRE_ROLL_SEC)
  end_time = onset_time + _MAX_SYLLABLE_SEC
  if end_time - start_time < _MIN_SYLLABLE_SEC:
    end_time = start_time + _MIN_SYLLABLE_SEC

  mouth_shape = (MouthState.O if centroid[frame_index] <= centroid_threshold
                 else MouthState.OPEN)
  onset_strength = (float(onset_env[frame_index])
                    if onset_env.size > frame_index else 0.0)
  syllables.append(
    Syllable(
      start_time=start_time,
      end_time=end_time,
      mouth_shape=mouth_shape,
      onset_strength=onset_strength,
    ))


def _build_rhythmic_candidates(
  voiced_mask: np.ndarray,
  *,
  sr: int,
  hop_length: int,
) -> np.ndarray:
  segments = _find_runs(voiced_mask)
  candidates: list[float] = []
  for start_frame, end_frame in segments:
    start_time = float(
      librosa.frames_to_time(start_frame, sr=sr, hop_length=hop_length))
    end_time = float(
      librosa.frames_to_time(end_frame, sr=sr, hop_length=hop_length))
    if end_time <= start_time:
      continue
    flap_time = start_time
    while flap_time < end_time:
      candidates.append(flap_time)
      flap_time += _FALLBACK_FLAP_SEC
  return np.array(candidates, dtype=np.float32)


def _merge_candidate_times(
  onset_times: np.ndarray,
  rhythmic_times: np.ndarray,
) -> list[float]:
  if onset_times.size == 0 and rhythmic_times.size == 0:
    return []
  if onset_times.size == 0:
    return rhythmic_times.tolist()
  if rhythmic_times.size == 0:
    return onset_times.tolist()

  candidates = np.concatenate([onset_times, rhythmic_times])
  candidates.sort()
  merged: list[float] = []
  for candidate in candidates:
    if not merged:
      merged.append(float(candidate))
      continue
    if candidate - merged[-1] >= _ONSET_MERGE_SEC:
      merged.append(float(candidate))
  return merged


def _find_runs(mask: np.ndarray) -> list[tuple[int, int]]:
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
    end = i
    runs.append((start, end))
  return runs
