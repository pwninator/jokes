"""Data structures for posable character animation sequences."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, cast, override

from common.posable_character import MouthState, PoseState, Transform


@dataclass(kw_only=True)
class SequenceEvent:
  """Base class for animation sequence events."""
  start_time: float
  end_time: float

  def validate(self) -> None:
    """Validate that the event is valid."""
    if self.start_time < 0:
      raise ValueError(f"start_time ({self.start_time}) must be non-negative")
    if self.end_time < self.start_time:
      raise ValueError(
        f"end_time ({self.end_time}) must be greater than or equal to start_time ({self.start_time})"
      )

  def to_dict(self) -> dict[str, Any]:
    """Convert the event to a dictionary."""
    return dataclasses.asdict(self)

  @staticmethod
  def _parse_common_fields(data: dict[str, Any]) -> dict[str, float]:
    if "end_time" not in data or data["end_time"] is None:
      raise ValueError("end_time is required")
    end_time = data["end_time"]
    return {
      "start_time": float(data["start_time"]),
      "end_time": float(end_time),
    }


@dataclass(kw_only=True)
class SequenceBooleanEvent(SequenceEvent):
  """Event for boolean properties (e.g., eyes open/closed)."""
  value: bool

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceBooleanEvent:
    """Create a SequenceBooleanEvent from a dictionary."""
    return cls(
      value=bool(data["value"]),
      **cls._parse_common_fields(data),
    )

  @classmethod
  def shift_events(
    cls,
    events: list[SequenceBooleanEvent],
    offset: float,
  ) -> list[SequenceBooleanEvent]:
    """Return a shifted copy of boolean events."""
    return [
      SequenceBooleanEvent(
        start_time=event.start_time + offset,
        end_time=event.end_time + offset,
        value=bool(event.value),
      ) for event in events
    ]


@dataclass(kw_only=True)
class SequenceMouthEvent(SequenceEvent):
  """Event for mouth state."""
  mouth_state: MouthState

  @override
  def to_dict(self) -> dict[str, Any]:
    data = super().to_dict()
    data["mouth_state"] = self.mouth_state.value
    return data

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceMouthEvent:
    """Create a SequenceMouthEvent from a dictionary."""
    return cls(
      mouth_state=MouthState(data["mouth_state"]),
      **cls._parse_common_fields(data),
    )

  @classmethod
  def shift_events(
    cls,
    events: list[SequenceMouthEvent],
    offset: float,
  ) -> list[SequenceMouthEvent]:
    """Return a shifted copy of mouth events."""
    return [
      cls(
        start_time=event.start_time + offset,
        end_time=event.end_time + offset,
        mouth_state=event.mouth_state,
      ) for event in events
    ]


@dataclass(kw_only=True)
class SequenceTransformEvent(SequenceEvent):
  """Event for transform properties (translation/scaling)."""
  target_transform: Transform

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceTransformEvent:
    """Create a SequenceTransformEvent from a dictionary."""
    transform_data = data["target_transform"]
    return cls(
      target_transform=Transform(
        translate_x=float(transform_data.get("translate_x", 0.0)),
        translate_y=float(transform_data.get("translate_y", 0.0)),
        scale_x=float(transform_data.get("scale_x", 1.0)),
        scale_y=float(transform_data.get("scale_y", 1.0)),
      ),
      **cls._parse_common_fields(data),
    )

  @classmethod
  def shift_events(
    cls,
    events: list[SequenceTransformEvent],
    offset: float,
  ) -> list[SequenceTransformEvent]:
    """Return a shifted copy of transform events."""
    return [
      cls(
        start_time=event.start_time + offset,
        end_time=event.end_time + offset,
        target_transform=event.target_transform,
      ) for event in events
    ]


@dataclass(kw_only=True)
class SequenceFloatEvent(SequenceEvent):
  """Event for float properties (e.g., mask/line offsets)."""
  target_value: float

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceFloatEvent:
    """Create a SequenceFloatEvent from a dictionary."""
    return cls(
      target_value=float(data["target_value"]),
      **cls._parse_common_fields(data),
    )

  @classmethod
  def shift_events(
    cls,
    events: list[SequenceFloatEvent],
    offset: float,
  ) -> list[SequenceFloatEvent]:
    """Return a shifted copy of float events."""
    return [
      cls(
        start_time=event.start_time + offset,
        end_time=event.end_time + offset,
        target_value=event.target_value,
      ) for event in events
    ]


@dataclass(kw_only=True)
class SequenceSoundEvent(SequenceEvent):
  """Event for sound effects."""
  gcs_uri: str = ""
  volume: float = 1.0

  @override
  def validate(self) -> None:
    super().validate()
    if self.end_time <= self.start_time:
      raise ValueError(
        "Sound events must have positive duration (end_time > start_time)")
    if not self.gcs_uri:
      raise ValueError("gcs_uri must be provided")

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SequenceSoundEvent:
    """Create a SequenceSoundEvent from a dictionary."""
    return cls(
      gcs_uri=str(data["gcs_uri"]),
      volume=float(data.get("volume", 1.0)),
      **cls._parse_common_fields(data),
    )

  @classmethod
  def shift_events(
    cls,
    events: list[SequenceSoundEvent],
    offset: float,
  ) -> list[SequenceSoundEvent]:
    """Return a shifted copy of sound events."""
    return [
      cls(
        start_time=event.start_time + offset,
        end_time=event.end_time + offset,
        gcs_uri=event.gcs_uri,
        volume=event.volume,
      ) for event in events
    ]


@dataclass
class PosableCharacterSequence:
  """Complete animation sequence for a posable character."""

  key: str | None = None
  transcript: str | None = None
  initial_pose: PoseState | None = None

  # Tracks (prefixed with sequence_ for sorting/identification)
  sequence_left_eye_open: list[SequenceBooleanEvent] = field(
    default_factory=list)
  sequence_right_eye_open: list[SequenceBooleanEvent] = field(
    default_factory=list)
  sequence_mouth_state: list[SequenceMouthEvent] = field(default_factory=list)
  sequence_left_hand_visible: list[SequenceBooleanEvent] = field(
    default_factory=list)
  sequence_right_hand_visible: list[SequenceBooleanEvent] = field(
    default_factory=list)

  sequence_left_hand_transform: list[SequenceTransformEvent] = field(
    default_factory=list)
  sequence_right_hand_transform: list[SequenceTransformEvent] = field(
    default_factory=list)
  sequence_head_transform: list[SequenceTransformEvent] = field(
    default_factory=list)
  sequence_surface_line_offset: list[SequenceFloatEvent] = field(
    default_factory=list)
  sequence_mask_boundary_offset: list[SequenceFloatEvent] = field(
    default_factory=list)

  sequence_sound_events: list[SequenceSoundEvent] = field(default_factory=list)
  sequence_surface_line_visible: list[SequenceBooleanEvent] = field(
    default_factory=list)
  sequence_head_masking_enabled: list[SequenceBooleanEvent] = field(
    default_factory=list)
  sequence_left_hand_masking_enabled: list[SequenceBooleanEvent] = field(
    default_factory=list)
  sequence_right_hand_masking_enabled: list[SequenceBooleanEvent] = field(
    default_factory=list)

  @property
  def duration_sec(self) -> float:
    """Return max end_time across all sequence tracks."""
    max_end = 0.0
    for track in self._all_tracks():
      for event in track:
        max_end = max(max_end, event.end_time)
    return max_end

  def validate(self) -> None:
    """Validate that events in each track are sorted and non-overlapping."""
    self._validate_track(self.sequence_left_eye_open, "sequence_left_eye_open")
    self._validate_track(self.sequence_right_eye_open,
                         "sequence_right_eye_open")
    self._validate_track(self.sequence_mouth_state, "sequence_mouth_state")
    self._validate_track(self.sequence_left_hand_visible,
                         "sequence_left_hand_visible")
    self._validate_track(self.sequence_right_hand_visible,
                         "sequence_right_hand_visible")
    self._validate_track(self.sequence_left_hand_transform,
                         "sequence_left_hand_transform")
    self._validate_track(self.sequence_right_hand_transform,
                         "sequence_right_hand_transform")
    self._validate_track(self.sequence_head_transform,
                         "sequence_head_transform")
    self._validate_track(self.sequence_surface_line_offset,
                         "sequence_surface_line_offset")
    self._validate_track(self.sequence_mask_boundary_offset,
                         "sequence_mask_boundary_offset")
    self._validate_track(self.sequence_surface_line_visible,
                         "sequence_surface_line_visible")
    self._validate_track(self.sequence_head_masking_enabled,
                         "sequence_head_masking_enabled")
    self._validate_track(self.sequence_left_hand_masking_enabled,
                         "sequence_left_hand_masking_enabled")
    self._validate_track(self.sequence_right_hand_masking_enabled,
                         "sequence_right_hand_masking_enabled")
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
          f"Overlapping events in track '{track_name}' at index {i}: " +
          f"start_time {event.start_time} < previous end_time {last_end_time}")
      last_end_time = event.end_time

  def _all_tracks(self) -> tuple[list[Any], ...]:
    """Return all event tracks in this sequence."""
    return (
      self.sequence_left_eye_open,
      self.sequence_right_eye_open,
      self.sequence_mouth_state,
      self.sequence_left_hand_visible,
      self.sequence_right_hand_visible,
      self.sequence_left_hand_transform,
      self.sequence_right_hand_transform,
      self.sequence_head_transform,
      self.sequence_surface_line_offset,
      self.sequence_mask_boundary_offset,
      self.sequence_sound_events,
      self.sequence_surface_line_visible,
      self.sequence_head_masking_enabled,
      self.sequence_left_hand_masking_enabled,
      self.sequence_right_hand_masking_enabled,
    )

  @classmethod
  def merge_all(
    cls,
    sequence_offsets: list[tuple[PosableCharacterSequence, float]],
  ) -> PosableCharacterSequence:
    """Return a new sequence containing all inputs shifted by their offsets."""
    out = cls()
    for sequence, offset in sequence_offsets:
      out._append_shifted(sequence=sequence, offset=offset)
    out.validate()
    return out

  @classmethod
  def build_pose_hold_sequence(
    cls,
    *,
    pose: PoseState,
    duration_sec: float,
  ) -> PosableCharacterSequence:
    """Build a static-pose sequence with explicit duration and initial pose."""
    end_time = max(0.0, duration_sec)
    sequence = cls(
      initial_pose=pose,
      # Any one non-sound track is sufficient to encode sequence duration.
      sequence_left_eye_open=[
        SequenceBooleanEvent(
          start_time=0.0,
          end_time=end_time,
          value=pose.left_eye_open,
        )
      ],
    )
    sequence.validate()
    return sequence

  def _append_shifted(
    self,
    *,
    sequence: PosableCharacterSequence,
    offset: float,
  ) -> None:
    """Append shifted events from `sequence` onto `self`."""
    self.sequence_left_eye_open.extend(
      SequenceBooleanEvent.shift_events(sequence.sequence_left_eye_open,
                                        offset))
    self.sequence_right_eye_open.extend(
      SequenceBooleanEvent.shift_events(sequence.sequence_right_eye_open,
                                        offset))
    self.sequence_mouth_state.extend(
      SequenceMouthEvent.shift_events(sequence.sequence_mouth_state, offset))
    self.sequence_left_hand_visible.extend(
      SequenceBooleanEvent.shift_events(sequence.sequence_left_hand_visible,
                                        offset))
    self.sequence_right_hand_visible.extend(
      SequenceBooleanEvent.shift_events(sequence.sequence_right_hand_visible,
                                        offset))
    self.sequence_left_hand_transform.extend(
      SequenceTransformEvent.shift_events(
        sequence.sequence_left_hand_transform, offset))
    self.sequence_right_hand_transform.extend(
      SequenceTransformEvent.shift_events(
        sequence.sequence_right_hand_transform, offset))
    self.sequence_head_transform.extend(
      SequenceTransformEvent.shift_events(sequence.sequence_head_transform,
                                          offset))
    self.sequence_surface_line_offset.extend(
      SequenceFloatEvent.shift_events(sequence.sequence_surface_line_offset,
                                      offset))
    self.sequence_mask_boundary_offset.extend(
      SequenceFloatEvent.shift_events(sequence.sequence_mask_boundary_offset,
                                      offset))
    self.sequence_sound_events.extend(
      SequenceSoundEvent.shift_events(sequence.sequence_sound_events, offset))
    self.sequence_surface_line_visible.extend(
      SequenceBooleanEvent.shift_events(sequence.sequence_surface_line_visible,
                                        offset))
    self.sequence_head_masking_enabled.extend(
      SequenceBooleanEvent.shift_events(sequence.sequence_head_masking_enabled,
                                        offset))
    self.sequence_left_hand_masking_enabled.extend(
      SequenceBooleanEvent.shift_events(
        sequence.sequence_left_hand_masking_enabled, offset))
    self.sequence_right_hand_masking_enabled.extend(
      SequenceBooleanEvent.shift_events(
        sequence.sequence_right_hand_masking_enabled, offset))

  def to_dict(self, include_key: bool = False) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, Any] = {
      "transcript":
      self.transcript,
      "sequence_left_eye_open":
      [e.to_dict() for e in self.sequence_left_eye_open],
      "sequence_right_eye_open":
      [e.to_dict() for e in self.sequence_right_eye_open],
      "sequence_mouth_state": [e.to_dict() for e in self.sequence_mouth_state],
      "sequence_left_hand_visible":
      [e.to_dict() for e in self.sequence_left_hand_visible],
      "sequence_right_hand_visible":
      [e.to_dict() for e in self.sequence_right_hand_visible],
      "sequence_left_hand_transform":
      [e.to_dict() for e in self.sequence_left_hand_transform],
      "sequence_right_hand_transform":
      [e.to_dict() for e in self.sequence_right_hand_transform],
      "sequence_head_transform":
      [e.to_dict() for e in self.sequence_head_transform],
      "sequence_surface_line_offset":
      [e.to_dict() for e in self.sequence_surface_line_offset],
      "sequence_mask_boundary_offset":
      [e.to_dict() for e in self.sequence_mask_boundary_offset],
      "sequence_sound_events":
      [e.to_dict() for e in self.sequence_sound_events],
      "sequence_surface_line_visible":
      [e.to_dict() for e in self.sequence_surface_line_visible],
      "sequence_head_masking_enabled":
      [e.to_dict() for e in self.sequence_head_masking_enabled],
      "sequence_left_hand_masking_enabled": [
        e.to_dict() for e in self.sequence_left_hand_masking_enabled
      ],
      "sequence_right_hand_masking_enabled": [
        e.to_dict() for e in self.sequence_right_hand_masking_enabled
      ],
    }
    if self.initial_pose is not None:
      data["initial_pose"] = _pose_state_to_dict(self.initial_pose)
    if include_key and self.key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(cls,
                data: dict[str, Any],
                key: str | None = None) -> PosableCharacterSequence:
    """Create a PosableCharacterSequence from a dictionary."""
    if not data:
      data = {}

    return cls(
      key=key if key else data.get("key"),
      transcript=data.get("transcript"),
      initial_pose=_parse_initial_pose_dict(data.get("initial_pose")),
      sequence_left_eye_open=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_left_eye_open", [])
      ],
      sequence_right_eye_open=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_right_eye_open", [])
      ],
      sequence_mouth_state=[
        SequenceMouthEvent.from_dict(e)
        for e in data.get("sequence_mouth_state", [])
      ],
      sequence_left_hand_visible=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_left_hand_visible", [])
      ],
      sequence_right_hand_visible=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_right_hand_visible", [])
      ],
      sequence_left_hand_transform=[
        SequenceTransformEvent.from_dict(e)
        for e in data.get("sequence_left_hand_transform", [])
      ],
      sequence_right_hand_transform=[
        SequenceTransformEvent.from_dict(e)
        for e in data.get("sequence_right_hand_transform", [])
      ],
      sequence_head_transform=[
        SequenceTransformEvent.from_dict(e)
        for e in data.get("sequence_head_transform", [])
      ],
      sequence_surface_line_offset=[
        SequenceFloatEvent.from_dict(e)
        for e in data.get("sequence_surface_line_offset", [])
      ],
      sequence_mask_boundary_offset=[
        SequenceFloatEvent.from_dict(e)
        for e in data.get("sequence_mask_boundary_offset", [])
      ],
      sequence_sound_events=[
        SequenceSoundEvent.from_dict(e)
        for e in data.get("sequence_sound_events", [])
      ],
      sequence_surface_line_visible=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_surface_line_visible", [])
      ],
      sequence_head_masking_enabled=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_head_masking_enabled", [])
      ],
      sequence_left_hand_masking_enabled=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_left_hand_masking_enabled", [])
      ],
      sequence_right_hand_masking_enabled=[
        SequenceBooleanEvent.from_dict(e)
        for e in data.get("sequence_right_hand_masking_enabled", [])
      ],
    )


def _spec_default_pose_state() -> PoseState:
  """Return canonical track defaults from the animator spec."""
  return PoseState(
    left_eye_open=True,
    right_eye_open=True,
    mouth_state=MouthState.CLOSED,
    left_hand_visible=True,
    right_hand_visible=True,
    left_hand_transform=Transform(),
    right_hand_transform=Transform(),
    head_transform=Transform(),
    surface_line_offset=50.0,
    mask_boundary_offset=50.0,
    surface_line_visible=True,
    head_masking_enabled=True,
    left_hand_masking_enabled=False,
    right_hand_masking_enabled=False,
  )


def _pose_state_to_dict(pose: PoseState) -> dict[str, Any]:
  return {
    "left_eye_open": pose.left_eye_open,
    "right_eye_open": pose.right_eye_open,
    "mouth_state": pose.mouth_state.value,
    "left_hand_visible": pose.left_hand_visible,
    "right_hand_visible": pose.right_hand_visible,
    "left_hand_transform": {
      "translate_x": pose.left_hand_transform.translate_x,
      "translate_y": pose.left_hand_transform.translate_y,
      "scale_x": pose.left_hand_transform.scale_x,
      "scale_y": pose.left_hand_transform.scale_y,
    },
    "right_hand_transform": {
      "translate_x": pose.right_hand_transform.translate_x,
      "translate_y": pose.right_hand_transform.translate_y,
      "scale_x": pose.right_hand_transform.scale_x,
      "scale_y": pose.right_hand_transform.scale_y,
    },
    "head_transform": {
      "translate_x": pose.head_transform.translate_x,
      "translate_y": pose.head_transform.translate_y,
      "scale_x": pose.head_transform.scale_x,
      "scale_y": pose.head_transform.scale_y,
    },
    "surface_line_offset": pose.surface_line_offset,
    "mask_boundary_offset": pose.mask_boundary_offset,
    "surface_line_visible": pose.surface_line_visible,
    "head_masking_enabled": pose.head_masking_enabled,
    "left_hand_masking_enabled": pose.left_hand_masking_enabled,
    "right_hand_masking_enabled": pose.right_hand_masking_enabled,
  }


def _parse_transform_dict(value: object, default: Transform) -> Transform:
  if not isinstance(value, dict):
    return default
  transform_data = cast(dict[str, object], value)
  return Transform(
    translate_x=_coerce_float(
      transform_data.get("translate_x"), default.translate_x),
    translate_y=_coerce_float(
      transform_data.get("translate_y"), default.translate_y),
    scale_x=_coerce_float(transform_data.get("scale_x"), default.scale_x),
    scale_y=_coerce_float(transform_data.get("scale_y"), default.scale_y),
  )


def _parse_initial_pose_dict(data: object) -> PoseState | None:
  if data is None:
    return None
  if not isinstance(data, dict):
    raise ValueError("initial_pose must be an object when provided")
  initial_pose_data = cast(dict[str, object], data)

  default = _spec_default_pose_state()
  mouth_state = _coerce_mouth_state(
    initial_pose_data.get("mouth_state"), default.mouth_state)
  return PoseState(
    left_eye_open=_coerce_bool(
      initial_pose_data.get("left_eye_open"), default.left_eye_open),
    right_eye_open=_coerce_bool(
      initial_pose_data.get("right_eye_open"), default.right_eye_open),
    mouth_state=mouth_state,
    left_hand_visible=_coerce_bool(initial_pose_data.get("left_hand_visible"),
                                   default.left_hand_visible),
    right_hand_visible=_coerce_bool(initial_pose_data.get("right_hand_visible"),
                                    default.right_hand_visible),
    left_hand_transform=_parse_transform_dict(
      initial_pose_data.get("left_hand_transform"), default.left_hand_transform),
    right_hand_transform=_parse_transform_dict(
      initial_pose_data.get("right_hand_transform"), default.right_hand_transform),
    head_transform=_parse_transform_dict(
      initial_pose_data.get("head_transform"), default.head_transform),
    surface_line_offset=_coerce_float(
      initial_pose_data.get("surface_line_offset"), default.surface_line_offset),
    mask_boundary_offset=_coerce_float(
      initial_pose_data.get("mask_boundary_offset"), default.mask_boundary_offset),
    surface_line_visible=_coerce_bool(
      initial_pose_data.get("surface_line_visible"), default.surface_line_visible),
    head_masking_enabled=_coerce_bool(
      initial_pose_data.get("head_masking_enabled"), default.head_masking_enabled),
    left_hand_masking_enabled=_coerce_bool(
      initial_pose_data.get("left_hand_masking_enabled"),
      default.left_hand_masking_enabled),
    right_hand_masking_enabled=_coerce_bool(
      initial_pose_data.get("right_hand_masking_enabled"),
      default.right_hand_masking_enabled),
  )


def _coerce_bool(value: object, default: bool) -> bool:
  if isinstance(value, bool):
    return value
  if isinstance(value, (int, float)):
    return bool(value)
  if isinstance(value, str):
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
      return True
    if normalized in {"false", "0", "no", "off"}:
      return False
  return default


def _coerce_float(value: object, default: float) -> float:
  if isinstance(value, (int, float)):
    return float(value)
  if isinstance(value, str):
    try:
      return float(value)
    except ValueError:
      return default
  return default


def _coerce_mouth_state(value: object, default: MouthState) -> MouthState:
  if isinstance(value, MouthState):
    return value
  if isinstance(value, str):
    try:
      return MouthState(value)
    except ValueError:
      return default
  return default
