"""Tests for mouth event detection."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from common.mouth_events import MouthEvent
from common.posable_character import MouthState
from services import mouth_event_detection
from services import mouth_event_detection_librosa
from services import mouth_event_detection_parselmouth
from services.mouth_event_detection_librosa import (
  _AudioFeatures,
  _Thresholds,
  _compute_features,
  _compute_frame_states,
  _compute_thresholds,
  _detect_state_transitions,
  _find_runs,
  _merge_boundary_frames,
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
# Integration Tests - detect_syllables_for_lip_sync() (audio-only)
# =============================================================================


class TestDetectSyllablesIntegration:
  """Integration tests for the main syllable detection behavior."""

  def test_finds_multiple_onsets(self, monkeypatch):
    """Detects separate syllables from distinct sound bursts."""
    wav_bytes = _make_wav_bytes(segments=[
      (0.1, 0.08, 440.0),
      (0.4, 0.08, 440.0),
      (0.7, 0.08, 440.0),
    ], )
    syllables = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="librosa",
      transcript=None,
    )

    assert len(syllables) >= 3
    starts = [s.start_time for s in syllables]
    assert any(start == pytest.approx(0.08, abs=0.08) for start in starts)
    assert any(start == pytest.approx(0.38, abs=0.08) for start in starts)
    assert any(start == pytest.approx(0.68, abs=0.08) for start in starts)

  def test_handles_silence(self, monkeypatch):
    """Returns empty list for silent audio."""
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(8000, dtype=np.float32), 8000, format="WAV")
    wav_bytes = buffer.getvalue()
    monkeypatch.setattr(mouth_event_detection_parselmouth,
                        "_detect_segments_with_confidence_parselmouth",
                        lambda _wav_bytes: [])
    syllables = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="librosa",
      transcript=None,
    )
    parselmouth = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="parselmouth",
      transcript=None,
    )

    assert syllables == []
    assert parselmouth == []

  def test_handles_empty_audio(self, monkeypatch):
    """Returns empty list for empty audio."""
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(0, dtype=np.float32), 8000, format="WAV")
    wav_bytes = buffer.getvalue()
    monkeypatch.setattr(mouth_event_detection_parselmouth,
                        "_detect_segments_with_confidence_parselmouth",
                        lambda _wav_bytes: [])
    syllables = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="librosa",
      transcript=None,
    )
    parselmouth = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="parselmouth",
      transcript=None,
    )

    assert syllables == []
    assert parselmouth == []

  def test_falls_back_when_onsets_missing(self, monkeypatch):
    """Uses rhythmic fallback for sustained sounds without clear onsets."""
    wav_bytes = _make_wav_bytes(segments=[
      (0.0, 0.5, 440.0),
    ], )

    def fake_onset_detect(*_args, **_kwargs):
      return np.array([], dtype=int)

    monkeypatch.setattr(mouth_event_detection_librosa.librosa.onset, "onset_detect",
                        fake_onset_detect)
    syllables = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="librosa",
      transcript=None,
    )

    assert len(syllables) >= 2

  def test_syllables_have_valid_times(self, monkeypatch):
    """All syllables have positive duration and valid times."""
    wav_bytes = _make_wav_bytes(segments=[
      (0.1, 0.08, 440.0),
      (0.4, 0.08, 880.0),
    ], )
    syllables = mouth_event_detection.detect_mouth_events(
      wav_bytes,
      mode="librosa",
      transcript=None,
    )

    for s in syllables:
      assert s.start_time >= 0
      assert s.end_time > s.start_time
      assert s.mouth_shape in (MouthState.OPEN, MouthState.O)


class TestDetectSegmentsWithConfidenceParselmouth:

  def test_parselmouth_detects_o_and_open_from_f2(self, monkeypatch):
    import types

    class _FakeFormant:

      def get_value_at_time(self, formant_number, time_sec):
        if formant_number == 1:
          return 400.0 if float(time_sec) < 0.11 else 900.0
        if formant_number == 2:
          return 900.0 if float(time_sec) < 0.11 else 2200.0
        raise AssertionError(f"Unexpected formant_number={formant_number}")

    class _FakeIntensity:

      def get_value(self, _time_sec):
        return 70.0

    class _FakePitch:

      def get_value_at_time(self, _time_sec):
        return 170.0

    class _FakeSound:

      def __init__(self, _values, sampling_frequency):
        self.sampling_frequency = sampling_frequency

      def to_formant_burg(self, time_step):
        assert time_step == pytest.approx(0.01, rel=1e-6)
        return _FakeFormant()

      def to_intensity(self, time_step):
        assert time_step == pytest.approx(0.01, rel=1e-6)
        return _FakeIntensity()

      def to_pitch(self, time_step):
        assert time_step == pytest.approx(0.01, rel=1e-6)
        return _FakePitch()

    fake_parselmouth = types.SimpleNamespace(Sound=_FakeSound)
    monkeypatch.setattr(mouth_event_detection_parselmouth, "parselmouth", fake_parselmouth)

    wav_bytes = _make_wav_bytes(
      sample_rate=1000,
      duration_sec=0.2,
      segments=[(0.0, 0.2, 200.0)],
    )
    segments = mouth_event_detection_parselmouth._detect_segments_with_confidence_parselmouth(
      wav_bytes)

    shapes = {segment.mouth_shape for segment in segments}
    assert MouthState.O in shapes
    assert MouthState.OPEN in shapes

  def test_parselmouth_open_wins_when_f1_high_even_if_f2_low(
      self, monkeypatch):
    import types

    class _FakeFormant:

      def get_value_at_time(self, formant_number, _time_sec):
        if formant_number == 1:
          return 900.0
        if formant_number == 2:
          return 900.0
        raise AssertionError(f"Unexpected formant_number={formant_number}")

    class _FakeIntensity:

      def get_value(self, _time_sec):
        return 70.0

    class _FakePitch:

      def get_value_at_time(self, _time_sec):
        return 170.0

    class _FakeSound:

      def __init__(self, _values, sampling_frequency):
        self.sampling_frequency = sampling_frequency

      def to_formant_burg(self, time_step):
        assert time_step == pytest.approx(0.01, rel=1e-6)
        return _FakeFormant()

      def to_intensity(self, time_step):
        assert time_step == pytest.approx(0.01, rel=1e-6)
        return _FakeIntensity()

      def to_pitch(self, time_step):
        assert time_step == pytest.approx(0.01, rel=1e-6)
        return _FakePitch()

    fake_parselmouth = types.SimpleNamespace(Sound=_FakeSound)
    monkeypatch.setattr(mouth_event_detection_parselmouth, "parselmouth", fake_parselmouth)

    wav_bytes = _make_wav_bytes(
      sample_rate=1000,
      duration_sec=0.2,
      segments=[(0.0, 0.2, 200.0)],
    )
    segments = mouth_event_detection_parselmouth._detect_segments_with_confidence_parselmouth(
      wav_bytes)

    shapes = {segment.mouth_shape for segment in segments}
    assert MouthState.O not in shapes
    assert MouthState.OPEN in shapes


class TestTimingMode:

  def test_detect_mouth_events_timing_uses_word_timing(
      self, monkeypatch):
    from common import audio_timing
    from services import transcript_alignment

    monkeypatch.setattr(transcript_alignment, "text_to_shapes",
                        lambda _word: [MouthState.O])

    timing = [
      audio_timing.WordTiming(
        word="Hi",
        start_time=0.0,
        end_time=0.2,
        char_timings=[
          audio_timing.CharTiming(char="H", start_time=0.0, end_time=0.1),
          audio_timing.CharTiming(char="i", start_time=0.1, end_time=0.2),
        ],
      ),
    ]

    events = mouth_event_detection.detect_mouth_events(
      b"noop",
      mode="timing",
      timing=timing,
    )

    assert events
    assert all(isinstance(e, MouthEvent) for e in events)

  def test_detect_mouth_events_timing_does_not_merge_adjacent_same_shape_events(
    self,
    monkeypatch,
  ):
    from common import audio_timing
    from services import transcript_alignment

    monkeypatch.setattr(
      transcript_alignment,
      "text_to_shapes",
      lambda _word: [MouthState.OPEN, MouthState.OPEN],
    )

    timing = [
      audio_timing.WordTiming(
        word="Hi",
        start_time=0.0,
        end_time=1.0,
        char_timings=[
          audio_timing.CharTiming(char="H", start_time=0.0, end_time=0.5),
          audio_timing.CharTiming(char="i", start_time=0.5, end_time=1.0),
        ],
      ),
    ]

    events = mouth_event_detection.detect_mouth_events(
      b"noop",
      mode="timing",
      timing=timing,
    )

    # The two OPEN phonemes should remain separate after post-processing.
    open_events = [e for e in events if e.mouth_shape == MouthState.OPEN]
    assert len(open_events) == 2


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

    monkeypatch.setattr(mouth_event_detection_librosa, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10, 40]),
    )
    # Disable rhythmic fallback to test only onset-based detection
    monkeypatch.setattr(mouth_event_detection_librosa, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    monkeypatch.setattr(
      mouth_event_detection_parselmouth,
      "_detect_segments_with_confidence_parselmouth",
      lambda wav_bytes: mouth_event_detection_librosa._detect_segments_with_confidence(
        wav_bytes),
    )
    syllables = mouth_event_detection.detect_mouth_events(
      b"dummy",
      mode="librosa",
      transcript=None,
    )

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

    monkeypatch.setattr(mouth_event_detection_librosa, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback
    monkeypatch.setattr(mouth_event_detection_librosa, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    monkeypatch.setattr(
      mouth_event_detection_parselmouth,
      "_detect_segments_with_confidence_parselmouth",
      lambda wav_bytes: mouth_event_detection_librosa._detect_segments_with_confidence(
        wav_bytes),
    )
    syllables = mouth_event_detection.detect_mouth_events(
      b"dummy",
      mode="librosa",
      transcript=None,
    )

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

    monkeypatch.setattr(mouth_event_detection_librosa, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback
    monkeypatch.setattr(mouth_event_detection_librosa, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    monkeypatch.setattr(
      mouth_event_detection_parselmouth,
      "_detect_segments_with_confidence_parselmouth",
      lambda wav_bytes: mouth_event_detection_librosa._detect_segments_with_confidence(
        wav_bytes),
    )
    syllables = mouth_event_detection.detect_mouth_events(
      b"dummy",
      mode="librosa",
      transcript=None,
    )

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

    monkeypatch.setattr(mouth_event_detection_librosa, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback to test only onset + transition detection
    monkeypatch.setattr(mouth_event_detection_librosa, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    monkeypatch.setattr(
      mouth_event_detection_parselmouth,
      "_detect_segments_with_confidence_parselmouth",
      lambda wav_bytes: mouth_event_detection_librosa._detect_segments_with_confidence(
        wav_bytes),
    )
    syllables = mouth_event_detection.detect_mouth_events(
      b"dummy",
      mode="librosa",
      transcript=None,
    )

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

    monkeypatch.setattr(mouth_event_detection_librosa, "_load_audio", lambda _:
                        (np.zeros(sr), sr))
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "spectral_centroid",
      lambda **kwargs: centroid.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.feature,
      "rms",
      lambda **kwargs: rms.reshape(1, -1),
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_strength",
      lambda **kwargs: onset_env,
    )
    monkeypatch.setattr(
      mouth_event_detection_librosa.librosa.onset,
      "onset_detect",
      lambda **kwargs: np.array([10]),
    )
    # Disable rhythmic fallback to test only onset + transition detection
    monkeypatch.setattr(mouth_event_detection_librosa, "_build_rhythmic_frames",
                        lambda *a, **k: [])

    monkeypatch.setattr(
      mouth_event_detection_parselmouth,
      "_detect_segments_with_confidence_parselmouth",
      lambda wav_bytes: mouth_event_detection_librosa._detect_segments_with_confidence(
        wav_bytes),
    )
    syllables = mouth_event_detection.detect_mouth_events(
      b"dummy",
      mode="librosa",
      transcript=None,
    )

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
    assert diff == pytest.approx(mouth_event_detection_librosa._HYSTERESIS_HZ, rel=0.01)


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


# =============================================================================
# Confidence Scoring Tests
# =============================================================================


class TestDetectSegmentsWithConfidence:
  """Tests for detect_segments_with_confidence function."""

  def test_returns_audio_segments(self):
    """Should return AudioSegment objects with confidence scores."""
    from services.mouth_event_detection_librosa import (
      _detect_segments_with_confidence, )

    wav_bytes = _make_wav_bytes(segments=[
      (0.1, 0.08, 440.0),
      (0.4, 0.08, 880.0),
    ])
    segments = _detect_segments_with_confidence(wav_bytes)

    assert len(segments) >= 2
    for seg in segments:
      assert isinstance(seg, MouthEvent)
      assert 0.0 <= seg.confidence <= 1.0
      assert seg.mean_centroid >= 0
      assert seg.mean_rms >= 0

  def test_silence_returns_empty(self):
    """Silent audio should return empty list."""
    from services.mouth_event_detection_librosa import _detect_segments_with_confidence

    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(8000, dtype=np.float32), 8000, format="WAV")
    segments = _detect_segments_with_confidence(buffer.getvalue())

    assert segments == []

  def test_high_centroid_has_higher_confidence(self):
    """Extreme centroid values should have higher confidence than ambiguous ones."""
    from services.mouth_event_detection_librosa import (
      _compute_segment_confidence, )

    # Extreme centroid (far from 1200Hz)
    high_conf = _compute_segment_confidence(
      mean_centroid=2500.0,
      mean_rms=0.5,
      rms_max=1.0,
      duration=0.1,
    )

    # Ambiguous centroid (near 1200Hz)
    low_conf = _compute_segment_confidence(
      mean_centroid=1200.0,
      mean_rms=0.5,
      rms_max=1.0,
      duration=0.1,
    )

    assert high_conf > low_conf

  def test_longer_duration_has_higher_confidence(self):
    """Longer segments should have higher confidence."""
    from services.mouth_event_detection_librosa import (
      _compute_segment_confidence, )

    short_conf = _compute_segment_confidence(
      mean_centroid=2000.0,
      mean_rms=0.5,
      rms_max=1.0,
      duration=0.02,  # Very short
    )

    long_conf = _compute_segment_confidence(
      mean_centroid=2000.0,
      mean_rms=0.5,
      rms_max=1.0,
      duration=0.15,  # Longer
    )

    assert long_conf > short_conf

  def test_higher_energy_has_higher_confidence(self):
    """Louder segments should have higher confidence."""
    from services.mouth_event_detection_librosa import (
      _compute_segment_confidence, )

    quiet_conf = _compute_segment_confidence(
      mean_centroid=2000.0,
      mean_rms=0.1,
      rms_max=1.0,
      duration=0.1,
    )

    loud_conf = _compute_segment_confidence(
      mean_centroid=2000.0,
      mean_rms=0.9,
      rms_max=1.0,
      duration=0.1,
    )

    assert loud_conf > quiet_conf

  def test_confidence_bounded_zero_to_one(self):
    """Confidence should always be between 0 and 1."""
    from services.mouth_event_detection_librosa import (
      _compute_segment_confidence, )

    # Edge cases
    test_cases = [
      {
        "mean_centroid": 0.0,
        "mean_rms": 0.0,
        "rms_max": 1.0,
        "duration": 0.0
      },
      {
        "mean_centroid": 10000.0,
        "mean_rms": 2.0,
        "rms_max": 1.0,
        "duration": 1.0
      },
      {
        "mean_centroid": 1200.0,
        "mean_rms": 0.5,
        "rms_max": 0.0,
        "duration": 0.1
      },
    ]

    for kwargs in test_cases:
      conf = _compute_segment_confidence(**kwargs)
      assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds for {kwargs}"


# =============================================================================
# Lip-Sync API Tests
# =============================================================================


class TestDetectSyllablesForLipSync:
  """Tests for detect_syllables_for_lip_sync public API."""

  def test_without_transcript_maps_segments_to_syllables(self, monkeypatch):

    def fake_detect_segments_librosa(_wav_bytes: bytes):
      return [
        MouthEvent(
          start_time=0.0,
          end_time=0.1,
          mouth_shape=MouthState.O,
          confidence=0.9,
          mean_centroid=900.0,
          mean_rms=0.5,
        ),
      ]

    def fake_detect_segments_parselmouth(_wav_bytes: bytes):
      return [
        MouthEvent(
          start_time=0.0,
          end_time=0.1,
          mouth_shape=MouthState.OPEN,
          confidence=0.8,
          mean_centroid=2000.0,
          mean_rms=0.4,
        ),
      ]

    monkeypatch.setattr(mouth_event_detection_librosa, "_detect_segments_with_confidence",
                        fake_detect_segments_librosa)
    monkeypatch.setattr(mouth_event_detection_parselmouth,
                        "_detect_segments_with_confidence_parselmouth",
                        fake_detect_segments_parselmouth)

    librosa_result = mouth_event_detection.detect_mouth_events(
      b"noop",
      mode="librosa",
      transcript=None,
    )
    parselmouth_result = mouth_event_detection.detect_mouth_events(
      b"noop",
      mode="parselmouth",
      transcript=None,
    )

    assert librosa_result == [
      MouthEvent(start_time=0.0,
                 end_time=0.1,
                 mouth_shape=MouthState.O,
                 confidence=0.9,
                 mean_centroid=900.0,
                 mean_rms=0.5),
    ]
    assert parselmouth_result == [
      MouthEvent(start_time=0.0,
                 end_time=0.1,
                 mouth_shape=MouthState.OPEN,
                 confidence=0.8,
                 mean_centroid=2000.0,
                 mean_rms=0.4),
    ]

  def test_with_transcript_uses_alignment_pipeline(self, monkeypatch):
    from services import transcript_alignment

    def fake_detect_segments_librosa(_wav_bytes: bytes):
      return [
        MouthEvent(
          start_time=0.0,
          end_time=0.12,
          mouth_shape=MouthState.OPEN,
          confidence=0.25,
          mean_centroid=1500.0,
          mean_rms=0.5,
        ),
      ]

    def fake_detect_segments_parselmouth(_wav_bytes: bytes):
      return [
        MouthEvent(
          start_time=0.0,
          end_time=0.12,
          mouth_shape=MouthState.O,
          confidence=0.45,
          mean_centroid=900.0,
          mean_rms=0.4,
        ),
      ]

    captured: dict[str, object] = {"calls": []}

    def fake_align_with_text(text: str, segments):
      captured["calls"].append((text, segments))
      # Return a deterministic shape to prove both paths were aligned.
      mouth_shape = (MouthState.O if segments and segments[0].confidence
                     == pytest.approx(0.25, rel=0.001) else MouthState.OPEN)
      return [
        MouthEvent(
          start_time=0.0,
          end_time=0.12,
          mouth_shape=mouth_shape,
          confidence=(segments[0].confidence if segments else 0.0),
          mean_centroid=(segments[0].mean_centroid if segments else 0.0),
          mean_rms=(segments[0].mean_rms if segments else 0.0),
        ),
      ]

    monkeypatch.setattr(mouth_event_detection_librosa, "_detect_segments_with_confidence",
                        fake_detect_segments_librosa)
    monkeypatch.setattr(mouth_event_detection_parselmouth,
                        "_detect_segments_with_confidence_parselmouth",
                        fake_detect_segments_parselmouth)
    monkeypatch.setattr(transcript_alignment, "align_with_text",
                        fake_align_with_text)

    librosa_result = mouth_event_detection.detect_mouth_events(
      b"noop",
      mode="librosa",
      transcript="hello",
    )
    parselmouth_result = mouth_event_detection.detect_mouth_events(
      b"noop",
      mode="parselmouth",
      transcript="hello",
    )

    calls = captured["calls"]
    assert isinstance(calls, list)
    assert len(calls) == 2
    assert calls[0][0] == "hello"
    assert calls[1][0] == "hello"

    assert librosa_result == [
      MouthEvent(start_time=0.0,
                 end_time=0.12,
                 mouth_shape=MouthState.O,
                 confidence=0.25,
                 mean_centroid=1500.0,
                 mean_rms=0.5),
    ]
    assert parselmouth_result == [
      MouthEvent(start_time=0.0,
                 end_time=0.12,
                 mouth_shape=MouthState.OPEN,
                 confidence=0.45,
                 mean_centroid=900.0,
                 mean_rms=0.4),
    ]
