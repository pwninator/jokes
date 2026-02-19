"""Audio timing primitives (e.g., ElevenLabs TTS timestamps).

We represent timing at a word level for downstream lip-sync and clip splitting.
Each `WordTiming` includes both the word window and per-character timings within
that window.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CharTiming:
  """A single character with an absolute time window (seconds)."""

  char: str
  start_time: float
  end_time: float


@dataclass(frozen=True)
class WordTiming:
  """Timing for a single word plus its internal per-character timings."""

  word: str
  start_time: float
  end_time: float
  char_timings: list[CharTiming]


@dataclass(frozen=True)
class VoiceSegment:
  """A contiguous voiced segment in multi-speaker dialogue.

  Indices refer to the (normalized) word timing list, using a half-open span:
  `[word_start_index, word_end_index)`.
  """

  voice_id: str
  start_time_seconds: float
  end_time_seconds: float
  word_start_index: int
  word_end_index: int
  dialogue_input_index: int


@dataclass(frozen=True)
class TtsTiming:
  """Optional timing metadata returned by a TTS provider."""

  alignment: list[WordTiming] | None = None
  """The raw character alignment for the original text input."""

  normalized_alignment: list[WordTiming] | None = None
  """The provider-normalized text (e.g. punctuation/spacing adjustments) with a corresponding alignment. When available, it's typically
    the better choice for downstream processing because the characters match
    what the model actually spoke/timed."""

  voice_segments: list[VoiceSegment] = field(default_factory=list)

  @property
  def alignment_data(self) -> list[WordTiming] | None:
    """Alignment data, preferring normalized alignment when available."""
    return self.normalized_alignment or self.alignment
