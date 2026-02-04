"""Tests for syllable detection."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from common.posable_character import MouthState
from services import syllable_detection
from services.syllable_detection import detect_syllables


def _make_wav_bytes(
  *,
  sample_rate: int = 22050,
  duration_sec: float = 1.0,
  segments: list[tuple[float, float, float]],
) -> bytes:
  total_samples = int(duration_sec * sample_rate)
  y = np.zeros(total_samples, dtype=np.float32)
  for start, length, freq in segments:
    start_idx = int(start * sample_rate)
    end_idx = min(total_samples, int((start + length) * sample_rate))
    if end_idx <= start_idx:
      continue
    t = np.arange(end_idx - start_idx, dtype=np.float32) / sample_rate
    y[start_idx:end_idx] = 0.5 * np.sin(2 * np.pi * freq * t)
  buffer = io.BytesIO()
  sf.write(buffer, y, sample_rate, format="WAV")
  return buffer.getvalue()


def test_detect_syllables_finds_multiple_onsets():
  wav_bytes = _make_wav_bytes(segments=[
    (0.1, 0.08, 440.0),
    (0.4, 0.08, 440.0),
    (0.7, 0.08, 440.0),
  ], )
  syllables = detect_syllables(wav_bytes)

  assert len(syllables) >= 3
  starts = [syllable.start_time for syllable in syllables]
  assert any(start == pytest.approx(0.08, abs=0.08) for start in starts)
  assert any(start == pytest.approx(0.38, abs=0.08) for start in starts)
  assert any(start == pytest.approx(0.68, abs=0.08) for start in starts)


def test_detect_syllables_classifies_o_vs_open(monkeypatch):
  wav_bytes = _make_wav_bytes(
    duration_sec=0.4,
    segments=[
      (0.0, 0.2, 220.0),
      (0.2, 0.2, 2000.0),
    ],
  )

  hop_length = int(round(22050 * (syllable_detection._HOP_MS / 1000.0)))
  onset_frames = np.array([
    int(round(0.05 * 22050 / hop_length)),
    int(round(0.25 * 22050 / hop_length)),
  ],
                          dtype=int)

  original_percentile = syllable_detection.np.percentile

  def fake_percentile(values, percentile):
    if float(np.max(values)) > 500:
      return float(np.min(values) + (np.max(values) - np.min(values)) / 2)
    return float(original_percentile(values, percentile))

  monkeypatch.setattr(syllable_detection.np, "percentile", fake_percentile)
  monkeypatch.setattr(syllable_detection.librosa.onset, "onset_detect",
                      lambda *_args, **_kwargs: onset_frames)
  monkeypatch.setattr(syllable_detection, "_build_rhythmic_candidates",
                      lambda *_args, **_kwargs: np.array([], dtype=np.float32))
  syllables = detect_syllables(wav_bytes)

  assert len(syllables) >= 2
  detected = [
    syllable for syllable in syllables if syllable.onset_strength > 0
  ]
  assert len(detected) >= 2
  shapes = {syllable.mouth_shape for syllable in detected}
  assert MouthState.O in shapes
  assert MouthState.OPEN in shapes


def test_detect_syllables_handles_silence():
  buffer = io.BytesIO()
  sf.write(buffer, np.zeros(8000, dtype=np.float32), 8000, format="WAV")
  syllables = detect_syllables(buffer.getvalue())

  assert syllables == []


def test_detect_syllables_falls_back_when_onsets_missing(monkeypatch):
  wav_bytes = _make_wav_bytes(segments=[
    (0.0, 0.5, 440.0),
  ], )

  def fake_onset_detect(*_args, **_kwargs):
    return np.array([], dtype=int)

  monkeypatch.setattr(syllable_detection.librosa.onset, "onset_detect",
                      fake_onset_detect)
  syllables = detect_syllables(wav_bytes)

  assert len(syllables) >= 2
