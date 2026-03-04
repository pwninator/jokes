"""Shared utilities for building joke/social video scripts."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, replace

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
  listener_pop_in_delay_after_teller_pop_in_end_sec:
  float = LISTENER_POP_IN_DELAY_AFTER_TELLER_POP_IN_END_SEC,
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
    listener_pop_in_end = (
      pop_in_end + listener_pop_in_delay_after_teller_pop_in_end_sec +
      pop_in_duration)
    response_start = max(setup_end + joke_audio_response_gap_sec,
                         listener_pop_in_end)
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


def build_portrait_timeline_and_character_items(
  *,
  teller_character: PosableCharacter,
  teller_voice: audio_voices.Voice,
  setup_sequence: PosableCharacterSequence,
  punchline_sequence: PosableCharacterSequence,
  z_index: int,
  actor_band_rect: SceneRect,
  actor_side_margin_px: int,
  listener_character: PosableCharacter | None = None,
  listener_voice: audio_voices.Voice | None = None,
  intro_sequence: PosableCharacterSequence | None = None,
  response_sequence: PosableCharacterSequence | None = None,
  extend_first_sequence: bool = False,
  surface_line_visible: bool | None = None,
) -> tuple[PortraitJokeTimeline, list[TimedCharacterSequence]]:
  """Load shared portrait joke sequences, resolve the timeline, and build items."""
  pop_in_sequence = load_sequence_from_firestore()
  if pop_in_sequence.duration_sec <= 0:
    raise ValueError("pop_in sequence must have positive duration")

  teller_laugh_sequence = load_random_giggle_sequence(voice=teller_voice)
  teller_laugh_duration_sec = teller_laugh_sequence.duration_sec
  if teller_laugh_duration_sec <= 0:
    raise ValueError(
      f"{teller_voice.name} giggle sequence must have positive duration")

  listener_laugh_sequence: PosableCharacterSequence | None = None
  listener_laugh_duration_sec = 0.0
  if listener_character is not None:
    if listener_voice is None:
      raise ValueError(
        "listener_voice is required when listener_character is set")
    listener_laugh_sequence = load_random_giggle_sequence(voice=listener_voice)
    listener_laugh_duration_sec = listener_laugh_sequence.duration_sec
    if listener_laugh_duration_sec <= 0:
      raise ValueError(
        f"{listener_voice.name} giggle sequence must have positive duration")

  timeline = resolve_timeline(
    pop_in_sequence=pop_in_sequence,
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
    laugh_duration_sec=max(teller_laugh_duration_sec,
                           listener_laugh_duration_sec),
  )
  character_items = build_character_sequences(
    teller_character=teller_character,
    listener_character=listener_character,
    pop_in_sequence=pop_in_sequence,
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
    teller_laugh_sequence=teller_laugh_sequence,
    listener_laugh_sequence=listener_laugh_sequence,
    timeline=timeline,
    z_index=z_index,
    actor_band_rect=actor_band_rect,
    actor_side_margin_px=actor_side_margin_px,
    extend_first_sequence=extend_first_sequence,
    surface_line_visible=surface_line_visible,
  )
  return timeline, character_items


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
  characters: list[PosableCharacter] = [teller_character]
  if listener_character is not None:
    characters.append(listener_character)

  actor_rects = build_actor_rects_for_tracks(
    characters=characters,
    actor_band_rect=actor_band_rect,
    actor_side_margin_px=actor_side_margin_px,
  )

  teller_items = [
    _build_timed_character_item(
      actor_id="actor_0",
      character=teller_character,
      sequence=pop_in_sequence,
      start_time_sec=timeline.pop_in_start_sec,
      end_time_sec=timeline.pop_in_end_sec,
      z_index=z_index,
      rect=actor_rects[0],
    ),
    _build_timed_character_item(
      actor_id="actor_0",
      character=teller_character,
      sequence=setup_sequence,
      start_time_sec=timeline.setup_start_sec,
      end_time_sec=timeline.setup_end_sec,
      z_index=z_index,
      rect=actor_rects[0],
    ),
    _build_timed_character_item(
      actor_id="actor_0",
      character=teller_character,
      sequence=punchline_sequence,
      start_time_sec=timeline.punchline_start_sec,
      end_time_sec=timeline.punchline_end_sec,
      z_index=z_index,
      rect=actor_rects[0],
    ),
    _build_timed_character_item(
      actor_id="actor_0",
      character=teller_character,
      sequence=teller_laugh_sequence,
      start_time_sec=timeline.laugh_start_sec,
      end_time_sec=timeline.laugh_start_sec + teller_laugh_sequence.duration_sec,
      z_index=z_index,
      rect=actor_rects[0],
    ),
  ]
  if intro_sequence is not None and timeline.intro_start_sec is not None and timeline.intro_end_sec is not None:
    teller_items.insert(
      1,
      _build_timed_character_item(
        actor_id="actor_0",
        character=teller_character,
        sequence=intro_sequence,
        start_time_sec=timeline.intro_start_sec,
        end_time_sec=timeline.intro_end_sec,
        z_index=z_index,
        rect=actor_rects[0],
      ))

  items_by_actor = [
    _finalize_actor_track(
      base_items=teller_items,
      scene_end_sec=timeline.total_duration_sec,
      extend_first_sequence=extend_first_sequence,
      surface_line_visible=surface_line_visible,
      blink_rng=random.Random("actor_0"),
      first_blink_delay_multiplier=1.0,
    )
  ]

  if listener_character is not None:
    listener_pop_in_start_sec = (
      timeline.pop_in_end_sec +
      listener_pop_in_delay_after_teller_pop_in_end_sec)
    listener_items = [
      _build_timed_character_item(
        actor_id="actor_1",
        character=listener_character,
        sequence=pop_in_sequence,
        start_time_sec=listener_pop_in_start_sec,
        end_time_sec=listener_pop_in_start_sec + pop_in_sequence.duration_sec,
        z_index=z_index,
        rect=actor_rects[1],
      ),
    ]
    if (response_sequence is not None and timeline.response_start_sec is not None
        and timeline.response_end_sec is not None):
      listener_items.append(
        _build_timed_character_item(
          actor_id="actor_1",
          character=listener_character,
          sequence=response_sequence,
          start_time_sec=timeline.response_start_sec,
          end_time_sec=timeline.response_end_sec,
          z_index=z_index,
          rect=actor_rects[1],
        ))
    if listener_laugh_sequence is not None:
      listener_items.append(
        _build_timed_character_item(
          actor_id="actor_1",
          character=listener_character,
          sequence=listener_laugh_sequence,
          start_time_sec=timeline.laugh_start_sec,
          end_time_sec=timeline.laugh_start_sec +
          listener_laugh_sequence.duration_sec,
          z_index=z_index,
          rect=actor_rects[1],
        ))
    items_by_actor.append(
      _finalize_actor_track(
        base_items=listener_items,
        scene_end_sec=timeline.total_duration_sec,
        extend_first_sequence=extend_first_sequence,
        surface_line_visible=surface_line_visible,
        blink_rng=random.Random("actor_1"),
        first_blink_delay_multiplier=
        BLINK_SECOND_ACTOR_FIRST_DELAY_MULTIPLIER,
      ))

  return [item for actor_items in items_by_actor for item in actor_items]


def _finalize_actor_track(
  *,
  base_items: list[TimedCharacterSequence],
  scene_end_sec: float,
  extend_first_sequence: bool,
  surface_line_visible: bool | None,
  blink_rng: random.Random,
  first_blink_delay_multiplier: float,
) -> list[TimedCharacterSequence]:
  """Fill gaps, inject blinks, and apply per-track overrides."""
  items = _fill_track_gaps(
    items=base_items,
    scene_end_sec=scene_end_sec,
    extend_first_sequence=extend_first_sequence,
  )
  items = _inject_blinks(
    items=items,
    rng=blink_rng,
    first_blink_delay_multiplier=first_blink_delay_multiplier,
  )
  if surface_line_visible is None:
    return items
  return [
    replace(
      item,
      sequence=_with_surface_line_visibility(
        sequence=item.sequence,
        visible=surface_line_visible,
      )) for item in items
  ]


def _build_timed_character_item(
  *,
  actor_id: str,
  character: PosableCharacter,
  sequence: PosableCharacterSequence,
  start_time_sec: float,
  end_time_sec: float,
  z_index: int,
  rect: SceneRect,
  fit_mode: FitMode = "contain",
) -> TimedCharacterSequence:
  """Build a timed character item and enforce duration/window agreement."""
  item_duration_sec = float(end_time_sec) - float(start_time_sec)
  if item_duration_sec <= 0.0:
    raise ValueError(
      f"TimedCharacterSequence window must be positive for actor_id "
      f"'{actor_id}': start={start_time_sec:.6f} end={end_time_sec:.6f}")
  sequence_duration_sec = float(sequence.duration_sec)
  if abs(sequence_duration_sec - item_duration_sec) > _EPSILON:
    raise ValueError(
      f"Sequence duration {sequence_duration_sec:.6f}s does not match item "
      f"window {item_duration_sec:.6f}s for actor_id '{actor_id}'")
  return TimedCharacterSequence(
    actor_id=actor_id,
    character=character,
    sequence=sequence,
    start_time_sec=float(start_time_sec),
    end_time_sec=float(end_time_sec),
    z_index=int(z_index),
    rect=rect,
    fit_mode=fit_mode,
  )


def _fill_track_gaps(
  *,
  items: list[TimedCharacterSequence],
  scene_end_sec: float,
  extend_first_sequence: bool,
) -> list[TimedCharacterSequence]:
  """Fill timeline gaps with explicit default-pose or first-pose clips."""
  if not items:
    return []

  sorted_items = sorted(items, key=lambda item: item.start_time_sec)
  first_item = sorted_items[0]
  first_sequence = first_item.sequence

  out: list[TimedCharacterSequence] = []
  cursor_sec = 0.0
  for index, item in enumerate(sorted_items):
    if item.start_time_sec > cursor_sec:
      gap_duration_sec = item.start_time_sec - cursor_sec
      if index == 0 and extend_first_sequence:
        filler_sequence = _build_first_pose_filler_sequence(
          first_sequence=first_sequence,
          duration_sec=gap_duration_sec,
        )
      else:
        filler_sequence = _build_default_pose_filler_sequence(gap_duration_sec)
      out.append(
        _build_timed_character_item(
          actor_id=first_item.actor_id,
          character=first_item.character,
          sequence=filler_sequence,
          start_time_sec=cursor_sec,
          end_time_sec=item.start_time_sec,
          z_index=first_item.z_index,
          rect=first_item.rect,
          fit_mode=first_item.fit_mode,
        ))
    out.append(item)
    cursor_sec = item.end_time_sec

  if scene_end_sec > cursor_sec:
    out.append(
      _build_timed_character_item(
        actor_id=first_item.actor_id,
        character=first_item.character,
        sequence=_build_default_pose_filler_sequence(scene_end_sec - cursor_sec),
        start_time_sec=cursor_sec,
        end_time_sec=scene_end_sec,
        z_index=first_item.z_index,
        rect=first_item.rect,
        fit_mode=first_item.fit_mode,
      ))

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
  items: list[TimedCharacterSequence],
  rng: random.Random | None = None,
  blink_period_sec: float = BLINK_PERIOD_SEC,
  blink_jitter_sec: float = BLINK_JITTER_SEC,
  blink_duration_sec: float = BLINK_DURATION_SEC,
  eye_close_buffer_sec: float = BLINK_EYE_CLOSE_BUFFER_SEC,
  first_blink_delay_multiplier: float = 1.0,
) -> list[TimedCharacterSequence]:
  """Inject blinks into resolved per-actor dialog entries.

  Args:
    items: Actor timeline items representing the actor's complete timeline.
    rng: Optional random generator used to sample blink intervals.
    blink_period_sec: Target blink cadence in seconds.
    blink_jitter_sec: Symmetric jitter range applied to `blink_period_sec`.
    blink_duration_sec: Duration of each injected blink in seconds.
    eye_close_buffer_sec: Minimum distance from open->closed transitions where
      blinks are disallowed.
    first_blink_delay_multiplier: Multiplier applied to the first sampled blink
      delay per open window.

  Returns:
    A new list of actor items where eye tracks include injected blinks while
    preserving existing explicit eye-state intent.
  """
  if not items:
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
    items)
  if not open_windows:
    return items

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
    return items

  blink_intervals = [(time_sec, time_sec + blink_duration_sec)
                     for time_sec in blink_times]
  return _apply_global_blink_intervals(
    items=items,
    blink_intervals=blink_intervals,
  )


def _resolve_open_windows_and_eye_close_times(
  items: list[TimedCharacterSequence],
) -> tuple[list[tuple[float, float]], list[float]]:
  """Resolve global open-eye windows and close transition times.

  Args:
    items: Actor timeline items.

  Returns:
    A tuple of:
      - `open_windows`: merged global windows where both eyes are open.
      - `eye_close_times`: global timestamps where state changes open->closed.
  """
  state_windows: list[tuple[float, float, bool]] = []
  for item in items:
    duration_sec = max(0.0, item.end_time_sec - item.start_time_sec)
    if duration_sec <= _EPSILON:
      continue
    animator = CharacterAnimator(item.sequence)
    boundaries = _sequence_eye_boundaries(sequence=item.sequence,
                                          duration_sec=duration_sec)
    for start_sec, end_sec in zip(boundaries[:-1], boundaries[1:]):
      if end_sec <= start_sec:
        continue
      pose = animator.sample_pose(start_sec)
      is_open = pose.left_eye_open and pose.right_eye_open
      state_windows.append((
        item.start_time_sec + start_sec,
        item.start_time_sec + end_sec,
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
  items: list[TimedCharacterSequence],
  blink_intervals: list[tuple[float, float]],
) -> list[TimedCharacterSequence]:
  """Apply global blink intervals to per-sequence local eye tracks.

  Args:
    items: Actor timeline items.
    blink_intervals: Global blink intervals as `(start_sec, end_sec)`.

  Returns:
    Updated actor items with blink overrides applied to affected sequences.
  """
  if not blink_intervals:
    return items

  updated_items: list[TimedCharacterSequence] = []
  for item in items:
    local_blinks: list[tuple[float, float]] = []
    for blink_start_sec, blink_end_sec in blink_intervals:
      if (blink_start_sec < item.start_time_sec
          or blink_end_sec > item.end_time_sec):
        continue
      local_blinks.append(
        (blink_start_sec - item.start_time_sec,
         blink_end_sec - item.start_time_sec))
    if not local_blinks:
      updated_items.append(item)
      continue
    updated_items.append(
      replace(
        item,
        sequence=_with_eye_blink_overrides(
          sequence=item.sequence,
          blink_intervals=local_blinks,
        )))
  return updated_items


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
  characters: list[PosableCharacter],
  actor_band_rect: SceneRect,
  actor_side_margin_px: int,
) -> list[SceneRect]:
  """Build actor rects with proportional horizontal allocation and bottom alignment."""
  if not characters:
    return []

  actor_sizes: list[tuple[int, int]] = []
  for character in characters:
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
