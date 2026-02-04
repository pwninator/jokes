"""Tests for syllable detection."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from common.posable_character import MouthState
from services import syllable_detection
from services.syllable_detection import (
  Syllable,
  _AudioFeatures,
  _Thresholds,
  _compute_features,
  _compute_frame_states,
  _compute_thresholds,
  _detect_state_transitions,
  _find_runs,
  _merge_boundary_frames,
  detect_syllables,
)


def _make_wav_bytes(
  *,
  sample_rate: int = 22050,
  duration_sec: float = 1.0,
  segments: list[tuple[float, float, float]],
) -> bytes:
  """Create WAV bytes with sine wave segments.

  Args:
    sample_rate: Sample rate in Hz.
    duration_sec: Total duration in seconds.
    segments: List of (start_sec, length_sec, frequency_hz) tuples.

  Returns:
    WAV file bytes.
  """
  total_samples = int(duration_sec * sample_rate)
  y = np.zeros(total_samples, dtype=np.float32)
  for start, length, freq in segments:
    start_idx = int(start * sample_rate)
    end_idx = min(total_samples, int((start + length) * sample_rate))
    if end_idx <= start_idx:
      continue
    t = np.arange(end_idx - start_idx, dtype=np.float32) / sample_rate
    # Add harmonics for spectral spread
    y[start_idx:end_idx] = (0.5 * np.sin(2 * np.pi * freq * t) +
                            0.2 * np.sin(2 * np.pi * (freq * 2) * t))
  buffer = io.BytesIO()
  sf.write(buffer, y, sample_rate, format="WAV")
  return buffer.getvalue()


# =============================================================================
# Integration Tests - detect_syllables()
# =============================================================================


class TestDetectSyllablesIntegration:
  """Integration tests for the main detect_syllables function."""

  def test_finds_multiple_onsets(self):
    """Detects separate syllables from distinct sound bursts."""
    wav_bytes = _make_wav_bytes(segments=[
      (0.1, 0.08, 440.0),
      (0.4, 0.08, 440.0),
      (0.7, 0.08, 440.0),
    ], )
    syllables = detect_syllables(wav_bytes)

    assert len(syllables) >= 3
    starts = [s.start_time for s in syllables]
    assert any(start == pytest.approx(0.08, abs=0.08) for start in starts)
    assert any(start == pytest.approx(0.38, abs=0.08) for start in starts)
    assert any(start == pytest.approx(0.68, abs=0.08) for start in starts)

  def test_handles_silence(self):
    """Returns empty list for silent audio."""
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(8000, dtype=np.float32), 8000, format="WAV")
    syllables = detect_syllables(buffer.getvalue())

    assert syllables == []

  def test_handles_empty_audio(self):
    """Returns empty list for empty audio."""
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(0, dtype=np.float32), 8000, format="WAV")
    syllables = detect_syllables(buffer.getvalue())

    assert syllables == []

  def test_falls_back_when_onsets_missing(self, monkeypatch):
    """Uses rhythmic fallback for sustained sounds without clear onsets."""
    wav_bytes = _make_wav_bytes(segments=[
      (0.0, 0.5, 440.0),
    ], )

    def fake_onset_detect(*_args, **_kwargs):
      return np.array([], dtype=int)

    monkeypatch.setattr(syllable_detection.librosa.onset, "onset_detect",
                        fake_onset_detect)
    syllables = detect_syllables(wav_bytes)

    assert len(syllables) >= 2

  def test_syllables_have_valid_times(self):
    """All syllables have positive duration and valid times."""
    wav_bytes = _make_wav_bytes(segments=[
      (0.1, 0.08, 440.0),
      (0.4, 0.08, 880.0),
    ], )
    syllables = detect_syllables(wav_bytes)

    for s in syllables:
      assert s.start_time >= 0
      assert s.end_time > s.start_time
      assert s.mouth_shape in (MouthState.OPEN, MouthState.O)


# =============================================================================
# Mouth Shape Classification Tests
# =============================================================================


class TestMouthShapeClassification:
  """Tests for O vs OPEN classification."""

  def test_classifies_o_vs_open(self, monkeypatch):
    """Distinguishes O (low centroid) from OPEN (high centroid)."""
    sr = 22050
    frame_count = 100

    # Create centroid with clear O and OPEN regions
    # Use wide regions to account for 3-frame smoothing
    centroid = np.full(frame_count, 1500.0)  # Neutral background
    centroid[5:25] = 400.0  # O region (low centroid)
    centroid[35:55] = 3000.0  # OPEN region (high centroid)

    rms = np.zeros(frame_count)
    rms[10:20] = 0.5  # Voiced within O region
    rms[40:50] = 0.5  # Voiced within OPEN region

    onset_env = np.zeros(frame_count)
    onset_env[10] = 1.0
    onset_env[40] = 1.0

    monkeypatch.setattr(syllable_detection, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10, 40]),
    )
    # Disable rhythmic fallback to test only onset-based detection
    monkeypatch.setattr(syllable_detection, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    syllables = detect_syllables(b"dummy")

    assert len(syllables) == 2
    assert syllables[0].mouth_shape == MouthState.O
    assert syllables[1].mouth_shape == MouthState.OPEN

  def test_low_spread_high_values_defaults_to_open(self, monkeypatch):
    """Low centroid spread with high values -> all OPEN."""
    sr = 22050
    frame_count = 100

    # High values, low spread
    centroid = np.random.uniform(2000, 2100, frame_count)
    rms = np.ones(frame_count) * 0.5
    onset_env = np.zeros(frame_count)
    onset_env[10] = 1.0

    monkeypatch.setattr(syllable_detection, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback
    monkeypatch.setattr(syllable_detection, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    syllables = detect_syllables(b"dummy")

    assert len(syllables) == 1
    assert syllables[0].mouth_shape == MouthState.OPEN

  def test_low_spread_low_values_defaults_to_o(self, monkeypatch):
    """Low centroid spread with low values (hohoho) -> all O."""
    sr = 22050
    frame_count = 100

    # Low values, low spread
    centroid = np.random.uniform(400, 600, frame_count)
    rms = np.ones(frame_count) * 0.5
    onset_env = np.zeros(frame_count)
    onset_env[10] = 1.0

    monkeypatch.setattr(syllable_detection, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback
    monkeypatch.setattr(syllable_detection, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    syllables = detect_syllables(b"dummy")

    assert len(syllables) == 1
    assert syllables[0].mouth_shape == MouthState.O


# =============================================================================
# State Transition Tests (Mid-Syllable Vowel Changes)
# =============================================================================


class TestStateTransitions:
  """Tests for detecting state transitions within voiced segments."""

  def test_detects_mid_syllable_transition(self, monkeypatch):
    """Detects O -> OPEN transition within a sustained sound (like 'whaaa')."""
    sr = 22050
    frame_count = 100

    # Continuous sound with centroid transition
    # Use wider regions to account for 3-frame smoothing
    # Frames 5-34: low centroid (O) - extends before voiced start
    # Frames 35-55: high centroid (OPEN) - extends after voiced end
    centroid = np.full(frame_count, 1500.0)  # Neutral background
    centroid[5:35] = 400.0  # O region
    centroid[35:55] = 2500.0  # OPEN region

    rms = np.zeros(frame_count)
    rms[10:50] = 0.5  # Continuous voiced segment

    onset_env = np.zeros(frame_count)
    onset_env[10] = 1.0  # Only one onset at start

    monkeypatch.setattr(syllable_detection, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback to test only onset + transition detection
    monkeypatch.setattr(syllable_detection, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    syllables = detect_syllables(b"dummy")

    # Should have 2 syllables: O then OPEN (transition at ~frame 35)
    assert len(syllables) == 2
    assert syllables[0].mouth_shape == MouthState.O
    assert syllables[1].mouth_shape == MouthState.OPEN

  def test_detects_open_to_o_transition(self, monkeypatch):
    """Detects OPEN -> O transition."""
    sr = 22050
    frame_count = 100

    # Transition from high to low centroid
    # Use wider regions to account for smoothing
    centroid = np.full(frame_count, 1500.0)  # Neutral background
    centroid[5:35] = 2500.0  # OPEN region
    centroid[35:55] = 400.0  # O region

    rms = np.zeros(frame_count)
    rms[10:50] = 0.5

    onset_env = np.zeros(frame_count)
    onset_env[10] = 1.0

    monkeypatch.setattr(syllable_detection, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      syllable_detection.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback to test only onset + transition detection
    monkeypatch.setattr(syllable_detection, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    syllables = detect_syllables(b"dummy")

    assert len(syllables) == 2
    assert syllables[0].mouth_shape == MouthState.OPEN
    assert syllables[1].mouth_shape == MouthState.O


# =============================================================================
# Hysteresis Tests
# =============================================================================


class TestHysteresis:
  """Tests for hysteresis behavior preventing jittery transitions."""

  def test_hysteresis_prevents_small_fluctuations(self):
    """Small centroid fluctuations don't cause state changes."""
    # Create thresholds with hysteresis
    thresholds = _Thresholds(
      rms_threshold=0.1,
      centroid_threshold_to_o=1000.0,  # Must drop below 1000 to become O
      centroid_threshold_to_open=1200.0,  # Must rise above 1200 to become OPEN
    )

    # Centroid oscillates between 1050 and 1150 (within hysteresis band)
    centroid = np.array([1050, 1150, 1050, 1150, 1050, 1150, 1050, 1150])
    rms = np.ones(8) * 0.5

    features = _AudioFeatures(
      centroid=centroid,
      rms=rms,
      onset_env=np.zeros(8),
      sr=22050,
      hop_length=220,
    )

    states = _compute_frame_states(features, thresholds)

    # Should stay in same state throughout (OPEN since starting above both)
    voiced_states = [s for s in states if s != MouthState.CLOSED]
    assert all(s == voiced_states[0] for s in voiced_states)

  def test_hysteresis_allows_large_transitions(self):
    """Large centroid changes do trigger state transitions."""
    thresholds = _Thresholds(
      rms_threshold=0.1,
      centroid_threshold_to_o=1000.0,
      centroid_threshold_to_open=1200.0,
    )

    # Centroid goes from well above to well below threshold
    centroid = np.array([1500, 1500, 800, 800, 1500, 1500])
    rms = np.ones(6) * 0.5

    features = _AudioFeatures(
      centroid=centroid,
      rms=rms,
      onset_env=np.zeros(6),
      sr=22050,
      hop_length=220,
    )

    states = _compute_frame_states(features, thresholds)

    # Should have transitions
    assert states[0] == MouthState.OPEN
    assert states[2] == MouthState.O
    assert states[4] == MouthState.OPEN


# =============================================================================
# Unit Tests - Helper Functions
# =============================================================================


class TestFindRuns:
  """Tests for _find_runs helper."""

  def test_finds_single_run(self):
    mask = np.array([False, True, True, True, False])
    runs = _find_runs(mask)
    assert runs == [(1, 4)]

  def test_finds_multiple_runs(self):
    mask = np.array([True, True, False, True, False, True, True])
    runs = _find_runs(mask)
    assert runs == [(0, 2), (3, 4), (5, 7)]

  def test_handles_empty_mask(self):
    mask = np.array([], dtype=bool)
    runs = _find_runs(mask)
    assert runs == []

  def test_handles_all_false(self):
    mask = np.array([False, False, False])
    runs = _find_runs(mask)
    assert runs == []

  def test_handles_all_true(self):
    mask = np.array([True, True, True])
    runs = _find_runs(mask)
    assert runs == [(0, 3)]


class TestDetectStateTransitions:
  """Tests for _detect_state_transitions helper."""

  def test_detects_o_to_open_transition(self):
    states = np.array([
      MouthState.CLOSED,
      MouthState.O,
      MouthState.O,
      MouthState.OPEN,
      MouthState.OPEN,
      MouthState.CLOSED,
    ])

    transitions = _detect_state_transitions(states)

    assert transitions == [3]  # Frame 3 is where O -> OPEN

  def test_detects_open_to_o_transition(self):
    states = np.array([
      MouthState.CLOSED,
      MouthState.OPEN,
      MouthState.OPEN,
      MouthState.O,
      MouthState.O,
      MouthState.CLOSED,
    ])

    transitions = _detect_state_transitions(states)

    assert transitions == [3]

  def test_no_transition_for_silence_gaps(self):
    """Silence between voiced segments doesn't count as transition."""
    states = np.array([
      MouthState.O,
      MouthState.O,
      MouthState.CLOSED,
      MouthState.CLOSED,
      MouthState.OPEN,
      MouthState.OPEN,
    ])

    transitions = _detect_state_transitions(states)

    # No transitions because the O->OPEN change happens across silence
    assert transitions == []

  def test_multiple_transitions(self):
    states = np.array([
      MouthState.O,
      MouthState.OPEN,
      MouthState.O,
      MouthState.OPEN,
    ])

    transitions = _detect_state_transitions(states)

    assert transitions == [1, 2, 3]


class TestMergeBoundaryFrames:
  """Tests for _merge_boundary_frames helper."""

  def test_merges_nearby_boundaries(self):
    features = _AudioFeatures(
      centroid=np.zeros(100),
      rms=np.zeros(100),
      onset_env=np.zeros(100),
      sr=22050,
      hop_length=220,
    )

    onset_frames = np.array([10, 50])
    transition_frames = [12, 52]  # Close to onsets
    rhythmic_frames = [15, 55]  # Also close

    merged = _merge_boundary_frames(onset_frames, transition_frames,
                                    rhythmic_frames, features)

    # Should merge nearby frames (within ~60ms)
    # 60ms at sr=22050, hop=220 is about 6 frames
    assert len(merged) < len(onset_frames) + len(transition_frames) + len(
      rhythmic_frames)

  def test_preserves_distant_boundaries(self):
    features = _AudioFeatures(
      centroid=np.zeros(100),
      rms=np.zeros(100),
      onset_env=np.zeros(100),
      sr=22050,
      hop_length=220,
    )

    onset_frames = np.array([10, 50, 90])
    transition_frames = []
    rhythmic_frames = []

    merged = _merge_boundary_frames(onset_frames, transition_frames,
                                    rhythmic_frames, features)

    assert merged == [10, 50, 90]

  def test_handles_empty_inputs(self):
    features = _AudioFeatures(
      centroid=np.zeros(100),
      rms=np.zeros(100),
      onset_env=np.zeros(100),
      sr=22050,
      hop_length=220,
    )

    merged = _merge_boundary_frames(np.array([]), [], [], features)

    assert merged == []


class TestComputeThresholds:
  """Tests for _compute_thresholds helper."""

  def test_computes_hysteresis_thresholds(self):
    features = _AudioFeatures(
      centroid=np.array([500, 1000, 1500, 2000, 2500]),
      rms=np.array([0.5, 0.5, 0.5, 0.5, 0.5]),
      onset_env=np.zeros(5),
      sr=22050,
      hop_length=220,
    )

    thresholds = _compute_thresholds(features)

    # threshold_to_o should be less than threshold_to_open
    assert thresholds.centroid_threshold_to_o < thresholds.centroid_threshold_to_open
    # Difference should be hysteresis value
    diff = thresholds.centroid_threshold_to_open - thresholds.centroid_threshold_to_o
    assert diff == pytest.approx(syllable_detection._HYSTERESIS_HZ, rel=0.01)


class TestComputeFrameStates:
  """Tests for _compute_frame_states helper."""

  def test_marks_silence_as_closed(self):
    features = _AudioFeatures(
      centroid=np.array([1500, 1500, 1500]),
      rms=np.array([0.0, 0.5, 0.0]),
      onset_env=np.zeros(3),
      sr=22050,
      hop_length=220,
    )
    thresholds = _Thresholds(
      rms_threshold=0.1,
      centroid_threshold_to_o=1000.0,
      centroid_threshold_to_open=1200.0,
    )

    states = _compute_frame_states(features, thresholds)

    assert states[0] == MouthState.CLOSED
    assert states[1] == MouthState.OPEN
    assert states[2] == MouthState.CLOSED

  def test_classifies_based_on_centroid(self):
    features = _AudioFeatures(
      centroid=np.array([800, 800, 1500, 1500]),
      rms=np.array([0.5, 0.5, 0.5, 0.5]),
      onset_env=np.zeros(4),
      sr=22050,
      hop_length=220,
    )
    thresholds = _Thresholds(
      rms_threshold=0.1,
      centroid_threshold_to_o=1000.0,
      centroid_threshold_to_open=1200.0,
    )

    states = _compute_frame_states(features, thresholds)

    assert states[0] == MouthState.O
    assert states[1] == MouthState.O
    assert states[2] == MouthState.OPEN
    assert states[3] == MouthState.OPEN
