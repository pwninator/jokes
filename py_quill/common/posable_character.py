"""Base class for posable sprite-based characters."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Iterator

from PIL import Image

if TYPE_CHECKING:
  from common.posable_character_sequence import (PosableCharacterSequence,
                                                 SequenceSoundEvent)
from common import models
from services import cloud_storage


class MouthState(Enum):
  """State of the mouth for a posable character."""

  CLOSED = "CLOSED"
  OPEN = "OPEN"
  O = "O"


@dataclass(frozen=True)
class Transform:
  """Translation and scaling transform for a sprite component."""

  translate_x: float = 0.0
  translate_y: float = 0.0
  scale_x: float = 1.0
  scale_y: float = 1.0

  @staticmethod
  def from_tuple(
    values: tuple[float, float] | tuple[float, float, float, float]
  ) -> "Transform":
    """Create a Transform from (tx, ty) or (tx, ty, sx, sy)."""
    if len(values) == 2:
      translate_x, translate_y = values
      return Transform(translate_x=translate_x, translate_y=translate_y)
    if len(values) == 4:
      translate_x, translate_y, scale_x, scale_y = values
      return Transform(
        translate_x=translate_x,
        translate_y=translate_y,
        scale_x=scale_x,
        scale_y=scale_y,
      )
    raise ValueError("Transform tuple must have 2 or 4 values")


class PosableCharacter:
  """Runtime class for a posable character state, using a shared definition."""

  def __init__(self, definition: models.PosableCharacterDef):
    self.definition = definition
    self.left_eye_open = True
    self.right_eye_open = True
    self.mouth_state = MouthState.OPEN
    self.left_hand_visible = True
    self.right_hand_visible = True
    self.left_hand_transform = Transform()
    self.right_hand_transform = Transform()
    self.head_transform = Transform()
    self._image_cache: dict[tuple[object, ...], Image.Image] = {}
    self._component_cache: dict[str, Image.Image] = {}

  @classmethod
  def from_def(cls, definition: models.PosableCharacterDef) -> PosableCharacter:
    """Create a PosableCharacter instance from a definition."""
    return cls(definition=definition)

  def set_pose(
    self,
    *,
    left_eye_open: bool | None = None,
    right_eye_open: bool | None = None,
    mouth_state: MouthState | None = None,
    left_hand_visible: bool | None = None,
    right_hand_visible: bool | None = None,
    left_hand_transform: Transform | tuple[float, float]
    | tuple[float, float, float, float] | None = None,
    right_hand_transform: Transform | tuple[float, float]
    | tuple[float, float, float, float] | None = None,
    head_transform: Transform | tuple[float, float]
    | tuple[float, float, float, float] | None = None,
  ) -> None:
    """Set the pose state; only provided params are updated."""
    if left_eye_open is not None:
      self.left_eye_open = left_eye_open
    if right_eye_open is not None:
      self.right_eye_open = right_eye_open
    if mouth_state is not None:
      self.mouth_state = mouth_state
    if left_hand_visible is not None:
      self.left_hand_visible = left_hand_visible
    if right_hand_visible is not None:
      self.right_hand_visible = right_hand_visible
    if left_hand_transform is not None:
      self.left_hand_transform = _coerce_transform(left_hand_transform)
    if right_hand_transform is not None:
      self.right_hand_transform = _coerce_transform(right_hand_transform)
    if head_transform is not None:
      self.head_transform = _coerce_transform(head_transform)

  def get_image(self) -> Image.Image:
    """Return a PIL image of the current pose, using cache if available."""
    self._validate_assets()
    cache_key = self._get_pose_cache_key()
    cached = self._image_cache.get(cache_key)
    if cached is not None:
      return cached

    def_ = self.definition
    canvas = Image.new("RGBA", (def_.width, def_.height), (0, 0, 0, 0))

    head_image = self._load_component(def_.head_gcs_uri)
    self._paste_component(canvas, head_image, self.head_transform)

    left_eye_uri = (def_.left_eye_open_gcs_uri
                    if self.left_eye_open else def_.left_eye_closed_gcs_uri)
    right_eye_uri = (def_.right_eye_open_gcs_uri
                     if self.right_eye_open else def_.right_eye_closed_gcs_uri)
    mouth_uri = _get_mouth_gcs_uri(self)

    left_eye_image = self._load_component(left_eye_uri)
    right_eye_image = self._load_component(right_eye_uri)
    mouth_image = self._load_component(mouth_uri)

    self._paste_component(canvas, left_eye_image, self.head_transform)
    self._paste_component(canvas, right_eye_image, self.head_transform)
    self._paste_component(canvas, mouth_image, self.head_transform)

    if self.left_hand_visible:
      left_hand_image = self._load_component(def_.left_hand_gcs_uri)
      self._paste_component(canvas, left_hand_image, self.left_hand_transform)
    if self.right_hand_visible:
      right_hand_image = self._load_component(def_.right_hand_gcs_uri)
      self._paste_component(canvas, right_hand_image,
                            self.right_hand_transform)

    self._image_cache[cache_key] = canvas
    return canvas

  def _get_pose_cache_key(self) -> tuple[object, ...]:
    return (
      self.left_eye_open,
      self.right_eye_open,
      self.mouth_state,
      self.left_hand_visible,
      self.right_hand_visible,
      self.left_hand_transform,
      self.right_hand_transform,
      self.head_transform,
    )

  def _load_component(self, gcs_uri: str) -> Image.Image:
    cached = self._component_cache.get(gcs_uri)
    if cached is not None:
      return cached
    image = cloud_storage.download_image_from_gcs(gcs_uri).convert("RGBA")
    self._component_cache[gcs_uri] = image
    return image

  def _paste_component(self, canvas: Image.Image, component: Image.Image,
                       transform: Transform) -> None:
    transformed, x, y = self._apply_transform(component, transform,
                                              canvas.size)
    canvas.paste(transformed, (x, y), transformed)

  def _apply_transform(
    self,
    component: Image.Image,
    transform: Transform,
    canvas_size: tuple[int, int],
  ) -> tuple[Image.Image, int, int]:
    target_width = max(1, int(round(component.width * transform.scale_x)))
    target_height = max(1, int(round(component.height * transform.scale_y)))
    resized = component
    if (target_width, target_height) != component.size:
      resized = component.resize(
        (target_width, target_height),
        resample=Image.Resampling.LANCZOS,
      )
    base_x = (canvas_size[0] - target_width) / 2
    base_y = (canvas_size[1] - target_height) / 2
    x = int(round(base_x + transform.translate_x))
    y = int(round(base_y + transform.translate_y))
    return resized, x, y

  def _validate_assets(self) -> None:
    d = self.definition
    required = {
      "width": d.width,
      "height": d.height,
      "head_gcs_uri": d.head_gcs_uri,
      "left_hand_gcs_uri": d.left_hand_gcs_uri,
      "right_hand_gcs_uri": d.right_hand_gcs_uri,
      "mouth_open_gcs_uri": d.mouth_open_gcs_uri,
      "mouth_closed_gcs_uri": d.mouth_closed_gcs_uri,
      "mouth_o_gcs_uri": d.mouth_o_gcs_uri,
      "left_eye_open_gcs_uri": d.left_eye_open_gcs_uri,
      "left_eye_closed_gcs_uri": d.left_eye_closed_gcs_uri,
      "right_eye_open_gcs_uri": d.right_eye_open_gcs_uri,
      "right_eye_closed_gcs_uri": d.right_eye_closed_gcs_uri,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
      raise ValueError("PosableCharacter definition must have: " +
                       ", ".join(missing))


def _coerce_transform(
  transform: Transform | tuple[float, float]
  | tuple[float, float, float, float]
) -> Transform:
  if isinstance(transform, Transform):
    return transform
  return Transform.from_tuple(transform)


def _get_mouth_gcs_uri(character: PosableCharacter) -> str:
  if character.mouth_state == MouthState.OPEN:
    return character.definition.mouth_open_gcs_uri
  if character.mouth_state == MouthState.O:
    return character.definition.mouth_o_gcs_uri
  return character.definition.mouth_closed_gcs_uri


def generate_frames(
  character: PosableCharacter,
  sequence: "PosableCharacterSequence",
  fps: float,
) -> Iterator[tuple[float, Image.Image, list["SequenceSoundEvent"]]]:
  """Generate frames and audio events from a sequence.

  Args:
    character: The character instance to animate (will be mutated).
    sequence: The animation sequence.
    fps: Frames per second.

  Yields:
    (timestamp, frame_image, starting_sounds) tuples.
  """
  if fps <= 0:
    raise ValueError("fps must be positive")

  # Calculate total duration
  all_events = []
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
    all_events.extend(track)

  def get_end_time(e):
    if hasattr(e, "end_time") and e.end_time is not None:
      return e.end_time
    return e.start_time

  total_duration = 0.0
  if all_events:
    total_duration = max(get_end_time(e) for e in all_events)

  # Ensure we capture the last moment
  total_frames = int(math.ceil(total_duration * fps)) + 1

  # Sort sound events for efficient checking
  sorted_sounds = sorted(sequence.sequence_sound_events,
                         key=lambda e: e.start_time)
  sound_idx = 0

  dt = 1.0 / fps

  # State tracking for interpolation (indices in track lists)
  # We assume tracks are sorted by start_time (guaranteed by validate())
  track_indices = {
    "sequence_left_eye_open": 0,
    "sequence_right_eye_open": 0,
    "sequence_mouth_state": 0,
    "sequence_left_hand_visible": 0,
    "sequence_right_hand_visible": 0,
    "sequence_left_hand_transform": 0,
    "sequence_right_hand_transform": 0,
    "sequence_head_transform": 0,
  }

  def get_boolean_value(track, track_name, time, default):
    idx = track_indices[track_name]
    # Advance index if current event ended before time
    while idx < len(track) and track[idx].end_time < time:
      idx += 1
    track_indices[track_name] = idx  # Update state

    # Check if we are inside an event
    if idx < len(track):
      event = track[idx]
      if event.start_time <= time <= event.end_time:
        return event.value
    return default

  def get_mouth_state(track, track_name, time, default):
    idx = track_indices[track_name]
    while idx < len(track) and track[idx].end_time < time:
      idx += 1
    track_indices[track_name] = idx

    if idx < len(track):
      event = track[idx]
      if event.start_time <= time <= event.end_time:
        return event.mouth_state
    return default

  def get_transform_value(track, track_name, time, default):
    idx = track_indices[track_name]
    # For transforms, we need the *active* event for interpolation
    # OR the *last finished* event for holding.

    # 1. Find the first event that ends >= time (potential active event)
    #    or is the first event that starts > time (future event)
    curr = idx
    while curr < len(track) and track[curr].end_time < time:
      curr += 1

    track_indices[track_name] = curr  # Optimization for next frame

    # If we have an active event
    if curr < len(track):
      event = track[curr]
      if event.start_time <= time <= event.end_time:
        # Interpolate
        # Start value comes from previous event's target, or default
        prev_target = default
        if curr > 0:
          prev_target = track[curr - 1].target_transform

        # Calculate progress
        duration = event.end_time - event.start_time
        t_rel = 0.0
        if duration > 1e-6:
          t_rel = (time - event.start_time) / duration
          t_rel = max(0.0, min(1.0, t_rel))

        # Lerp
        return Transform(
          translate_x=_lerp(prev_target.translate_x,
                            event.target_transform.translate_x, t_rel),
          translate_y=_lerp(prev_target.translate_y,
                            event.target_transform.translate_y, t_rel),
          scale_x=_lerp(prev_target.scale_x, event.target_transform.scale_x,
                        t_rel),
          scale_y=_lerp(prev_target.scale_y, event.target_transform.scale_y,
                        t_rel),
        )

    # If no active event, check if we should hold the last completed event
    if curr > 0:
      # The event at curr-1 has definitely ended (end_time < time)
      return track[curr - 1].target_transform

    # If curr == 0 and it starts > time, we are before first event -> default
    return default

  for frame_idx in range(total_frames):
    t = frame_idx * dt

    # Collect sounds starting in this frame window [t, t+dt)
    frame_sounds = []
    while sound_idx < len(sorted_sounds):
      snd = sorted_sounds[sound_idx]
      if snd.start_time < t:
        sound_idx += 1
        continue
      if snd.start_time < t + dt:
        frame_sounds.append(snd)
        sound_idx += 1
      else:
        break

    # Update Character State
    character.set_pose(
      left_eye_open=get_boolean_value(sequence.sequence_left_eye_open,
                                      "sequence_left_eye_open", t, True),
      right_eye_open=get_boolean_value(sequence.sequence_right_eye_open,
                                       "sequence_right_eye_open", t, True),
      mouth_state=get_mouth_state(sequence.sequence_mouth_state,
                                  "sequence_mouth_state", t,
                                  MouthState.CLOSED),
      left_hand_visible=get_boolean_value(sequence.sequence_left_hand_visible,
                                          "sequence_left_hand_visible", t,
                                          True),
      right_hand_visible=get_boolean_value(
        sequence.sequence_right_hand_visible, "sequence_right_hand_visible", t,
        True),
      left_hand_transform=get_transform_value(
        sequence.sequence_left_hand_transform, "sequence_left_hand_transform",
        t, Transform()),
      right_hand_transform=get_transform_value(
        sequence.sequence_right_hand_transform,
        "sequence_right_hand_transform", t, Transform()),
      head_transform=get_transform_value(sequence.sequence_head_transform,
                                         "sequence_head_transform", t,
                                         Transform()),
    )

    yield t, character.get_image(), frame_sounds


def _lerp(a: float, b: float, t: float) -> float:
  """Linear interpolation between a and b."""
  return a + (b - a) * t
