"""Generic scene script objects for deterministic video rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from common.posable_character import PosableCharacter
from common.posable_character_sequence import PosableCharacterSequence

FitMode = Literal["contain", "cover", "fill"]


@dataclass(frozen=True)
class SceneCanvas:
  """Canvas dimensions and optional solid background color."""

  width_px: int
  height_px: int
  background_rgba: tuple[int, int, int, int] = (0, 0, 0, 255)

  def validate(self) -> None:
    """Validate the canvas dimensions."""
    if int(self.width_px) <= 0 or int(self.height_px) <= 0:
      raise ValueError("SceneCanvas width_px and height_px must be positive")


@dataclass(frozen=True)
class SceneRect:
  """Absolute pixel rectangle on the output canvas."""

  x_px: int
  y_px: int
  width_px: int
  height_px: int

  def validate(self) -> None:
    """Validate the rectangle dimensions."""
    if int(self.width_px) <= 0 or int(self.height_px) <= 0:
      raise ValueError("SceneRect width_px and height_px must be positive")


@dataclass(frozen=True)
class TimedImage:
  """An image layer active on `[start_time_sec, end_time_sec)`."""

  gcs_uri: str
  start_time_sec: float
  end_time_sec: float
  z_index: int
  rect: SceneRect
  fit_mode: FitMode = "contain"


@dataclass(frozen=True)
class TimedCharacterSequence:
  """A character sequence clip active on `[start_time_sec, end_time_sec)`.

  `actor_id` identifies which sequence track this clip targets. Clips sharing
  the same actor id must not overlap in a valid script.
  """

  actor_id: str
  character: PosableCharacter
  sequence: PosableCharacterSequence
  start_time_sec: float
  end_time_sec: float
  z_index: int
  rect: SceneRect
  fit_mode: FitMode = "contain"


SceneItem = TimedImage | TimedCharacterSequence


@dataclass(frozen=True)
class SceneScript:
  """A generic deterministic scene timeline."""

  canvas: SceneCanvas
  items: list[SceneItem]
  duration_sec: float
  subtitle_rect: SceneRect | None = None

  def validate(self) -> None:
    """Validate item timing, geometry and actor overlap constraints."""
    self.canvas.validate()
    if float(self.duration_sec) <= 0:
      raise ValueError("SceneScript duration_sec must be > 0")

    character_items_by_actor: dict[str, list[TimedCharacterSequence]] = {}
    for index, item in enumerate(self.items):
      _validate_item_bounds(item,
                            duration_sec=float(self.duration_sec),
                            item_index=index)
      _validate_fit_mode(item.fit_mode, item_index=index)
      item.rect.validate()
      if isinstance(item, TimedCharacterSequence):
        character_items_by_actor.setdefault(item.actor_id, []).append(item)

    for actor_id, actor_items in character_items_by_actor.items():
      actor_items.sort(key=lambda entry: float(entry.start_time_sec))
      prior_end = -1.0
      for item in actor_items:
        if float(item.start_time_sec) < prior_end:
          raise ValueError(
            f"Overlapping character sequence items for actor_id '{actor_id}'")
        prior_end = float(item.end_time_sec)

      first_character = actor_items[0].character
      first_z_index = int(actor_items[0].z_index)
      first_rect = actor_items[0].rect
      first_fit_mode = actor_items[0].fit_mode
      for item in actor_items[1:]:
        if item.character is not first_character:
          raise ValueError(
            f"actor_id '{actor_id}' references multiple character objects")
        if int(item.z_index) != first_z_index:
          raise ValueError(
            f"actor_id '{actor_id}' uses inconsistent z_index values")
        if item.rect != first_rect:
          raise ValueError(
            f"actor_id '{actor_id}' uses inconsistent rect values")
        if item.fit_mode != first_fit_mode:
          raise ValueError(
            f"actor_id '{actor_id}' uses inconsistent fit_mode values")

      for item in actor_items:
        _validate_sequence_fits_item(item)


def _validate_fit_mode(fit_mode: str, *, item_index: int) -> None:
  if fit_mode not in ("contain", "cover", "fill"):
    raise ValueError(
      f"Scene item {item_index} has unsupported fit_mode '{fit_mode}'")


def _validate_item_bounds(
  item: SceneItem,
  *,
  duration_sec: float,
  item_index: int,
) -> None:
  start = float(item.start_time_sec)
  end = float(item.end_time_sec)
  if start < 0:
    raise ValueError(f"Scene item {item_index} start_time_sec must be >= 0")
  if end <= start:
    raise ValueError(
      f"Scene item {item_index} end_time_sec must be > start_time_sec")
  if end > float(duration_sec):
    raise ValueError(
      f"Scene item {item_index} end_time_sec exceeds script duration")


def _validate_sequence_fits_item(item: TimedCharacterSequence) -> None:
  item.sequence.validate()
  item_duration = float(item.end_time_sec) - float(item.start_time_sec)
  sequence_duration = _sequence_duration_sec(item.sequence)
  if sequence_duration > item_duration + 1e-6:
    raise ValueError(
      f"Sequence duration {sequence_duration:.3f}s exceeds item window "
      f"{item_duration:.3f}s for actor_id '{item.actor_id}'")


def _sequence_duration_sec(sequence: PosableCharacterSequence) -> float:
  max_end = 0.0
  tracks = [
    sequence.sequence_left_eye_open,
    sequence.sequence_right_eye_open,
    sequence.sequence_mouth_state,
    sequence.sequence_left_hand_visible,
    sequence.sequence_right_hand_visible,
    sequence.sequence_left_hand_transform,
    sequence.sequence_right_hand_transform,
    sequence.sequence_head_transform,
    sequence.sequence_sound_events,
  ]
  for track in tracks:
    for event in track:
      max_end = max(max_end, float(event.end_time))
  return max_end
