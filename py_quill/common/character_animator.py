"""Random-access evaluator for posable character animation sequences.

This implementation must strictly conform to:
`py_quill/common/character_animator_spec.md`.
"""

from __future__ import annotations

import math
from collections.abc import Iterator

from common.posable_character import (MouthState, PosableCharacter, PoseState,
                                      Transform)
from common.posable_character_sequence import (
  PosableCharacterSequence, SequenceBooleanEvent, SequenceFloatEvent,
  SequenceMouthEvent, SequenceSoundEvent, SequenceTransformEvent)
from PIL import Image


class CharacterAnimator:
  """Evaluate a `PosableCharacterSequence` at arbitrary timestamps.

  Behavior in this class is intentionally spec-driven and must stay aligned
  with `py_quill/common/character_animator_spec.md`.
  """

  def __init__(self, sequence: PosableCharacterSequence):
    sequence.validate()
    self._sequence: PosableCharacterSequence = sequence
    self._left_eye_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_left_eye_open,
      key=lambda event: event.start_time,
    )
    self._right_eye_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_right_eye_open,
      key=lambda event: event.start_time,
    )
    self._mouth_track: list[SequenceMouthEvent] = sorted(
      sequence.sequence_mouth_state,
      key=lambda event: event.start_time,
    )
    self._left_hand_visible_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_left_hand_visible,
      key=lambda event: event.start_time,
    )
    self._right_hand_visible_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_right_hand_visible,
      key=lambda event: event.start_time,
    )
    self._left_hand_transform_track: list[SequenceTransformEvent] = sorted(
      sequence.sequence_left_hand_transform,
      key=lambda event: event.start_time,
    )
    self._right_hand_transform_track: list[SequenceTransformEvent] = sorted(
      sequence.sequence_right_hand_transform,
      key=lambda event: event.start_time,
    )
    self._head_transform_track: list[SequenceTransformEvent] = sorted(
      sequence.sequence_head_transform,
      key=lambda event: event.start_time,
    )
    self._surface_line_offset_track: list[SequenceFloatEvent] = sorted(
      sequence.sequence_surface_line_offset,
      key=lambda event: event.start_time,
    )
    self._mask_boundary_offset_track: list[SequenceFloatEvent] = sorted(
      sequence.sequence_mask_boundary_offset,
      key=lambda event: event.start_time,
    )
    self._surface_line_visible_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_surface_line_visible,
      key=lambda event: event.start_time,
    )
    self._head_masking_enabled_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_head_masking_enabled,
      key=lambda event: event.start_time,
    )
    self._left_hand_masking_enabled_track: list[SequenceBooleanEvent] = sorted(
      sequence.sequence_left_hand_masking_enabled,
      key=lambda event: event.start_time,
    )
    self._right_hand_masking_enabled_track: list[
      SequenceBooleanEvent] = sorted(
        sequence.sequence_right_hand_masking_enabled,
        key=lambda event: event.start_time,
      )
    self._sound_track: list[SequenceSoundEvent] = sorted(
      sequence.sequence_sound_events,
      key=lambda event: event.start_time,
    )
    self._duration_sec: float = self._compute_duration_sec()

  @property
  def duration_sec(self) -> float:
    """Total sequence duration in seconds."""
    return self._duration_sec

  def sample_pose(self, time_sec: float) -> PoseState:
    """Return the resolved pose state at `time_sec`."""
    return PoseState(
      left_eye_open=self._sample_boolean(self._left_eye_track, time_sec, True),
      right_eye_open=self._sample_boolean(self._right_eye_track, time_sec,
                                          True),
      mouth_state=self._sample_mouth(self._mouth_track, time_sec,
                                     MouthState.CLOSED),
      left_hand_visible=self._sample_boolean(self._left_hand_visible_track,
                                             time_sec, True),
      right_hand_visible=self._sample_boolean(self._right_hand_visible_track,
                                              time_sec, True),
      left_hand_transform=self._sample_transform(
        self._left_hand_transform_track, time_sec, Transform()),
      right_hand_transform=self._sample_transform(
        self._right_hand_transform_track,
        time_sec,
        Transform(),
      ),
      head_transform=self._sample_transform(self._head_transform_track,
                                            time_sec, Transform()),
      surface_line_offset=self._sample_float(
        self._surface_line_offset_track,
        time_sec,
        50.0,
      ),
      mask_boundary_offset=self._sample_float(
        self._mask_boundary_offset_track,
        time_sec,
        50.0,
      ),
      surface_line_visible=self._sample_boolean(
        self._surface_line_visible_track,
        time_sec,
        True,
      ),
      head_masking_enabled=self._sample_boolean(
        self._head_masking_enabled_track,
        time_sec,
        True,
      ),
      left_hand_masking_enabled=self._sample_boolean(
        self._left_hand_masking_enabled_track,
        time_sec,
        False,
      ),
      right_hand_masking_enabled=self._sample_boolean(
        self._right_hand_masking_enabled_track,
        time_sec,
        False,
      ),
    )

  def apply_pose(self, character: PosableCharacter,
                 time_sec: float) -> PoseState:
    """Apply sampled pose to `character` and return the sampled pose."""
    pose = self.sample_pose(time_sec)
    character.apply_pose_state(pose)
    return pose

  def render_frame(self, character: PosableCharacter,
                   time_sec: float) -> tuple[PoseState, Image.Image]:
    """Apply pose at `time_sec` and render `character` image."""
    pose = self.apply_pose(character, time_sec)
    return pose, character.get_image()

  def sound_events_between(
    self,
    start_time_sec: float,
    end_time_sec: float,
    *,
    include_start: bool = True,
    include_end: bool = False,
  ) -> list[SequenceSoundEvent]:
    """Return sound events whose `start_time` falls in the selected window."""
    if end_time_sec < start_time_sec:
      return []

    out: list[SequenceSoundEvent] = []
    for event in self._sound_track:
      event_time = event.start_time
      lower_ok = (event_time >= start_time_sec
                  if include_start else event_time > start_time_sec)
      if not lower_ok:
        continue

      upper_ok = (event_time <= end_time_sec
                  if include_end else event_time < end_time_sec)
      if not upper_ok:
        break

      out.append(event)
    return out

  def generate_frames(
    self,
    character: PosableCharacter,
    fps: float,
  ) -> Iterator[tuple[float, Image.Image, list[SequenceSoundEvent]]]:
    """Sequential wrapper over random-access evaluation."""
    if fps <= 0:
      raise ValueError("fps must be positive")

    dt = 1.0 / fps
    total_frames = int(math.ceil(self.duration_sec * fps)) + 1
    for frame_idx in range(total_frames):
      time_sec = frame_idx * dt
      frame_sounds = self.sound_events_between(
        time_sec,
        time_sec + dt,
        include_start=True,
        include_end=False,
      )
      _pose, image = self.render_frame(character, time_sec)
      yield time_sec, image, frame_sounds

  def _compute_duration_sec(self) -> float:
    duration = 0.0
    for track in (
        self._left_eye_track,
        self._right_eye_track,
        self._mouth_track,
        self._left_hand_visible_track,
        self._right_hand_visible_track,
        self._left_hand_transform_track,
        self._right_hand_transform_track,
        self._head_transform_track,
        self._surface_line_offset_track,
        self._mask_boundary_offset_track,
        self._surface_line_visible_track,
        self._head_masking_enabled_track,
        self._left_hand_masking_enabled_track,
        self._right_hand_masking_enabled_track,
        self._sound_track,
    ):
      for event in track:
        duration = max(duration, self._event_end_time(event))
    return duration

  @staticmethod
  def _event_end_time(
    event: SequenceBooleanEvent | SequenceMouthEvent
    | SequenceTransformEvent | SequenceFloatEvent
    | SequenceSoundEvent
  ) -> float:
    return event.end_time

  @staticmethod
  def _sample_boolean(
    track: list[SequenceBooleanEvent],
    time_sec: float,
    default: bool,
  ) -> bool:
    for event in track:
      start = event.start_time
      end = event.end_time
      if start <= time_sec < end:
        return event.value
      if start > time_sec:
        break
    return default

  @staticmethod
  def _sample_mouth(
    track: list[SequenceMouthEvent],
    time_sec: float,
    default: MouthState,
  ) -> MouthState:
    for event in track:
      start = event.start_time
      end = event.end_time
      if start <= time_sec < end:
        return event.mouth_state
      if start > time_sec:
        break
    return default

  @staticmethod
  def _sample_transform(
    track: list[SequenceTransformEvent],
    time_sec: float,
    default: Transform,
  ) -> Transform:
    if not track:
      return default

    previous_target = default
    for event in track:
      start = event.start_time
      end = event.end_time

      if time_sec < start:
        return previous_target

      if start <= time_sec < end:
        duration = end - start
        if duration <= 1e-6:
          return event.target_transform
        progress = (time_sec - start) / duration
        progress = max(0.0, min(1.0, progress))
        return Transform(
          translate_x=_lerp(previous_target.translate_x,
                            event.target_transform.translate_x, progress),
          translate_y=_lerp(previous_target.translate_y,
                            event.target_transform.translate_y, progress),
          scale_x=_lerp(previous_target.scale_x,
                        event.target_transform.scale_x, progress),
          scale_y=_lerp(previous_target.scale_y,
                        event.target_transform.scale_y, progress),
        )

      previous_target = event.target_transform

    return previous_target

  @staticmethod
  def _sample_float(
    track: list[SequenceFloatEvent],
    time_sec: float,
    default: float,
  ) -> float:
    if not track:
      return default

    previous_target = default
    for event in track:
      start = event.start_time
      end = event.end_time
      target = event.target_value
      if time_sec < start:
        return previous_target
      if start <= time_sec < end:
        duration = end - start
        if duration <= 1e-6:
          return target
        progress = (time_sec - start) / duration
        progress = max(0.0, min(1.0, progress))
        return _lerp(previous_target, target, progress)
      if start > time_sec:
        break
      previous_target = target
    return previous_target


def _lerp(a: float, b: float, t: float) -> float:
  return a + (b - a) * t
