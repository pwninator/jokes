"""Audio operations module."""

import array
import io
import sys
import wave
from dataclasses import dataclass
from typing import Any, Tuple

import librosa
import numpy as np
import soundfile as sf

# --- Tuning Constants ---

# Frame length for RMS energy calculation in find_best_split_point.
# Larger values smooth the energy curve but reduce temporal resolution.
# 2048 samples is ~85ms at 24kHz.
RMS_FRAME_LENGTH = 2048

# Hop length for RMS energy calculation.
# Smaller values increase temporal resolution.
# 512 samples is ~21ms at 24kHz.
RMS_HOP_LENGTH = 512

# Frame length for librosa.effects.trim in trim_silence.
# Default is 2048. Matches RMS_FRAME_LENGTH for consistency.
SILENCE_TRIM_FRAME_LENGTH = 2048

# Hop length for librosa.effects.trim in trim_silence.
# Default is 512. Matches RMS_HOP_LENGTH for consistency.
SILENCE_TRIM_HOP_LENGTH = 512

# Absolute amplitude threshold for silence detection in split_wav_on_silence (fallback).
# This is for raw 16-bit PCM samples (range -32768 to 32767).
# 250 is roughly -42dB relative to full scale.
# Increasing this makes it less sensitive to noise (might cut off quiet speech).
# Decreasing this makes it more sensitive (might treat noise as speech).
SILENCE_ABS_AMPLITUDE_THRESHOLD = 250


@dataclass(frozen=True)
class SplitAudioSegment:
  """A segment of split audio with timing offset information."""
  wav_bytes: bytes
  offset_sec: float


def split_audio(
    wav_bytes: bytes,
    estimated_cut_points: list[float],
    search_radius_sec: float = 0.2,
    trim: bool = True,
) -> list[SplitAudioSegment]:
  """Split audio at refined points near the estimated cuts.

  Args:
    wav_bytes: The original audio WAV bytes.
    estimated_cut_points: List of timestamps (seconds) where cuts should happen.
    search_radius_sec: How far to search around each cut point for silence.
    trim: Whether to trim silence from the start/end of each resulting segment.

  Returns:
    A list of SplitAudioSegment objects. The size will be len(estimated_cut_points) + 1.
  """
  if not estimated_cut_points:
    # No cuts, just return the whole file (optionally trimmed).
    if trim:
      trimmed, lead = trim_silence(wav_bytes)
      return [SplitAudioSegment(trimmed, lead)]
    return [SplitAudioSegment(wav_bytes, 0.0)]

  # 1. Refine all cut points.
  refined_points: list[float] = []
  last_point = 0.0
  for cut in estimated_cut_points:
    # Ensure search window is valid and ordered
    search_start = max(last_point, cut - search_radius_sec)
    search_end = cut + search_radius_sec

    refined = find_best_split_point(wav_bytes, search_start, search_end)

    # Ensure strictly increasing split points to avoid empty or negative slices
    # If the refined point is <= last_point, push it forward slightly.
    if refined <= last_point:
      refined = last_point + 0.01  # Minimal increment

    refined_points.append(refined)
    last_point = refined

  # 2. Slice audio based on refined points.
  # We do this iteratively.
  segments: list[SplitAudioSegment] = []
  current_bytes = wav_bytes
  cumulative_time_base = 0.0

  for i, split_pt in enumerate(refined_points):
    # Calculate split point relative to the *current* clip.
    # split_pt is absolute time in the original file.
    # The current clip starts at cumulative_time_base.
    relative_split = split_pt - cumulative_time_base

    # Sanity check: if relative_split is negative or near zero, handle it?
    # split_wav_at_point handles bounds clamping.

    part1, remainder = split_wav_at_point(current_bytes, relative_split)

    # Process part1
    offset = cumulative_time_base
    if trim:
      part1, lead_silence = trim_silence(part1)
      offset += lead_silence

    segments.append(SplitAudioSegment(part1, offset))

    # Prepare for next iteration
    current_bytes = remainder
    cumulative_time_base = split_pt

  # 3. Handle the final segment
  final_offset = cumulative_time_base
  final_bytes = current_bytes
  if trim:
    final_bytes, lead_silence = trim_silence(final_bytes)
    final_offset += lead_silence

  segments.append(SplitAudioSegment(final_bytes, final_offset))

  return segments


def find_best_split_point(
    wav_bytes: bytes,
    search_start_sec: float,
    search_end_sec: float,
) -> float:
  """Find the best split point in the given window based on minimum RMS energy."""
  y, sr = sf.read(io.BytesIO(wav_bytes))
  start_sample = int(search_start_sec * sr)
  end_sample = int(search_end_sec * sr)

  # Ensure bounds are within the audio
  start_sample = max(0, start_sample)
  end_sample = min(len(y), end_sample)

  if start_sample >= end_sample:
    return (start_sample + end_sample) / 2 / sr

  segment = y[start_sample:end_sample]

  # Calculate RMS energy.
  # We use a small hop_length for higher temporal resolution.
  rms = librosa.feature.rms(
      y=segment,
      frame_length=RMS_FRAME_LENGTH,
      hop_length=RMS_HOP_LENGTH,
  )[0]

  if len(rms) == 0:
    return (start_sample + end_sample) / 2 / sr

  min_rms_index = np.argmin(rms)

  # Convert frame index to time relative to segment start
  split_time_relative = librosa.frames_to_time(
      min_rms_index, sr=sr, hop_length=RMS_HOP_LENGTH
  )

  return float(search_start_sec + split_time_relative)


def trim_silence(wav_bytes: bytes) -> tuple[bytes, float]:
  """Trim leading and trailing silence.

  Returns:
    A tuple of (trimmed_wav_bytes, leading_silence_duration_sec).
  """
  y, sr = sf.read(io.BytesIO(wav_bytes))
  trimmed_y, index = librosa.effects.trim(
      y,
      frame_length=SILENCE_TRIM_FRAME_LENGTH,
      hop_length=SILENCE_TRIM_HOP_LENGTH,
  )
  # index is [start_sample, end_sample] (exclusive)
  start_sample = index[0]

  buffer = io.BytesIO()
  sf.write(buffer, trimmed_y, sr, format='WAV')
  return buffer.getvalue(), float(start_sample) / sr


def split_wav_at_point(
    wav_bytes: bytes, split_point_sec: float
) -> tuple[bytes, bytes]:
  """Split a WAV into two parts at the given timestamp."""
  y, sr = sf.read(io.BytesIO(wav_bytes))
  split_sample = int(split_point_sec * sr)
  split_sample = max(0, min(len(y), split_sample))

  y1 = y[:split_sample]
  y2 = y[split_sample:]

  buf1 = io.BytesIO()
  sf.write(buf1, y1, sr, format='WAV')

  buf2 = io.BytesIO()
  sf.write(buf2, y2, sr, format='WAV')

  return buf1.getvalue(), buf2.getvalue()


def get_wav_duration_sec(wav_bytes: bytes) -> float:
  """Compute WAV duration from bytes."""
  params, _frames = read_wav_bytes(wav_bytes)
  framerate = float(params.framerate)
  if framerate <= 0:
    raise ValueError("WAV framerate must be positive")
  return float(params.nframes) / framerate


def split_wav_on_silence(
    wav_bytes: bytes,
    *,
    silence_duration_sec: float,
) -> tuple[bytes, bytes, bytes]:
  """Split a WAV into 3 clips using the first two interior long silent runs."""
  params, frames = read_wav_bytes(wav_bytes)
  frame_size_bytes = int(params.nchannels) * int(params.sampwidth)
  silence_frames = max(
      1, int(round(int(params.framerate) * silence_duration_sec))
  )

  silent_frames_mask = _compute_silent_frame_mask(
      frames,
      params=params,
      silence_abs_amplitude_threshold=SILENCE_ABS_AMPLITUDE_THRESHOLD,
  )
  runs = _find_silent_runs(silent_frames_mask, min_run_frames=silence_frames)

  # Prefer pauses between utterances, not leading/trailing.
  nframes = int(params.nframes)
  interior_runs = [
      (start, end) for start, end in runs if start > 0 and end < nframes
  ]
  if len(interior_runs) < 2:
    raise ValueError(
        f"Expected at least 2 interior silence runs of ~{silence_duration_sec}s; found {len(interior_runs)}"
    )

  (run1_start, run1_end), (run2_start, run2_end) = (
      interior_runs[0],
      interior_runs[1],
  )
  silences_are_ordered = (
      0 <= run1_start < run1_end <= run2_start < run2_end <= nframes
  )
  if not silences_are_ordered:
    raise ValueError(
        f"Detected silence runs are not ordered as expected: {interior_runs}"
    )

  setup_frames = frames[: run1_start * frame_size_bytes]
  response_frames = frames[
      run1_end * frame_size_bytes : run2_start * frame_size_bytes
  ]
  punchline_frames = frames[run2_end * frame_size_bytes :]

  if not setup_frames or not response_frames or not punchline_frames:
    raise ValueError("Split produced an empty clip")

  return (
      _write_wav_bytes(params=params, frames=setup_frames),
      _write_wav_bytes(params=params, frames=response_frames),
      _write_wav_bytes(params=params, frames=punchline_frames),
  )


def read_wav_bytes(wav_bytes: bytes) -> tuple[Any, bytes]:
  """Parse WAV bytes into (params, raw PCM frame bytes)."""
  with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
    # pylint: disable=no-member
    params = wf.getparams()
    nframes = wf.getnframes()
    frames = wf.readframes(nframes)
    # pylint: enable=no-member

  if params.comptype != "NONE":
    raise ValueError(f"Unsupported WAV compression: {params.comptype}")

  frame_size_bytes = int(params.nchannels) * int(params.sampwidth)
  expected_len = int(params.nframes) * frame_size_bytes
  if expected_len and len(frames) != expected_len:
    # Some providers produce WAV headers with placeholder sizes (e.g. 0xFFFFFFFF),
    # which makes `wave` report an absurd nframes count. If the actual payload is
    # well-formed PCM, infer the correct nframes from the real byte length.
    if (
        frame_size_bytes > 0
        and expected_len > len(frames)
        and len(frames) % frame_size_bytes == 0
    ):
      inferred_nframes = len(frames) // frame_size_bytes
      if hasattr(params, "_replace"):
        params = params._replace(nframes=inferred_nframes)
      else:
        try:
          params.nframes = inferred_nframes
        except Exception:
          pass
    else:
      raise ValueError(
          f"Unexpected WAV frame byte length: expected={expected_len} got={len(frames)}"
      )
  return params, frames


def _write_wav_bytes(*, params: Any, frames: bytes) -> bytes:
  """Write WAV bytes from params + raw frame bytes."""
  buffer = io.BytesIO()
  with wave.open(buffer, "wb") as wf:
    # pylint: disable=no-member
    wf.setnchannels(int(params.nchannels))
    wf.setsampwidth(int(params.sampwidth))
    wf.setframerate(int(params.framerate))
    wf.writeframes(frames)
    # pylint: enable=no-member
  return buffer.getvalue()


def _compute_silent_frame_mask(
    frames: bytes,
    *,
    params: Any,
    silence_abs_amplitude_threshold: int,
) -> list[bool]:
  """Return a per-frame boolean mask for silence detection."""
  nchannels = int(params.nchannels)
  sampwidth = int(params.sampwidth)
  nframes = int(params.nframes)

  frame_size_bytes = nchannels * sampwidth
  if nframes == 0:
    return []
  if len(frames) != nframes * frame_size_bytes:
    raise ValueError("Frame byte length does not match WAV params")

  # Gemini output is LINEAR16 (signed int16). Support that robustly.
  if sampwidth == 2:
    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
      # WAV PCM is little-endian. Ensure consistent interpretation.
      samples.byteswap()

    # Compute a per-frame peak amplitude.
    peaks: list[int] = [0] * nframes
    sample_index = 0
    for frame_index in range(nframes):
      peak = 0
      for _ch in range(nchannels):
        sample = samples[sample_index]
        sample_index += 1
        value = abs(int(sample))
        if value > peak:
          peak = value
      peaks[frame_index] = peak

    # Adaptive threshold: sample peaks to estimate noise floor.
    step = max(1, nframes // 5000)
    sampled = [peaks[i] for i in range(0, nframes, step)]
    sampled.sort()
    if not sampled:
      return [True] * nframes

    def percentile(p: float) -> int:
      idx = int(round((len(sampled) - 1) * p))
      idx = max(0, min(idx, len(sampled) - 1))
      return int(sampled[idx])

    p10 = percentile(0.10)
    p50 = percentile(0.50)

    # If the file has long quiet regions, p10 approximates the noise floor.
    # Use both p10 and p50 so we don't classify everything as silence in cases
    # where the whole file is quiet.
    adaptive_threshold = max(
        int(silence_abs_amplitude_threshold),
        int(round(p10 * 1.8)),
        int(round(p50 * 0.05)),
    )

    return [peak <= adaptive_threshold for peak in peaks]

  # Fallback: treat only all-zero frames as silence.
  zero_frame = b"\x00" * frame_size_bytes
  silent = [False] * nframes
  for frame_index in range(nframes):
    chunk = frames[
        frame_index * frame_size_bytes : (frame_index + 1) * frame_size_bytes
    ]
    silent[frame_index] = chunk == zero_frame
  return silent


def _find_silent_runs(
    mask: list[bool],
    *,
    min_run_frames: int,
) -> list[tuple[int, int]]:
  """Return [(start_frame, end_frame_exclusive)] for silent runs >= min_run."""
  runs: list[tuple[int, int]] = []
  i = 0
  n = len(mask)
  while i < n:
    if not mask[i]:
      i += 1
      continue
    start = i
    while i < n and mask[i]:
      i += 1
    end = i
    if (end - start) >= min_run_frames:
      runs.append((start, end))
  return runs
