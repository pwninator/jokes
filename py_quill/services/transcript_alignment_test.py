"""Tests for transcript alignment module."""

from __future__ import annotations

import pytest
from common.mouth_events import MouthEvent
from common.posable_character import MouthState
from services.transcript_alignment import (
  _VOWEL_TO_SHAPES,
  _compute_match_cost,
  _compute_skip_audio_cost,
  _dp_align,
  align_shapes,
  align_with_text,
  text_to_shapes,
)

# =============================================================================
# Tests for text_to_shapes()
# =============================================================================


class TestTextToShapes:
  """Tests for text to mouth shape conversion."""

  def test_empty_text_returns_empty_list(self):
    assert text_to_shapes("") == []
    assert text_to_shapes("   ") == []

  def test_single_word_open_vowel(self):
    # "cat" has /æ/ which maps to OPEN
    shapes = text_to_shapes("cat")
    assert MouthState.OPEN in shapes

  def test_single_word_rounded_vowel(self):
    # "book" has /ʊ/ which maps to O
    shapes = text_to_shapes("book")
    assert MouthState.O in shapes

  def test_diphthong_cow_expands_to_two_shapes(self):
    # "cow" has /aʊ/ which expands to [OPEN, O]
    shapes = text_to_shapes("cow")
    assert shapes == [MouthState.OPEN, MouthState.O]

  def test_diphthong_boy_expands_to_two_shapes(self):
    # "boy" has /ɔɪ/ which expands to [O, OPEN]
    shapes = text_to_shapes("boy")
    assert shapes == [MouthState.O, MouthState.OPEN]

  def test_diphthong_go_stays_rounded(self):
    # "go" has /oʊ/ which stays as [O]
    shapes = text_to_shapes("go")
    assert shapes == [MouthState.O]

  def test_multiple_words(self):
    # "hello world" - multiple vowels
    shapes = text_to_shapes("hello world")
    assert len(shapes) >= 2

  def test_consonants_only_returns_empty(self):
    # "shh" has no vowels
    shapes = text_to_shapes("shh")
    assert shapes == []

  def test_sentence_extracts_all_vowels(self):
    # "Hey want to hear a joke" should have multiple vowel sounds
    shapes = text_to_shapes("Hey want to hear a joke")
    assert len(shapes) >= 5  # At least one per word with vowels

  def test_stress_markers_stripped(self):
    # G2P returns vowels with stress markers like AA0, AA1, AA2
    # These should be handled correctly
    shapes = text_to_shapes("about")  # Has unstressed schwa
    assert len(shapes) >= 1


class TestVowelMapping:
  """Tests for the vowel to shape mapping table."""

  def test_all_vowels_have_mappings(self):
    """Ensure all common ARPABET vowels are mapped."""
    expected_vowels = {
      "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW",
      "OY", "UH", "UW"
    }
    for vowel in expected_vowels:
      assert vowel in _VOWEL_TO_SHAPES, f"Missing mapping for {vowel}"

  def test_all_mappings_are_valid_mouth_states(self):
    """Ensure all mapped values are valid MouthState values."""
    for vowel, shapes in _VOWEL_TO_SHAPES.items():
      assert len(shapes) >= 1, f"{vowel} has empty shape list"
      for shape in shapes:
        assert isinstance(shape,
                          MouthState), (f"{vowel} has invalid shape {shape}")


# =============================================================================
# Tests for align_shapes() and DP alignment
# =============================================================================


class TestAlignShapes:
  """Tests for shape alignment."""

  def test_empty_audio_returns_empty(self):
    text_shapes = [MouthState.OPEN, MouthState.O]
    result = align_shapes(text_shapes, [])
    assert result == []

  def test_empty_text_uses_audio_shapes(self):
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
      MouthEvent(0.1, 0.2, MouthState.O, 0.9),
    ]
    result = align_shapes([], audio_segments)
    assert len(result) == 2
    assert result[0].mouth_shape == MouthState.OPEN
    assert result[1].mouth_shape == MouthState.O

  def test_perfect_alignment_uses_text_shapes(self):
    """When text and audio shapes match exactly, use text shapes."""
    text_shapes = [MouthState.OPEN, MouthState.O]
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
      MouthEvent(0.1, 0.2, MouthState.O, 0.9),
    ]
    result = align_shapes(text_shapes, audio_segments)
    assert len(result) == 2
    assert result[0].mouth_shape == MouthState.OPEN
    assert result[1].mouth_shape == MouthState.O

  def test_text_overrides_low_confidence_audio(self):
    """Text shapes should override low-confidence audio guesses."""
    text_shapes = [MouthState.O]  # Text says O
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.2),  # Low confidence OPEN
    ]
    result = align_shapes(text_shapes, audio_segments)
    assert len(result) == 1
    assert result[0].mouth_shape == MouthState.O

  def test_preserves_timing_from_audio(self):
    """Result should have timing from audio segments."""
    text_shapes = [MouthState.OPEN]
    audio_segments = [
      MouthEvent(0.5, 0.8, MouthState.O, 0.5),
    ]
    result = align_shapes(text_shapes, audio_segments)
    assert result[0].start_time == 0.5
    assert result[0].end_time == 0.8

  def test_extra_audio_segments_use_audio_shape(self):
    """Extra audio segments without text should use audio shapes."""
    text_shapes = [MouthState.OPEN]  # Only one text shape
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
      MouthEvent(0.1, 0.2, MouthState.O, 0.9),  # Extra segment (e.g., laughter)
    ]
    result = align_shapes(text_shapes, audio_segments)
    assert len(result) == 2
    # First should match text
    # Second should use audio shape since text is exhausted
    assert result[1].mouth_shape == MouthState.O

  def test_handles_count_mismatch_more_text_than_audio(self):
    """When there are more text shapes than audio, some text is skipped."""
    text_shapes = [MouthState.OPEN, MouthState.O, MouthState.OPEN]
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
      MouthEvent(0.1, 0.2, MouthState.O, 0.8),
    ]
    result = align_shapes(text_shapes, audio_segments)
    # Should have 2 segments (matching audio count)
    assert len(result) == 2


class TestDPAlign:
  """Tests for the dynamic programming alignment algorithm."""

  def test_dp_handles_empty_inputs(self):
    result = _dp_align([], [])
    assert result == []

  def test_dp_matches_identical_sequences(self):
    text = [MouthState.OPEN, MouthState.O]
    audio = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
      MouthEvent(0.1, 0.2, MouthState.O, 0.8),
    ]
    alignment = _dp_align(text, audio)
    assert len(alignment) == 2
    # Each audio should match corresponding text
    assert alignment[0] == (0, 0)  # audio[0] -> text[0]
    assert alignment[1] == (1, 1)  # audio[1] -> text[1]

  def test_dp_skips_high_confidence_mismatch(self):
    """High confidence audio that disagrees should be skipped (no text consumed)."""
    text = [MouthState.O]  # One O expected
    audio = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.95),  # High conf OPEN (noise?)
      MouthEvent(0.1, 0.2, MouthState.O, 0.9),  # High conf O (real word)
    ]
    alignment = _dp_align(text, audio)
    # Should skip first audio, match second to text
    assert len(alignment) == 2
    # First audio skipped (text_idx = None)
    assert alignment[0][1] is None
    # Second audio matched to text[0]
    assert alignment[1] == (1, 0)


class TestCostFunctions:
  """Tests for alignment cost functions."""

  def test_match_cost_zero_when_shapes_agree(self):
    segment = MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8)
    cost = _compute_match_cost(MouthState.OPEN, segment)
    assert cost == 0.0

  def test_match_cost_higher_with_high_confidence_mismatch(self):
    low_conf = MouthEvent(0.0, 0.1, MouthState.OPEN, 0.2)
    high_conf = MouthEvent(0.0, 0.1, MouthState.OPEN, 0.9)

    low_cost = _compute_match_cost(MouthState.O, low_conf)
    high_cost = _compute_match_cost(MouthState.O, high_conf)

    assert high_cost > low_cost

  def test_skip_audio_cost_higher_for_confident_segments(self):
    low_conf = MouthEvent(0.0, 0.1, MouthState.OPEN, 0.1)
    high_conf = MouthEvent(0.0, 0.1, MouthState.OPEN, 0.9)

    low_cost = _compute_skip_audio_cost(low_conf)
    high_cost = _compute_skip_audio_cost(high_conf)

    assert high_cost > low_cost


# =============================================================================
# Tests for align_with_text()
# =============================================================================


class TestAlignWithText:
  """Tests for the convenience function that takes raw text."""

  def test_aligns_simple_sentence(self):
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
      MouthEvent(0.1, 0.2, MouthState.O, 0.8),
      MouthEvent(0.2, 0.3, MouthState.OPEN, 0.8),
    ]
    result = align_with_text("hello", audio_segments)
    assert len(result) >= 1

  def test_handles_empty_text(self):
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
    ]
    result = align_with_text("", audio_segments)
    assert len(result) == 1

  def test_returns_aligned_segment_objects(self):
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),
    ]
    result = align_with_text("cat", audio_segments)
    assert all(isinstance(seg, MouthEvent) for seg in result)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
  """Integration tests for realistic scenarios."""

  def test_joke_setup_alignment(self):
    """Test alignment for typical joke setup text."""
    text = "Hey want to hear a joke? Why did the chicken cross the road?"
    audio_segments = [
      MouthEvent(0.0, 0.15, MouthState.OPEN, 0.7),
      MouthEvent(0.15, 0.3, MouthState.O, 0.6),
      MouthEvent(0.3, 0.45, MouthState.OPEN, 0.8),
      MouthEvent(0.45, 0.6, MouthState.O, 0.7),
      MouthEvent(0.6, 0.75, MouthState.OPEN, 0.8),
      MouthEvent(0.75, 0.9, MouthState.OPEN, 0.6),
      MouthEvent(0.9, 1.05, MouthState.O, 0.7),
      MouthEvent(1.05, 1.2, MouthState.OPEN, 0.8),
    ]
    result = align_with_text(text, audio_segments)

    # Should have same number of segments as audio
    assert len(result) == len(audio_segments)
    # All should have valid timing
    for seg in result:
      assert seg.start_time >= 0
      assert seg.end_time > seg.start_time
      assert seg.mouth_shape in (MouthState.OPEN, MouthState.O)

  def test_what_response_alignment(self):
    """Test alignment for simple 'what?' response."""
    text = "what?"
    audio_segments = [
      MouthEvent(0.0, 0.2, MouthState.O, 0.7),  # 'wh' + vowel
    ]
    result = align_with_text(text, audio_segments)

    assert len(result) == 1
    # "what" vowel is /ʌ/ which should be OPEN
    assert result[0].mouth_shape == MouthState.OPEN

  def test_laughter_fallback_to_audio(self):
    """Test that segments beyond text (laughter) use audio shapes."""
    text = "Ha"  # Very short text
    audio_segments = [
      MouthEvent(0.0, 0.1, MouthState.OPEN, 0.8),  # "Ha"
      MouthEvent(0.1, 0.2, MouthState.OPEN, 0.8),  # laughter
      MouthEvent(0.2, 0.3, MouthState.OPEN, 0.7),  # laughter
      MouthEvent(0.3, 0.4, MouthState.OPEN, 0.6),  # laughter
    ]
    result = align_with_text(text, audio_segments)

    # First segment should use text, rest should use audio
    assert len(result) == 4
