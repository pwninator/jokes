"""Python-native configuration objects for generating joke videos."""

from __future__ import annotations

from dataclasses import dataclass

from common import audio_timing
from common.posable_character import PosableCharacter


@dataclass(frozen=True)
class TimedImage:
  """A joke image asset that becomes active at `start_time_sec`."""
  gcs_uri: str
  start_time_sec: float


@dataclass(frozen=True)
class DialogClip:
  """A single spoken clip on a character timeline.

  `timing` carries provider word timing and is the only supported source for
  mouth-shape extraction in the new infra.
  """
  audio_gcs_uri: str
  start_time_sec: float
  transcript: str
  timing: list[audio_timing.WordTiming] | None


@dataclass(frozen=True)
class CharacterTrackSpec:
  """A renderable character plus all dialog clips attributed to it.

  `character_id` is a stable script-level identifier for timeline targeting.
  """
  character_id: str
  character: PosableCharacter
  dialogs: list[DialogClip]


@dataclass(frozen=True)
class PortraitJokeVideoScript:
  """Input spec for the portrait joke video (images + footer + characters)."""

  joke_images: list[TimedImage]
  footer_background_gcs_uri: str
  characters: list[CharacterTrackSpec]
  duration_sec: float
  fps: int = 24
  seed: int = 0


@dataclass(frozen=True)
class PortraitMouthTestVideoScript:
  """Input spec for the portrait mouth test grid video."""

  footer_background_gcs_uri: str
  characters: list[CharacterTrackSpec]
  duration_sec: float
  fps: int = 24
  seed: int = 0
