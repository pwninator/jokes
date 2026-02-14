"""Build declarative `SceneScript` objects for joke/social portrait videos."""

from __future__ import annotations

import random
from dataclasses import dataclass

from common.posable_character import PosableCharacter
from common.posable_character_sequence import PosableCharacterSequence
from services import audio_voices, firestore
from services.video.script import (FitMode, SceneCanvas, SceneRect,
                                   SceneScript, TimedCharacterSequence,
                                   TimedImage)

_PORTRAIT_VIDEO_WIDTH_PX = 1080
_PORTRAIT_VIDEO_HEIGHT_PX = 1920
_PORTRAIT_IMAGE_LAYER_Z_INDEX = 20
_PORTRAIT_CHARACTER_LAYER_Z_INDEX = 30
_PORTRAIT_BANNER_BACKGROUND_Z_INDEX = 30
_PORTRAIT_BANNER_LOGO_Z_INDEX = 40
_PORTRAIT_FOOTER_BACKGROUND_Z_INDEX = 10
_PORTRAIT_FOOTER_BACKGROUND_GCS_URI = (
  "gs://images.quillsstorybook.com/_joke_assets/blank_paper.png")

_PORTRAIT_BANNER_HEIGHT_PX = 240
_PORTRAIT_BANNER_HORIZONTAL_MARGIN_PX = 80
_PORTRAIT_IMAGE_HEIGHT_PX = 1080
_PORTRAIT_CHARACTER_GAP_PX = 120
_PORTRAIT_CHARACTER_BAND_HEIGHT_PX = 300
_PORTRAIT_BOTTOM_SAFE_MARGIN_PX = 120
_PORTRAIT_CHARACTER_SIDE_MARGIN_PX = 80

_PORTRAIT_IMAGE_TOP_PX = _PORTRAIT_BANNER_HEIGHT_PX
_PORTRAIT_IMAGE_BOTTOM_PX = _PORTRAIT_IMAGE_TOP_PX + _PORTRAIT_IMAGE_HEIGHT_PX
_PORTRAIT_CHARACTER_TOP_PX = _PORTRAIT_IMAGE_BOTTOM_PX + _PORTRAIT_CHARACTER_GAP_PX
_PORTRAIT_CHARACTER_BOTTOM_PX = (_PORTRAIT_CHARACTER_TOP_PX +
                                 _PORTRAIT_CHARACTER_BAND_HEIGHT_PX)
_PORTRAIT_FOOTER_HEIGHT_PX = _PORTRAIT_VIDEO_HEIGHT_PX - _PORTRAIT_IMAGE_BOTTOM_PX
_PORTRAIT_ACTUAL_BOTTOM_MARGIN_PX = (_PORTRAIT_VIDEO_HEIGHT_PX -
                                     _PORTRAIT_CHARACTER_BOTTOM_PX)
_PORTRAIT_BANNER_GCS_URI = (
  "gs://images.quillsstorybook.com/_joke_assets/logos/icon_words_transparent_light.png"
)
_PORTRAIT_BANNER_RECT = SceneRect(
  x_px=0,
  y_px=0,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX,
  height_px=_PORTRAIT_BANNER_HEIGHT_PX,
)
_PORTRAIT_BANNER_LOGO_RECT = SceneRect(
  x_px=_PORTRAIT_BANNER_HORIZONTAL_MARGIN_PX,
  y_px=0,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX -
  (_PORTRAIT_BANNER_HORIZONTAL_MARGIN_PX * 2),
  height_px=_PORTRAIT_BANNER_HEIGHT_PX,
)
_PORTRAIT_TOP_RECT = SceneRect(
  x_px=0,
  y_px=_PORTRAIT_IMAGE_TOP_PX,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX,
  height_px=_PORTRAIT_IMAGE_HEIGHT_PX,
)
_PORTRAIT_FOOTER_RECT = SceneRect(
  x_px=0,
  y_px=_PORTRAIT_IMAGE_BOTTOM_PX,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX,
  height_px=_PORTRAIT_FOOTER_HEIGHT_PX,
)
_PORTRAIT_CHARACTER_RECT = SceneRect(
  x_px=0,
  y_px=_PORTRAIT_CHARACTER_TOP_PX,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX,
  height_px=_PORTRAIT_CHARACTER_BAND_HEIGHT_PX,
)
_JOKE_AUDIO_RESPONSE_GAP_SEC = 0.8
_JOKE_AUDIO_SETUP_GAP_SEC = 0.8
_JOKE_AUDIO_PUNCHLINE_GAP_SEC = 1.0
_LISTENER_POP_IN_DELAY_AFTER_TELLER_POP_IN_END_SEC = 0.7
_VIDEO_TAIL_SEC = 2.0
_POP_IN_SEQUENCE_ID = "pop_in"
_GIGGLE_VARIANT_MIN = 1
_GIGGLE_VARIANT_MAX = 3


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


def _validate_portrait_layout() -> None:
  """Validate static portrait layout constants once at import time."""
  if _PORTRAIT_ACTUAL_BOTTOM_MARGIN_PX < _PORTRAIT_BOTTOM_SAFE_MARGIN_PX:
    raise ValueError("Portrait layout violates bottom safe margin")


_validate_portrait_layout()


def build_portrait_joke_scene_script(
  *,
  setup_image_gcs_uri: str,
  punchline_image_gcs_uri: str,
  teller_character: PosableCharacter,
  teller_voice: audio_voices.Voice,
  setup_sequence: PosableCharacterSequence,
  punchline_sequence: PosableCharacterSequence,
  listener_character: PosableCharacter | None = None,
  listener_voice: audio_voices.Voice | None = None,
  intro_sequence: PosableCharacterSequence | None = None,
  response_sequence: PosableCharacterSequence | None = None,
) -> SceneScript:
  """Build the portrait joke `SceneScript` from prebuilt character sequences."""
  pop_in_sequence = _load_sequence_from_firestore(_POP_IN_SEQUENCE_ID)
  pop_in_duration_sec = pop_in_sequence.duration_sec
  if pop_in_duration_sec <= 0:
    raise ValueError("pop_in sequence must have positive duration")

  teller_laugh_sequence = _load_random_giggle_sequence(voice=teller_voice)
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
    listener_laugh_sequence = _load_random_giggle_sequence(
      voice=listener_voice)
    listener_laugh_duration_sec = listener_laugh_sequence.duration_sec
    if listener_laugh_duration_sec <= 0:
      raise ValueError(
        f"{listener_voice.name} giggle sequence must have positive duration")

  timeline = _resolve_portrait_timeline(
    pop_in_sequence=pop_in_sequence,
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
    laugh_duration_sec=max(teller_laugh_duration_sec,
                           listener_laugh_duration_sec),
  )

  timed_images: list[TimedImage] = []
  timed_images.extend(
    _build_joke_image_items(
      setup_image_gcs_uri=setup_image_gcs_uri,
      punchline_image_gcs_uri=punchline_image_gcs_uri,
      timeline=timeline,
    ))
  timed_images.extend(_build_background_image_items(timeline=timeline))

  character_items = _build_character_dialogs(
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
    z_index=_PORTRAIT_CHARACTER_LAYER_Z_INDEX,
  )

  script = SceneScript(
    canvas=SceneCanvas(
      width_px=_PORTRAIT_VIDEO_WIDTH_PX,
      height_px=_PORTRAIT_VIDEO_HEIGHT_PX,
    ),
    items=[*timed_images, *character_items],
    duration_sec=timeline.total_duration_sec,
  )
  script.validate()
  return script


def _build_background_image_items(
  *,
  timeline: PortraitJokeTimeline,
) -> list[TimedImage]:
  """Build static portrait background layers (banner bg, logo, footer bg)."""
  return [
    _build_static_image_item(
      gcs_uri=_PORTRAIT_FOOTER_BACKGROUND_GCS_URI,
      duration_sec=timeline.total_duration_sec,
      z_index=_PORTRAIT_BANNER_BACKGROUND_Z_INDEX,
      rect=_PORTRAIT_BANNER_RECT,
      fit_mode="fill",
    ),
    _build_static_image_item(
      gcs_uri=_PORTRAIT_BANNER_GCS_URI,
      duration_sec=timeline.total_duration_sec,
      z_index=_PORTRAIT_BANNER_LOGO_Z_INDEX,
      rect=_PORTRAIT_BANNER_LOGO_RECT,
      fit_mode="contain",
    ),
    _build_static_image_item(
      gcs_uri=_PORTRAIT_FOOTER_BACKGROUND_GCS_URI,
      duration_sec=timeline.total_duration_sec,
      z_index=_PORTRAIT_FOOTER_BACKGROUND_Z_INDEX,
      rect=_PORTRAIT_FOOTER_RECT,
      fit_mode="fill",
    ),
  ]


def _build_static_image_item(
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


def _build_joke_image_items(
  *,
  setup_image_gcs_uri: str,
  punchline_image_gcs_uri: str,
  timeline: PortraitJokeTimeline,
) -> list[TimedImage]:
  """Build timed setup/punchline image items from timeline."""
  return [
    TimedImage(
      gcs_uri=setup_image_gcs_uri,
      start_time_sec=0.0,
      end_time_sec=timeline.punchline_start_sec,
      z_index=int(_PORTRAIT_IMAGE_LAYER_Z_INDEX),
      rect=_PORTRAIT_TOP_RECT,
      fit_mode="fill",
    ),
    TimedImage(
      gcs_uri=punchline_image_gcs_uri,
      start_time_sec=timeline.punchline_start_sec,
      end_time_sec=timeline.total_duration_sec,
      z_index=int(_PORTRAIT_IMAGE_LAYER_Z_INDEX),
      rect=_PORTRAIT_TOP_RECT,
      fit_mode="fill",
    ),
  ]


def _resolve_portrait_timeline(
  *,
  pop_in_sequence: PosableCharacterSequence,
  intro_sequence: PosableCharacterSequence | None,
  setup_sequence: PosableCharacterSequence,
  response_sequence: PosableCharacterSequence | None,
  punchline_sequence: PosableCharacterSequence,
  laugh_duration_sec: float,
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
    _JOKE_AUDIO_SETUP_GAP_SEC) if intro_end is not None else pop_in_end
  setup_end = setup_start + setup_duration
  response_start: float | None = None
  response_end: float | None = None
  punchline_start = setup_end + _JOKE_AUDIO_PUNCHLINE_GAP_SEC
  if response_sequence is not None:
    response_start = setup_end + _JOKE_AUDIO_RESPONSE_GAP_SEC
    response_end = response_start + response_duration
    punchline_start = response_end + _JOKE_AUDIO_PUNCHLINE_GAP_SEC
  punchline_end = punchline_start + punchline_duration
  laugh_start = punchline_end
  laugh_end = laugh_start + max(0.0, laugh_duration_sec)
  total_duration = laugh_end + _VIDEO_TAIL_SEC

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


def _build_character_dialogs(
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
      _LISTENER_POP_IN_DELAY_AFTER_TELLER_POP_IN_END_SEC)
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
  actor_rects = _build_actor_rects_for_tracks(tracks)
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


def _load_sequence_from_firestore(
    sequence_id: str) -> PosableCharacterSequence:
  """Load a required character sequence by Firestore document id."""
  sequence = firestore.get_posable_character_sequence(sequence_id)
  if sequence is None:
    raise ValueError(
      f"Missing required posable_character_sequences/{sequence_id}")
  sequence.validate()
  return sequence


def _load_random_giggle_sequence(
  *,
  voice: audio_voices.Voice,
) -> PosableCharacterSequence:
  """Load a random `voice_giggle[1-3]` sequence for the provided voice enum."""
  giggle_variant = random.randint(_GIGGLE_VARIANT_MIN, _GIGGLE_VARIANT_MAX)
  sequence_id = f"{voice.name}_giggle{giggle_variant}"
  return _load_sequence_from_firestore(sequence_id)


def _build_actor_rects_for_tracks(
  tracks: list[tuple[PosableCharacter, list[tuple[float,
                                                  PosableCharacterSequence]]]],
) -> list[SceneRect]:
  """Build actor rects with proportional horizontal allocation and bottom alignment."""
  if not tracks:
    return []

  actor_sizes: list[tuple[int, int]] = []
  for character, _dialogs in tracks:
    actor_sizes.append(
      (character.definition.width, character.definition.height))

  tallest_height = max(height for _width, height in actor_sizes)
  left_bound = int(_PORTRAIT_CHARACTER_RECT.x_px +
                   _PORTRAIT_CHARACTER_SIDE_MARGIN_PX)
  right_bound = int(_PORTRAIT_CHARACTER_RECT.x_px +
                    _PORTRAIT_CHARACTER_RECT.width_px -
                    _PORTRAIT_CHARACTER_SIDE_MARGIN_PX)
  available_width = max(1, right_bound - left_bound)
  total_width = max(1, sum(width for width, _height in actor_sizes))

  rects: list[SceneRect] = []
  cursor_x = left_bound
  for width_px, height_px in actor_sizes:
    slot_width = available_width * (width_px / total_width)
    center_x = cursor_x + (slot_width / 2.0)
    y = int(_PORTRAIT_CHARACTER_RECT.y_px + (tallest_height - height_px))
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
