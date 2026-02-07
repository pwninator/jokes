"""Tests for audio_operations module."""

import array
import io
import wave
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from common import audio_operations


def _create_sine_wave(
    duration_sec: float, freq: float = 440.0, sr: int = 24000, amp: float = 0.5
) -> np.ndarray:
  t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
  return amp * np.sin(2 * np.pi * freq * t)


def _create_silence(duration_sec: float, sr: int = 24000) -> np.ndarray:
  return np.zeros(int(duration_sec * sr))


def _to_wav_bytes(audio: np.ndarray, sr: int = 24000) -> bytes:
  buffer = io.BytesIO()
  sf.write(buffer, audio, sr, format='WAV')
  return buffer.getvalue()


class TestFindBestSplitPoint:
  def test_finds_silence_in_middle(self):
    sr = 24000
    # 0.5s tone, 0.5s silence, 0.5s tone
    part1 = _create_sine_wave(0.5, sr=sr)
    silence = _create_silence(0.5, sr=sr)
    part2 = _create_sine_wave(0.5, sr=sr)
    audio = np.concatenate([part1, silence, part2])
    wav_bytes = _to_wav_bytes(audio, sr=sr)

    # Search window covering the silence
    # Center is 0.75s. Window 0.5s to 1.0s.
    split_point = audio_operations.find_best_split_point(
        wav_bytes, search_start_sec=0.4, search_end_sec=1.1
    )

    # Should be within the silence (0.5 to 1.0)
    assert 0.5 <= split_point <= 1.0

  def test_finds_silence_with_noise(self):
    sr = 24000
    # 0.5s tone, 0.5s low noise (simulating silence), 0.5s tone
    part1 = _create_sine_wave(0.5, sr=sr)
    noise = np.random.normal(0, 0.001, int(0.5 * sr))  # Very quiet noise
    part2 = _create_sine_wave(0.5, sr=sr)
    audio = np.concatenate([part1, noise, part2])
    wav_bytes = _to_wav_bytes(audio, sr=sr)

    split_point = audio_operations.find_best_split_point(
        wav_bytes, search_start_sec=0.4, search_end_sec=1.1
    )

    # Should be within the "silence" (0.5 to 1.0)
    assert 0.5 <= split_point <= 1.0

  def test_fallback_to_midpoint_if_no_audio(self):
    # Empty audio
    wav_bytes = _to_wav_bytes(np.array([]))
    split_point = audio_operations.find_best_split_point(
        wav_bytes, search_start_sec=0.0, search_end_sec=1.0
    )
    # With empty audio, the "clamped" start/end samples are both 0.
    # So it returns (0+0)/2 = 0.0.
    assert split_point == 0.0


class TestTrimSilence:
  def test_trims_leading_and_trailing_silence(self):
    sr = 24000
    silence_start = _create_silence(0.5, sr=sr)
    audio_content = _create_sine_wave(1.0, sr=sr)
    silence_end = _create_silence(0.5, sr=sr)
    full_audio = np.concatenate([silence_start, audio_content, silence_end])
    wav_bytes = _to_wav_bytes(full_audio, sr=sr)

    trimmed_bytes, lead_duration = audio_operations.trim_silence(wav_bytes)

    # Check lead duration
    # librosa.effects.trim works on frames (default 2048 samples).
    # This creates a potential margin of error around ~0.085s (2048/24000).
    assert lead_duration == pytest.approx(0.5, abs=0.1)

    # Check trimmed audio length
    y, _ = sf.read(io.BytesIO(trimmed_bytes))
    duration = len(y) / sr
    assert duration == pytest.approx(1.0, abs=0.1)


class TestSplitWavAtPoint:
  def test_splits_correctly(self):
    sr = 24000
    audio = _create_sine_wave(2.0, sr=sr)
    wav_bytes = _to_wav_bytes(audio, sr=sr)

    part1_bytes, part2_bytes = audio_operations.split_wav_at_point(
        wav_bytes, split_point_sec=0.5
    )

    y1, _ = sf.read(io.BytesIO(part1_bytes))
    y2, _ = sf.read(io.BytesIO(part2_bytes))

    assert len(y1) / sr == pytest.approx(0.5, abs=0.01)
    assert len(y2) / sr == pytest.approx(1.5, abs=0.01)


class TestSplitWavOnSilence:
  def test_splits_on_two_pauses(self):
    sr = 24000
    # Make silence "perfectly" silent (zeros) because `_compute_silent_frame_mask`
    # logic depends on amplitude thresholds or zeros.
    # The existing logic (migrated) expects integer PCM data. `_to_wav_bytes` uses float32 by default via soundfile?
    # No, sf.write default subtype depends on format. For WAV it's typically PCM_16 if not specified or float if input is float.
    # `audio_operations.read_wav_bytes` handles decoding.
    # But `_compute_silent_frame_mask` handles "LINEAR16" (sampwidth=2).
    # If `sf.write` writes float, `read_wav_bytes` might fail or return different sampwidth.
    # Let's explicitly write PCM_16.

    def _to_pcm16_wav_bytes(audio: np.ndarray, sr: int = 24000) -> bytes:
      buffer = io.BytesIO()
      # Scale float to int16 range if needed, soundfile does it automatically if subtype='PCM_16'
      sf.write(buffer, audio, sr, format='WAV', subtype='PCM_16')
      return buffer.getvalue()

    tone = _create_sine_wave(0.5, sr=sr)
    silence = _create_silence(1.0, sr=sr)

    full_audio = np.concatenate([tone, silence, tone, silence, tone])
    wav_bytes = _to_pcm16_wav_bytes(full_audio, sr=sr)

    part1, part2, part3 = audio_operations.split_wav_on_silence(
        wav_bytes, silence_duration_sec=0.8
    )

    # Check durations
    assert audio_operations.get_wav_duration_sec(part1) == pytest.approx(0.5, abs=0.1)
    assert audio_operations.get_wav_duration_sec(part2) == pytest.approx(0.5, abs=0.1)
    assert audio_operations.get_wav_duration_sec(part3) == pytest.approx(0.5, abs=0.1)


class TestReadWavBytes:
  def test_read_wav_bytes_allows_placeholder_data_chunk_size(self):
    """Some providers emit WAV headers with placeholder sizes (e.g. 0xFFFFFFFF)."""

    def make_wav_bytes(duration_sec: float, *, rate: int = 1000) -> bytes:
      frames = array.array("h", [0] * int(rate * duration_sec)).tobytes()
      buffer = io.BytesIO()
      with wave.open(buffer, "wb") as wf:
        # pylint: disable=no-member
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)
        # pylint: enable=no-member
      return buffer.getvalue()

    wav_bytes = make_wav_bytes(0.25, rate=1000)
    marker = b"data"
    idx = wav_bytes.find(marker)
    assert idx != -1
    size_offset = idx + 4
    patched = bytearray(wav_bytes)
    # Set data chunk size to 0xFFFFFFFF (placeholder), leaving payload intact.
    patched[size_offset:size_offset + 4] = (0xFFFFFFFF).to_bytes(4, "little")

    params, frames = audio_operations.read_wav_bytes(bytes(patched))
    assert int(params.nframes) == len(frames) // (int(params.nchannels) *
                                                 int(params.sampwidth))
