"""Data structures for posable character animation sequences."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, TypeVar

from common.posable_character import MouthState, Transform

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
