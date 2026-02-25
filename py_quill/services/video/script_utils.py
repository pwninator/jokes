"""Shared utilities for building joke/social video scripts."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from common.character_animator import CharacterAnimator
from common.posable_character import PosableCharacter, PoseState
from common.posable_character_sequence import (PosableCharacterSequence,
                                               SequenceBooleanEvent)
from services import audio_voices, firestore
from services.video.script import (FitMode, SceneRect, TimedCharacterSequence,
                                   TimedImage)

POP_IN_SEQUENCE_ID = "pop_in"
JOKE_AUDIO_RESPONSE_GAP_SEC = 0.8
JOKE_AUDIO_SETUP_GAP_SEC = 0.8
JOKE_AUDIO_PUNCHLINE_GAP_SEC = 1.0
LISTENER_POP_IN_DELAY_AFTER_TELLER_POP_IN_END_SEC = 0.7
VIDEO_TAIL_SEC = 2.0
GIGGLE_VARIANT_MIN = 1
GIGGLE_VARIANT_MAX = 3
BLINK_PERIOD_SEC = 4.0
BLINK_JITTER_SEC = 1.0
BLINK_DURATION_SEC = 0.15
BLINK_EYE_CLOSE_BUFFER_SEC = 2.0
"""Minimum time from open->closed transitions where blinks are disallowed."""
BLINK_SECOND_ACTOR_FIRST_DELAY_MULTIPLIER = 1.5
"""First-blink delay multiplier for the second actor track."""
_EPSILON = 1e-6


@dataclass(frozen=True)
class PortraitJokeTimeline:
  """Resolved timeline for a portrait joke scene."""

  pop_in_start_sec: float
  pop_in_end_sec: float
  intro_start_sec: float | None
  intro_end_sec: float | None
  setup_start_sec: float
  setup_end_sec: float
  response_start_sec: float | None
  response_end_sec: float | None
  punchline_start_sec: float
  punchline_end_sec: float
  laugh_start_sec: float
  laugh_end_sec: float
  total_duration_sec: float


def build_static_image_item(
  *,
  gcs_uri: str,
  duration_sec: float,
  z_index: int,
  rect: SceneRect,
  fit_mode: FitMode,
) -> TimedImage:
  """Build a static image layer spanning the entire script duration."""
  return TimedImage(
    gcs_uri=gcs_uri,
    start_time_sec=0.0,
    end_time_sec=duration_sec,
    z_index=int(z_index),
    rect=rect,
    fit_mode=fit_mode,
  )


def resolve_timeline(
  *,
  pop_in_sequence: PosableCharacterSequence,
  intro_sequence: PosableCharacterSequence | None,
  setup_sequence: PosableCharacterSequence,
  response_sequence: PosableCharacterSequence | None,
  punchline_sequence: PosableCharacterSequence,
  laugh_duration_sec: float,
  joke_audio_setup_gap_sec: float = JOKE_AUDIO_SETUP_GAP_SEC,
  joke_audio_response_gap_sec: float = JOKE_AUDIO_RESPONSE_GAP_SEC,
  joke_audio_punchline_gap_sec: float = JOKE_AUDIO_PUNCHLINE_GAP_SEC,
  video_tail_sec: float = VIDEO_TAIL_SEC,
) -> PortraitJokeTimeline:
  """Resolve all key script timestamps."""
  pop_in_duration = pop_in_sequence.duration_sec
  pop_in_start = 0.0
  pop_in_end = pop_in_duration

  intro_start: float | None = None
  intro_end: float | None = None
  intro_duration = (intro_sequence.duration_sec
                    if intro_sequence is not None else 0.0)
  if intro_sequence is not None:
    intro_start = pop_in_end
    intro_end = intro_start + intro_duration
  setup_duration = setup_sequence.duration_sec
  response_duration = (response_sequence.duration_sec
                       if response_sequence is not None else 0.0)
  punchline_duration = punchline_sequence.duration_sec

  setup_start = (
    intro_end +
    joke_audio_setup_gap_sec) if intro_end is not None else pop_in_end
  setup_end = setup_start + setup_duration
  response_start: float | None = None
  response_end: float | None = None
  punchline_start = setup_end + joke_audio_punchline_gap_sec
  if response_sequence is not None:
    response_start = setup_end + joke_audio_response_gap_sec
    response_end = response_start + response_duration
    punchline_start = response_end + joke_audio_punchline_gap_sec
  punchline_end = punchline_start + punchline_duration
  laugh_start = punchline_end
  laugh_end = laugh_start + max(0.0, laugh_duration_sec)
  total_duration = laugh_end + video_tail_sec

  return PortraitJokeTimeline(
    pop_in_start_sec=pop_in_start,
    pop_in_end_sec=pop_in_end,
    intro_start_sec=intro_start,
    intro_end_sec=intro_end,
    setup_start_sec=setup_start,
    setup_end_sec=setup_end,
    response_start_sec=response_start if response_start is not None else None,
    response_end_sec=response_end if response_end is not None else None,
    punchline_start_sec=punchline_start,
    punchline_end_sec=punchline_end,
    laugh_start_sec=laugh_start,
    laugh_end_sec=laugh_end,
    total_duration_sec=total_duration,
  )


def build_character_sequences(
  *,
  teller_character: PosableCharacter,
  listener_character: PosableCharacter | None,
  pop_in_sequence: PosableCharacterSequence,
  intro_sequence: PosableCharacterSequence | None,
  setup_sequence: PosableCharacterSequence,
  response_sequence: PosableCharacterSequence | None,
  punchline_sequence: PosableCharacterSequence,
  teller_laugh_sequence: PosableCharacterSequence,
  listener_laugh_sequence: PosableCharacterSequence | None,
  timeline: PortraitJokeTimeline,
  z_index: int,
  actor_band_rect: SceneRect,
  actor_side_margin_px: int,
  listener_pop_in_delay_after_teller_pop_in_end_sec:
  float = LISTENER_POP_IN_DELAY_AFTER_TELLER_POP_IN_END_SEC,
  extend_first_sequence: bool = False,
  surface_line_visible: bool | None = None,
) -> list[TimedCharacterSequence]:
  """Build timed character sequence items for teller/listener tracks."""
  tracks: list[tuple[PosableCharacter,
                     list[tuple[float, PosableCharacterSequence]]]] = []

  teller_dialogs: list[tuple[float, PosableCharacterSequence]] = [
    (timeline.pop_in_start_sec, pop_in_sequence)
  ]
  if intro_sequence is not None:
    teller_dialogs.append((timeline.intro_start_sec or 0.0, intro_sequence))
  teller_dialogs.extend([
    (timeline.setup_start_sec, setup_sequence),
    (timeline.punchline_start_sec, punchline_sequence),
    (timeline.laugh_start_sec, teller_laugh_sequence),
  ])
  tracks.append((teller_character, teller_dialogs))

  if listener_character:
    listener_pop_in_start_sec = (
      timeline.pop_in_end_sec +
      listener_pop_in_delay_after_teller_pop_in_end_sec)
    listener_dialogs: list[tuple[float, PosableCharacterSequence]] = [
      (listener_pop_in_start_sec, pop_in_sequence)
    ]
    if response_sequence and timeline.response_start_sec is not None:
      listener_dialogs.append((timeline.response_start_sec, response_sequence))
    if listener_laugh_sequence is not None:
      listener_dialogs.append(
        (timeline.laugh_start_sec, listener_laugh_sequence))
    tracks.append((listener_character, listener_dialogs))

  items: list[TimedCharacterSequence] = []
  actor_rects = build_actor_rects_for_tracks(
    tracks=tracks,
    actor_band_rect=actor_band_rect,
    actor_side_margin_px=actor_side_margin_px,
  )
  for actor_index, (character, dialogs) in enumerate(tracks):
    actor_id = f"actor_{actor_index}"
    actor_rect = actor_rects[actor_index]
    dialog_entries = _fill_track_gaps(
      dialogs=dialogs,
      scene_end_sec=timeline.total_duration_sec,
      extend_first_sequence=extend_first_sequence,
    )
    first_blink_delay_multiplier = (BLINK_SECOND_ACTOR_FIRST_DELAY_MULTIPLIER
                                    if actor_index == 1 else 1.0)
    dialog_entries = _inject_blinks(
      dialog_entries=dialog_entries,
      rng=random.Random(actor_id),
      first_blink_delay_multiplier=first_blink_delay_multiplier,
    )
    for start_time, sequence in dialog_entries:
      resolved_sequence = sequence
      if surface_line_visible is not None:
        resolved_sequence = _with_surface_line_visibility(
          sequence=resolved_sequence,
          visible=surface_line_visible,
        )
      duration_sec = resolved_sequence.duration_sec
      items.append(
        TimedCharacterSequence(
          actor_id=actor_id,
          character=character,
          sequence=resolved_sequence,
          start_time_sec=start_time,
          end_time_sec=start_time + duration_sec,
          z_index=int(z_index),
          rect=actor_rect,
          fit_mode="contain",
        ))

  return items


def _fill_track_gaps(
  *,
  dialogs: list[tuple[float, PosableCharacterSequence]],
  scene_end_sec: float,
  extend_first_sequence: bool,
) -> list[tuple[float, PosableCharacterSequence]]:
  """Fill timeline gaps with explicit default-pose or first-pose clips."""
  if not dialogs:
    return []

  sorted_dialogs = sorted(dialogs, key=lambda entry: entry[0])
  _, first_sequence = sorted_dialogs[0]

  out: list[tuple[float, PosableCharacterSequence]] = []
  cursor_sec = 0.0
  for index, (start_sec, sequence) in enumerate(sorted_dialogs):
    if start_sec > cursor_sec:
      gap_duration_sec = start_sec - cursor_sec
      if index == 0 and extend_first_sequence:
        out.append((cursor_sec,
                    _build_first_pose_filler_sequence(
                      first_sequence=first_sequence,
                      duration_sec=gap_duration_sec,
                    )))
      else:
        out.append(
          (cursor_sec, _build_default_pose_filler_sequence(gap_duration_sec)))
    out.append((start_sec, sequence))
    cursor_sec = max(cursor_sec, start_sec + sequence.duration_sec)

  if scene_end_sec > cursor_sec:
    out.append(
      (cursor_sec,
       _build_default_pose_filler_sequence(scene_end_sec - cursor_sec)))

  return out


def _build_default_pose_filler_sequence(
  duration_sec: float, ) -> PosableCharacterSequence:
  """Build a sequence that keeps the character at its default pose."""
  return PosableCharacterSequence.build_pose_hold_sequence(
    pose=PoseState(),
    duration_sec=duration_sec,
  )


def _build_first_pose_filler_sequence(
  *,
  first_sequence: PosableCharacterSequence,
  duration_sec: float,
) -> PosableCharacterSequence:
  """Build a filler that holds the initial pose of the first sequence."""
  animator = CharacterAnimator(first_sequence)
  return PosableCharacterSequence.build_pose_hold_sequence(
    pose=animator.sample_pose(0.0),
    duration_sec=duration_sec,
  )


def _with_surface_line_visibility(
  *,
  sequence: PosableCharacterSequence,
  visible: bool,
) -> PosableCharacterSequence:
  """Return a copy of `sequence` with surface line visibility fixed."""
  updated = copy.deepcopy(sequence)
  updated.sequence_surface_line_visible = [
    SequenceBooleanEvent(
      start_time=0.0,
      end_time=max(0.0, updated.duration_sec),
      value=visible,
    )
  ]
  updated.validate()
  return updated


def _inject_blinks(
  *,
  dialog_entries: list[tuple[float, PosableCharacterSequence]],
  rng: random.Random | None = None,
  blink_period_sec: float = BLINK_PERIOD_SEC,
  blink_jitter_sec: float = BLINK_JITTER_SEC,
  blink_duration_sec: float = BLINK_DURATION_SEC,
  eye_close_buffer_sec: float = BLINK_EYE_CLOSE_BUFFER_SEC,
  first_blink_delay_multiplier: float = 1.0,
) -> list[tuple[float, PosableCharacterSequence]]:
  """Inject blinks into resolved per-actor dialog entries.

  Args:
    dialog_entries: Ordered `(start_time_sec, sequence)` entries representing the
      actor's complete resolved timeline.
    rng: Optional random generator used to sample blink intervals.
    blink_period_sec: Target blink cadence in seconds.
    blink_jitter_sec: Symmetric jitter range applied to `blink_period_sec`.
    blink_duration_sec: Duration of each injected blink in seconds.
    eye_close_buffer_sec: Minimum distance from open->closed transitions where
      blinks are disallowed.
    first_blink_delay_multiplier: Multiplier applied to the first sampled blink
      delay per open window.

  Returns:
    A new list of dialog entries where eye tracks include injected blinks while
    preserving existing explicit eye-state intent.
  """
  if not dialog_entries:
    return []
  if blink_period_sec <= 0.0:
    raise ValueError("blink_period_sec must be positive")
  if blink_jitter_sec < 0.0:
    raise ValueError("blink_jitter_sec must be non-negative")
  if blink_duration_sec <= 0.0:
    raise ValueError("blink_duration_sec must be positive")
  if eye_close_buffer_sec < 0.0:
    raise ValueError("eye_close_buffer_sec must be non-negative")
  if first_blink_delay_multiplier <= 0.0:
    raise ValueError("first_blink_delay_multiplier must be positive")

  resolved_rng = rng or random.Random(0)
  open_windows, eye_close_times = _resolve_open_windows_and_eye_close_times(
    dialog_entries)
  if not open_windows:
    return dialog_entries

  blink_times = _generate_blink_times(
    open_windows=open_windows,
    eye_close_times=eye_close_times,
    rng=resolved_rng,
    blink_period_sec=blink_period_sec,
    blink_jitter_sec=blink_jitter_sec,
    blink_duration_sec=blink_duration_sec,
    eye_close_buffer_sec=eye_close_buffer_sec,
    first_blink_delay_multiplier=first_blink_delay_multiplier,
  )
  if not blink_times:
    return dialog_entries

  blink_intervals = [(time_sec, time_sec + blink_duration_sec)
                     for time_sec in blink_times]
  return _apply_global_blink_intervals(
    dialog_entries=dialog_entries,
    blink_intervals=blink_intervals,
  )


def _resolve_open_windows_and_eye_close_times(
  dialog_entries: list[tuple[float, PosableCharacterSequence]],
) -> tuple[list[tuple[float, float]], list[float]]:
  """Resolve global open-eye windows and close transition times.

  Args:
    dialog_entries: Actor timeline entries as `(global_start_sec, sequence)`.

  Returns:
    A tuple of:
      - `open_windows`: merged global windows where both eyes are open.
      - `eye_close_times`: global timestamps where state changes open->closed.
  """
  state_windows: list[tuple[float, float, bool]] = []
  for global_start_sec, sequence in dialog_entries:
    duration_sec = max(0.0, sequence.duration_sec)
    if duration_sec <= _EPSILON:
      continue
    animator = CharacterAnimator(sequence)
    boundaries = _sequence_eye_boundaries(sequence=sequence,
                                          duration_sec=duration_sec)
    for start_sec, end_sec in zip(boundaries[:-1], boundaries[1:]):
      if end_sec <= start_sec:
        continue
      pose = animator.sample_pose(start_sec)
      is_open = pose.left_eye_open and pose.right_eye_open
      state_windows.append((
        global_start_sec + start_sec,
        global_start_sec + end_sec,
        is_open,
      ))

  merged_windows = _merge_state_windows(state_windows)
  open_windows = [(start_sec, end_sec)
                  for start_sec, end_sec, is_open in merged_windows if is_open]

  eye_close_times: list[float] = []
  previous_is_open: bool | None = None
  for start_sec, _end_sec, is_open in merged_windows:
    if previous_is_open is True and not is_open:
      eye_close_times.append(start_sec)
    previous_is_open = is_open
  return open_windows, eye_close_times


def _sequence_eye_boundaries(
  *,
  sequence: PosableCharacterSequence,
  duration_sec: float,
) -> list[float]:
  """Build sorted boundary timestamps for eye-state evaluation.

  Args:
    sequence: Sequence whose eye tracks are being sampled.
    duration_sec: Sequence duration clamp used for boundary normalization.

  Returns:
    Sorted unique timestamps that partition eye-state intervals.
  """
  boundaries = {0.0, duration_sec}
  for event in sequence.sequence_left_eye_open:
    boundaries.add(max(0.0, min(duration_sec, event.start_time)))
    boundaries.add(max(0.0, min(duration_sec, event.end_time)))
  for event in sequence.sequence_right_eye_open:
    boundaries.add(max(0.0, min(duration_sec, event.start_time)))
    boundaries.add(max(0.0, min(duration_sec, event.end_time)))
  return sorted(boundaries)


def _merge_state_windows(
  windows: list[tuple[float, float,
                      bool]], ) -> list[tuple[float, float, bool]]:
  """Merge contiguous/overlapping boolean state windows.

  Args:
    windows: `(start_sec, end_sec, is_open)` windows to normalize.

  Returns:
    Sorted merged windows with no overlap and preserved state transitions.
  """
  if not windows:
    return []
  sorted_windows = sorted(windows, key=lambda item: (item[0], item[1]))
  merged: list[tuple[float, float, bool]] = []
  for start_sec, end_sec, is_open in sorted_windows:
    if not merged:
      merged.append((start_sec, end_sec, is_open))
      continue
    last_start, last_end, last_is_open = merged[-1]
    if is_open == last_is_open and start_sec <= (last_end + _EPSILON):
      merged[-1] = (last_start, max(last_end, end_sec), last_is_open)
      continue
    merged.append((start_sec, end_sec, is_open))
  return merged


def _generate_blink_times(
  *,
  open_windows: list[tuple[float, float]],
  eye_close_times: list[float],
  rng: random.Random,
  blink_period_sec: float,
  blink_jitter_sec: float,
  blink_duration_sec: float,
  eye_close_buffer_sec: float,
  first_blink_delay_multiplier: float,
) -> list[float]:
  """Generate blink start times inside valid open windows.

  Args:
    open_windows: Global windows where both eyes are open.
    eye_close_times: Global open->closed transition timestamps.
    rng: Random generator used to sample blink spacing.
    blink_period_sec: Target blink cadence in seconds.
    blink_jitter_sec: Symmetric jitter range around `blink_period_sec`.
    blink_duration_sec: Duration of each blink interval.
    eye_close_buffer_sec: Required distance from close transitions.
    first_blink_delay_multiplier: Multiplier applied to the first sampled blink
      delay per open window.

  Returns:
    Global blink start timestamps that satisfy timing and safety constraints.
  """
  min_period = max(0.0, blink_period_sec - blink_jitter_sec)
  max_period = blink_period_sec + blink_jitter_sec
  blink_times: list[float] = []
  for window_start_sec, window_end_sec in open_windows:
    cursor_sec = window_start_sec
    is_first_candidate = True
    while cursor_sec < window_end_sec:
      next_period = rng.uniform(min_period, max_period)
      if is_first_candidate:
        next_period *= first_blink_delay_multiplier
      candidate_sec = cursor_sec + next_period
      is_first_candidate = False
      if candidate_sec >= window_end_sec:
        break
      adjusted_sec = _adjust_away_from_eye_close_events(
        time_sec=candidate_sec,
        eye_close_times=eye_close_times,
        eye_close_buffer_sec=eye_close_buffer_sec,
      )
      if adjusted_sec is None:
        cursor_sec = candidate_sec
        continue
      if adjusted_sec < window_start_sec or adjusted_sec >= window_end_sec:
        cursor_sec = candidate_sec
        continue
      if adjusted_sec < (cursor_sec + min_period - _EPSILON):
        cursor_sec = candidate_sec
        continue
      if not _is_far_from_eye_close_events(
          time_sec=adjusted_sec,
          eye_close_times=eye_close_times,
          eye_close_buffer_sec=eye_close_buffer_sec):
        cursor_sec = candidate_sec
        continue
      blink_end_sec = adjusted_sec + blink_duration_sec
      if not _is_interval_within_open_windows(start_sec=adjusted_sec,
                                              end_sec=blink_end_sec,
                                              open_windows=open_windows):
        cursor_sec = candidate_sec
        continue
      blink_times.append(adjusted_sec)
      cursor_sec = max(adjusted_sec, candidate_sec)
  return blink_times


def _adjust_away_from_eye_close_events(
  *,
  time_sec: float,
  eye_close_times: list[float],
  eye_close_buffer_sec: float,
) -> float | None:
  """Shift a candidate time outside eye-close exclusion ranges.

  Args:
    time_sec: Candidate blink start timestamp.
    eye_close_times: Global open->closed transition timestamps.
    eye_close_buffer_sec: Exclusion radius around each close event.

  Returns:
    Adjusted timestamp if a valid position can be found, else `None`.
  """
  adjusted_sec = time_sec
  max_iterations = len(eye_close_times) + 1
  for _ in range(max_iterations):
    moved = False
    for close_time_sec in eye_close_times:
      distance_sec = adjusted_sec - close_time_sec
      if abs(distance_sec) >= eye_close_buffer_sec:
        continue
      adjusted_sec = (close_time_sec - eye_close_buffer_sec if distance_sec < 0
                      else close_time_sec + eye_close_buffer_sec)
      moved = True
      break
    if not moved:
      return adjusted_sec
  return None


def _is_far_from_eye_close_events(
  *,
  time_sec: float,
  eye_close_times: list[float],
  eye_close_buffer_sec: float,
) -> bool:
  """Check whether a timestamp is outside close-event exclusion ranges.

  Args:
    time_sec: Candidate blink timestamp.
    eye_close_times: Global open->closed transition timestamps.
    eye_close_buffer_sec: Exclusion radius around each close event.

  Returns:
    True if `time_sec` is at least `eye_close_buffer_sec` away from every close
    event; otherwise False.
  """
  for close_time_sec in eye_close_times:
    if abs(time_sec - close_time_sec) < eye_close_buffer_sec:
      return False
  return True


def _is_interval_within_open_windows(
  *,
  start_sec: float,
  end_sec: float,
  open_windows: list[tuple[float, float]],
) -> bool:
  """Check that an interval is fully contained in some open window.

  Args:
    start_sec: Interval start timestamp.
    end_sec: Interval end timestamp.
    open_windows: Global open-eye windows.

  Returns:
    True when the full interval `[start_sec, end_sec]` fits in a single open
    window; otherwise False.
  """
  for open_start_sec, open_end_sec in open_windows:
    if start_sec >= (open_start_sec - _EPSILON) and end_sec <= (open_end_sec +
                                                                _EPSILON):
      return True
  return False


def _apply_global_blink_intervals(
  *,
  dialog_entries: list[tuple[float, PosableCharacterSequence]],
  blink_intervals: list[tuple[float, float]],
) -> list[tuple[float, PosableCharacterSequence]]:
  """Apply global blink intervals to per-sequence local eye tracks.

  Args:
    dialog_entries: Actor timeline entries as `(global_start_sec, sequence)`.
    blink_intervals: Global blink intervals as `(start_sec, end_sec)`.

  Returns:
    Updated dialog entries with blink overrides applied to affected sequences.
  """
  if not blink_intervals:
    return dialog_entries

  updated_entries: list[tuple[float, PosableCharacterSequence]] = []
  for start_sec, sequence in dialog_entries:
    duration_sec = sequence.duration_sec
    end_sec = start_sec + duration_sec
    local_blinks: list[tuple[float, float]] = []
    for blink_start_sec, blink_end_sec in blink_intervals:
      if blink_start_sec < start_sec or blink_end_sec > end_sec:
        continue
      local_blinks.append(
        (blink_start_sec - start_sec, blink_end_sec - start_sec))
    if not local_blinks:
      updated_entries.append((start_sec, sequence))
      continue
    updated_entries.append((
      start_sec,
      _with_eye_blink_overrides(
        sequence=sequence,
        blink_intervals=local_blinks,
      ),
    ))
  return updated_entries


def _with_eye_blink_overrides(
  *,
  sequence: PosableCharacterSequence,
  blink_intervals: list[tuple[float, float]],
) -> PosableCharacterSequence:
  """Inject blink intervals into a sequence's left/right eye tracks.

  Args:
    sequence: Source sequence to copy and modify.
    blink_intervals: Local blink intervals relative to this sequence.

  Returns:
    A deep-copied sequence with both eye tracks rewritten to include blink
    overrides while preserving existing non-eye tracks.
  """
  updated = copy.deepcopy(sequence)
  duration_sec = max(0.0, updated.duration_sec)
  if duration_sec <= _EPSILON:
    return updated

  left_default = (updated.initial_pose.left_eye_open
                  if updated.initial_pose is not None else True)
  right_default = (updated.initial_pose.right_eye_open
                   if updated.initial_pose is not None else True)

  updated.sequence_left_eye_open = _override_boolean_track_with_blinks(
    original_track=updated.sequence_left_eye_open,
    default_value=left_default,
    duration_sec=duration_sec,
    blink_intervals=blink_intervals,
  )
  updated.sequence_right_eye_open = _override_boolean_track_with_blinks(
    original_track=updated.sequence_right_eye_open,
    default_value=right_default,
    duration_sec=duration_sec,
    blink_intervals=blink_intervals,
  )
  updated.validate()
  return updated


def _override_boolean_track_with_blinks(
  *,
  original_track: list[SequenceBooleanEvent],
  default_value: bool,
  duration_sec: float,
  blink_intervals: list[tuple[float, float]],
) -> list[SequenceBooleanEvent]:
  """Rewrite a boolean event track with blink overrides applied.

  Args:
    original_track: Existing non-overlapping boolean events for a property.
    default_value: Value when no event is active at a sampled timestamp.
    duration_sec: Timeline duration for normalization and clamping.
    blink_intervals: Local blink intervals to force `False`.

  Returns:
    A normalized non-overlapping event list with blink overrides embedded.
  """
  boundaries = {0.0, duration_sec}
  for event in original_track:
    boundaries.add(max(0.0, min(duration_sec, event.start_time)))
    boundaries.add(max(0.0, min(duration_sec, event.end_time)))
  for blink_start_sec, blink_end_sec in blink_intervals:
    boundaries.add(max(0.0, min(duration_sec, blink_start_sec)))
    boundaries.add(max(0.0, min(duration_sec, blink_end_sec)))

  events: list[SequenceBooleanEvent] = []
  for start_sec, end_sec in zip(
      sorted(boundaries)[:-1],
      sorted(boundaries)[1:]):
    if end_sec <= start_sec:
      continue
    value = _sample_boolean_track(
      track=original_track,
      time_sec=start_sec,
      default_value=default_value,
    )
    if _is_time_in_intervals(start_sec, blink_intervals):
      value = False
    if events and events[-1].value == value:
      events[-1].end_time = end_sec
      continue
    events.append(
      SequenceBooleanEvent(
        start_time=start_sec,
        end_time=end_sec,
        value=value,
      ))
  return events


def _sample_boolean_track(
  *,
  track: list[SequenceBooleanEvent],
  time_sec: float,
  default_value: bool,
) -> bool:
  """Sample a boolean event track at a specific time.

  Args:
    track: Sorted non-overlapping boolean events.
    time_sec: Time to sample.
    default_value: Value used when no event covers `time_sec`.

  Returns:
    The active event value at `time_sec`, or `default_value` if none.
  """
  for event in track:
    if event.start_time <= time_sec < event.end_time:
      return event.value
    if event.start_time > time_sec:
      break
  return default_value


def _is_time_in_intervals(
  time_sec: float,
  intervals: list[tuple[float, float]],
) -> bool:
  """Check whether a timestamp lies inside any half-open interval.

  Args:
    time_sec: Timestamp to evaluate.
    intervals: Half-open intervals as `(start_sec, end_sec)`.

  Returns:
    True if `start_sec <= time_sec < end_sec` for at least one interval.
  """
  for start_sec, end_sec in intervals:
    if start_sec <= time_sec < end_sec:
      return True
  return False


def load_sequence_from_firestore(
    sequence_id: str = POP_IN_SEQUENCE_ID) -> PosableCharacterSequence:
  """Load a required character sequence by Firestore document id."""
  sequence = firestore.get_posable_character_sequence(sequence_id)
  if sequence is None:
    raise ValueError(
      f"Missing required posable_character_sequences/{sequence_id}")
  sequence.validate()
  return sequence


def load_random_giggle_sequence(
  *,
  voice: audio_voices.Voice,
  giggle_variant_min: int = GIGGLE_VARIANT_MIN,
  giggle_variant_max: int = GIGGLE_VARIANT_MAX,
) -> PosableCharacterSequence:
  """Load a random `voice_giggle[1-3]` sequence for the provided voice enum."""
  giggle_variant = random.randint(giggle_variant_min, giggle_variant_max)
  sequence_id = f"{voice.name}_giggle{giggle_variant}"
  return load_sequence_from_firestore(sequence_id)


def build_actor_rects_for_tracks(
  *,
  tracks: list[tuple[PosableCharacter, list[tuple[float,
                                                  PosableCharacterSequence]]]],
  actor_band_rect: SceneRect,
  actor_side_margin_px: int,
) -> list[SceneRect]:
  """Build actor rects with proportional horizontal allocation and bottom alignment."""
  if not tracks:
    return []

  actor_sizes: list[tuple[int, int]] = []
  for character, _dialogs in tracks:
    actor_sizes.append(
      (character.definition.width, character.definition.height))

  tallest_height = max(height for _width, height in actor_sizes)
  left_bound = int(actor_band_rect.x_px + actor_side_margin_px)
  right_bound = int(actor_band_rect.x_px + actor_band_rect.width_px -
                    actor_side_margin_px)
  available_width = max(1, right_bound - left_bound)
  total_width = max(1, sum(width for width, _height in actor_sizes))

  rects: list[SceneRect] = []
  cursor_x = left_bound
  for width_px, height_px in actor_sizes:
    slot_width = available_width * (width_px / total_width)
    center_x = cursor_x + (slot_width / 2.0)
    y = int(actor_band_rect.y_px + (tallest_height - height_px))
    x = int(round(center_x - (width_px / 2.0)))
    rects.append(
      SceneRect(
        x_px=x,
        y_px=int(y),
        width_px=int(width_px),
        height_px=int(height_px),
      ))
    cursor_x += slot_width
  return rects
