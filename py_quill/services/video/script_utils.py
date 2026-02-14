"""Shared utilities for building joke/social video scripts."""

from __future__ import annotations

import random
from dataclasses import dataclass

from common.posable_character import PosableCharacter
from common.posable_character_sequence import PosableCharacterSequence
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


def resolve_portrait_timeline(
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


def build_character_dialogs(
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
    for start_time, sequence in dialogs:
      duration_sec = sequence.duration_sec
      items.append(
        TimedCharacterSequence(
          actor_id=actor_id,
          character=character,
          sequence=sequence,
          start_time_sec=start_time,
          end_time_sec=start_time + duration_sec,
          z_index=int(z_index),
          rect=actor_rect,
          fit_mode="contain",
        ))

  return items


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
