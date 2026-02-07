"""Data structures for posable character animation sequences."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any, Iterator, TypeVar

from PIL import Image

from common.posable_character import MouthState, PosableCharacter, Transform

T = TypeVar("T")


@dataclass
class SequenceEvent:
  """Base class for animation sequence events."""
  start_time: float
  end_time: float

  def validate(self) -> None:
    if self.start_time < 0:
      raise ValueError("start_time must be non-negative")
    if self.end_time < self.start_time:
      raise ValueError("end_time must be greater than or equal to start_time")

  def to_dict(self) -> dict[str, Any]:
    return dataclasses.asdict(self)


@dataclass
class SequenceBooleanEvent(SequenceEvent):
  """Event for boolean properties (e.g., eyes open/closed)."""
  value: bool

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceBooleanEvent:
    return cls(
      start_time=float(data["start_time"]),
      end_time=float(data["end_time"]),
      value=bool(data["value"]),
    )


@dataclass
class SequenceMouthEvent(SequenceEvent):
  """Event for mouth state."""
  mouth_state: MouthState

  def to_dict(self) -> dict[str, Any]:
    return {
      "start_time": self.start_time,
      "end_time": self.end_time,
      "mouth_state": self.mouth_state.value,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceMouthEvent:
    return cls(
      start_time=float(data["start_time"]),
      end_time=float(data["end_time"]),
      mouth_state=MouthState(data["mouth_state"]),
    )


@dataclass
class SequenceTransformEvent(SequenceEvent):
  """Event for transform properties (translation/scaling)."""
  target_transform: Transform

  def to_dict(self) -> dict[str, Any]:
    return {
      "start_time": self.start_time,
      "end_time": self.end_time,
      "target_transform": {
        "translate_x": self.target_transform.translate_x,
        "translate_y": self.target_transform.translate_y,
        "scale_x": self.target_transform.scale_x,
        "scale_y": self.target_transform.scale_y,
      },
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceTransformEvent:
    transform_data = data["target_transform"]
    return cls(
      start_time=float(data["start_time"]),
      end_time=float(data["end_time"]),
      target_transform=Transform(
        translate_x=float(transform_data.get("translate_x", 0.0)),
        translate_y=float(transform_data.get("translate_y", 0.0)),
        scale_x=float(transform_data.get("scale_x", 1.0)),
        scale_y=float(transform_data.get("scale_y", 1.0)),
      ),
    )


@dataclass
class SequenceSoundEvent:
  """Event for sound effects."""
  start_time: float
  gcs_uri: str
  volume: float = 1.0
  end_time: float | None = None

  def validate(self) -> None:
    if self.start_time < 0:
      raise ValueError("start_time must be non-negative")
    if self.end_time is not None and self.end_time < self.start_time:
      raise ValueError("end_time must be greater than or equal to start_time")
    if not self.gcs_uri:
      raise ValueError("gcs_uri must be provided")

  def to_dict(self) -> dict[str, Any]:
    return dataclasses.asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceSoundEvent:
    end_time = data.get("end_time")
    return cls(
      start_time=float(data["start_time"]),
      gcs_uri=str(data["gcs_uri"]),
      volume=float(data.get("volume", 1.0)),
      end_time=float(end_time) if end_time is not None else None,
    )


@dataclass
class PosableCharacterSequence:
  """Complete animation sequence for a posable character."""

  key: str | None = None

  # Tracks (prefixed with sequence_ for sorting/identification)
  sequence_left_eye_open: list[SequenceBooleanEvent] = field(default_factory=list)
  sequence_right_eye_open: list[SequenceBooleanEvent] = field(default_factory=list)
  sequence_mouth_state: list[SequenceMouthEvent] = field(default_factory=list)
  sequence_left_hand_visible: list[SequenceBooleanEvent] = field(default_factory=list)
  sequence_right_hand_visible: list[SequenceBooleanEvent] = field(default_factory=list)

  sequence_left_hand_transform: list[SequenceTransformEvent] = field(default_factory=list)
  sequence_right_hand_transform: list[SequenceTransformEvent] = field(default_factory=list)
  sequence_head_transform: list[SequenceTransformEvent] = field(default_factory=list)

  sequence_sound_events: list[SequenceSoundEvent] = field(default_factory=list)

  def validate(self) -> None:
    """Validate that events in each track are sorted and non-overlapping."""
    self._validate_track(self.sequence_left_eye_open, "sequence_left_eye_open")
    self._validate_track(self.sequence_right_eye_open, "sequence_right_eye_open")
    self._validate_track(self.sequence_mouth_state, "sequence_mouth_state")
    self._validate_track(self.sequence_left_hand_visible, "sequence_left_hand_visible")
    self._validate_track(self.sequence_right_hand_visible, "sequence_right_hand_visible")
    self._validate_track(self.sequence_left_hand_transform, "sequence_left_hand_transform")
    self._validate_track(self.sequence_right_hand_transform, "sequence_right_hand_transform")
    self._validate_track(self.sequence_head_transform, "sequence_head_transform")
    # Sound events can overlap, so we only validate individual events.
    for event in self.sequence_sound_events:
      event.validate()

  def _validate_track(self, track: list[Any], track_name: str) -> None:
    if not track:
      return

    # Sort by start time just in case, though usually we expect sorted input
    track.sort(key=lambda e: e.start_time)

    last_end_time = -1.0
    for i, event in enumerate(track):
      event.validate()
      if event.start_time < last_end_time:
        raise ValueError(
          f"Overlapping events in track '{track_name}' at index {i}: "
          f"start_time {event.start_time} < previous end_time {last_end_time}"
        )
      last_end_time = event.end_time

  def to_dict(self, include_key: bool = False) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    data = {
      "sequence_left_eye_open": [e.to_dict() for e in self.sequence_left_eye_open],
      "sequence_right_eye_open": [e.to_dict() for e in self.sequence_right_eye_open],
      "sequence_mouth_state": [e.to_dict() for e in self.sequence_mouth_state],
      "sequence_left_hand_visible": [e.to_dict() for e in self.sequence_left_hand_visible],
      "sequence_right_hand_visible": [e.to_dict() for e in self.sequence_right_hand_visible],
      "sequence_left_hand_transform": [e.to_dict() for e in self.sequence_left_hand_transform],
      "sequence_right_hand_transform": [e.to_dict() for e in self.sequence_right_hand_transform],
      "sequence_head_transform": [e.to_dict() for e in self.sequence_head_transform],
      "sequence_sound_events": [e.to_dict() for e in self.sequence_sound_events],
    }
    if include_key and self.key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(cls, data: dict[str, Any], key: str | None = None) -> PosableCharacterSequence:
    """Create a PosableCharacterSequence from a dictionary."""
    if not data:
        data = {}

    return cls(
      key=key if key else data.get("key"),
      sequence_left_eye_open=[
        SequenceBooleanEvent.from_dict(e) for e in data.get("sequence_left_eye_open", [])
      ],
      sequence_right_eye_open=[
        SequenceBooleanEvent.from_dict(e) for e in data.get("sequence_right_eye_open", [])
      ],
      sequence_mouth_state=[
        SequenceMouthEvent.from_dict(e) for e in data.get("sequence_mouth_state", [])
      ],
      sequence_left_hand_visible=[
        SequenceBooleanEvent.from_dict(e) for e in data.get("sequence_left_hand_visible", [])
      ],
      sequence_right_hand_visible=[
        SequenceBooleanEvent.from_dict(e) for e in data.get("sequence_right_hand_visible", [])
      ],
      sequence_left_hand_transform=[
        SequenceTransformEvent.from_dict(e) for e in data.get("sequence_left_hand_transform", [])
      ],
      sequence_right_hand_transform=[
        SequenceTransformEvent.from_dict(e) for e in data.get("sequence_right_hand_transform", [])
      ],
      sequence_head_transform=[
        SequenceTransformEvent.from_dict(e) for e in data.get("sequence_head_transform", [])
      ],
      sequence_sound_events=[
        SequenceSoundEvent.from_dict(e) for e in data.get("sequence_sound_events", [])
      ],
    )


def generate_frames(
  character: PosableCharacter,
  sequence: PosableCharacterSequence,
  fps: float,
) -> Iterator[tuple[float, Image.Image, list[SequenceSoundEvent]]]:
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
