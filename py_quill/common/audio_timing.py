"""Audio timing primitives (e.g., ElevenLabs character-level timestamps)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CharacterAlignment:
  """Character-level timing alignment.

  `characters[i]` corresponds to the time window:
    [`character_start_times_seconds[i]`, `character_end_times_seconds[i]`]
  """

  characters: list[str]
  character_start_times_seconds: list[float]
  character_end_times_seconds: list[float]


@dataclass(frozen=True)
class VoiceSegment:
  """A contiguous voiced segment in multi-speaker dialogue."""

  voice_id: str
  start_time_seconds: float
  end_time_seconds: float
  character_start_index: int
  character_end_index: int
  dialogue_input_index: int


@dataclass(frozen=True)
class TtsTiming:
  """Optional timing metadata returned by a TTS provider.

  Notes on alignment variants:
  - `alignment` is the raw character alignment for the original text input.
  - `normalized_alignment` is provider-normalized text (e.g. punctuation/spacing
    adjustments) with a corresponding alignment. When available, it's typically
    the better choice for downstream processing because the characters match
    what the model actually spoke/timed.
  """

  alignment: CharacterAlignment | None = None
  normalized_alignment: CharacterAlignment | None = None
  voice_segments: list[VoiceSegment] = field(default_factory=list)
