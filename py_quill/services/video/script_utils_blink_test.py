from __future__ import annotations

import random

import pytest
from common.posable_character import PoseState
from common.posable_character_sequence import PosableCharacterSequence
from services.video import script_utils


class _ConstantRandom(random.Random):
  """Deterministic RNG test double that returns a fixed uniform value."""

  def __init__(self, value: float):
    """Initialize the deterministic random generator.

    Args:
      value: Constant value returned from `uniform`.

    Returns:
      None.
    """
    super().__init__(0)
    self._value = value

  def uniform(self, a: float, b: float) -> float:
    """Return a fixed value regardless of requested range.

    Args:
      a: Lower bound requested by caller.
      b: Upper bound requested by caller.

    Returns:
      The configured constant value.
    """
    _ = (a, b)
    return self._value


def _pose_hold_sequence(
  *,
  duration_sec: float,
  left_eye_open: bool,
  right_eye_open: bool,
) -> PosableCharacterSequence:
  """Build a static pose-hold sequence for blink test setup.

  Args:
    duration_sec: Sequence duration in seconds.
    left_eye_open: Left eye state held for the full duration.
    right_eye_open: Right eye state held for the full duration.

  Returns:
    A `PosableCharacterSequence` that keeps the requested eye state.
  """
  return PosableCharacterSequence.build_pose_hold_sequence(
    pose=PoseState(
      left_eye_open=left_eye_open,
      right_eye_open=right_eye_open,
    ),
    duration_sec=duration_sec,
  )


def _blink_starts_from_track(
  entries: list[tuple[float, PosableCharacterSequence]],
  *,
  from_left_track: bool,
  blink_duration_sec: float,
) -> list[float]:
  """Extract global blink start times from one eye track.

  Args:
    entries: Timeline entries as `(sequence_start_sec, sequence)`.
    from_left_track: True to inspect left-eye events, False for right-eye.
    blink_duration_sec: Duration used to identify injected blink events.

  Returns:
    Global blink start times matching the expected blink duration.
  """
  starts: list[float] = []
  for sequence_start_sec, sequence in entries:
    track = (sequence.sequence_left_eye_open
             if from_left_track else sequence.sequence_right_eye_open)
    for event in track:
      duration_sec = event.end_time - event.start_time
      if event.value:
        continue
      if duration_sec != pytest.approx(blink_duration_sec):
        continue
      starts.append(sequence_start_sec + event.start_time)
  return starts


def _blink_starts(
  entries: list[tuple[float, PosableCharacterSequence]],
  *,
  blink_duration_sec: float,
) -> tuple[list[float], list[float]]:
  """Extract global blink starts from both left and right eye tracks.

  Args:
    entries: Timeline entries as `(sequence_start_sec, sequence)`.
    blink_duration_sec: Duration used to identify injected blink events.

  Returns:
    Tuple of `(left_blink_starts, right_blink_starts)`.
  """
  left_starts = _blink_starts_from_track(
    entries,
    from_left_track=True,
    blink_duration_sec=blink_duration_sec,
  )
  right_starts = _blink_starts_from_track(
    entries,
    from_left_track=False,
    blink_duration_sec=blink_duration_sec,
  )
  return left_starts, right_starts


def test_inject_blinks_long_open_window_adds_periodic_blinks():
  entries = [(0.0,
              _pose_hold_sequence(
                duration_sec=10.0,
                left_eye_open=True,
                right_eye_open=True,
              ))]

  updated = script_utils._inject_blinks(
    dialog_entries=entries,
    rng=random.Random(7),
    blink_period_sec=4.0,
    blink_jitter_sec=0.0,
    blink_duration_sec=0.15,
    eye_close_buffer_sec=2.0,
  )

  left_starts, right_starts = _blink_starts(updated, blink_duration_sec=0.15)
  assert left_starts == pytest.approx([4.0, 8.0])
  assert right_starts == pytest.approx([4.0, 8.0])


def test_inject_blinks_closed_eyes_have_no_new_blinks():
  entries = [(0.0,
              _pose_hold_sequence(
                duration_sec=8.0,
                left_eye_open=False,
                right_eye_open=False,
              ))]

  updated = script_utils._inject_blinks(
    dialog_entries=entries,
    rng=random.Random(11),
    blink_period_sec=4.0,
    blink_jitter_sec=1.0,
    blink_duration_sec=0.15,
    eye_close_buffer_sec=2.0,
  )

  left_starts, right_starts = _blink_starts(updated, blink_duration_sec=0.15)
  assert left_starts == []
  assert right_starts == []


def test_inject_blinks_adjusts_to_two_seconds_before_eye_close():
  entries = [
    (0.0,
     _pose_hold_sequence(
       duration_sec=5.0,
       left_eye_open=True,
       right_eye_open=True,
     )),
    (5.0,
     _pose_hold_sequence(
       duration_sec=2.0,
       left_eye_open=False,
       right_eye_open=False,
     )),
  ]

  updated = script_utils._inject_blinks(
    dialog_entries=entries,
    rng=_ConstantRandom(4.0),
    blink_period_sec=4.0,
    blink_jitter_sec=1.0,
    blink_duration_sec=0.15,
    eye_close_buffer_sec=2.0,
  )

  left_starts, right_starts = _blink_starts(updated, blink_duration_sec=0.15)
  assert left_starts == pytest.approx([3.0])
  assert right_starts == pytest.approx([3.0])


def test_inject_blinks_skips_short_open_window_near_close_event():
  entries = [
    (0.0,
     _pose_hold_sequence(
       duration_sec=3.9,
       left_eye_open=True,
       right_eye_open=True,
     )),
    (3.9,
     _pose_hold_sequence(
       duration_sec=2.0,
       left_eye_open=False,
       right_eye_open=False,
     )),
  ]

  updated = script_utils._inject_blinks(
    dialog_entries=entries,
    rng=_ConstantRandom(3.0),
    blink_period_sec=4.0,
    blink_jitter_sec=1.0,
    blink_duration_sec=0.15,
    eye_close_buffer_sec=2.0,
  )

  left_starts, right_starts = _blink_starts(updated, blink_duration_sec=0.15)
  assert left_starts == []
  assert right_starts == []


def test_inject_blinks_across_sequences_targets_correct_local_sequence():
  entries = [
    (0.0,
     _pose_hold_sequence(
       duration_sec=2.0,
       left_eye_open=True,
       right_eye_open=True,
     )),
    (2.0,
     _pose_hold_sequence(
       duration_sec=4.0,
       left_eye_open=True,
       right_eye_open=True,
     )),
  ]

  updated = script_utils._inject_blinks(
    dialog_entries=entries,
    rng=random.Random(31),
    blink_period_sec=4.0,
    blink_jitter_sec=0.0,
    blink_duration_sec=0.15,
    eye_close_buffer_sec=2.0,
  )

  left_starts, right_starts = _blink_starts(updated, blink_duration_sec=0.15)
  assert left_starts == pytest.approx([4.0])
  assert right_starts == pytest.approx([4.0])


def test_inject_blinks_applies_first_delay_multiplier():
  entries = [(0.0,
              _pose_hold_sequence(
                duration_sec=10.0,
                left_eye_open=True,
                right_eye_open=True,
              ))]

  updated = script_utils._inject_blinks(
    dialog_entries=entries,
    rng=_ConstantRandom(4.0),
    blink_period_sec=4.0,
    blink_jitter_sec=1.0,
    blink_duration_sec=0.15,
    eye_close_buffer_sec=2.0,
    first_blink_delay_multiplier=1.5,
  )

  left_starts, right_starts = _blink_starts(updated, blink_duration_sec=0.15)
  assert left_starts == pytest.approx([6.0])
  assert right_starts == pytest.approx([6.0])
