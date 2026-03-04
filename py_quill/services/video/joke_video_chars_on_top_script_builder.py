"""Build declarative `SceneScript` objects for portrait joke videos.

This variant positions characters above the joke image area.
"""

# pylint: disable=duplicate-code

from __future__ import annotations

import dataclasses

from common.posable_character import PosableCharacter
from common.posable_character_sequence import PosableCharacterSequence
from services import audio_voices
from services.video import script_utils
from services.video.script import (SceneCanvas, SceneRect, SceneScript,
                                   TimedCharacterSequence, TimedImage)
from services.video.script_utils import PortraitJokeTimeline

_CANVAS_WIDTH_PX = 1080
_CANVAS_HEIGHT_PX = 1920

_TOP_MARGIN_PX = 140
_SUBTITLE_HEIGHT_PX = 100
_CHARACTER_HEIGHT_PX = 360
_JOKE_IMAGE_HEIGHT_PX = 1080
_BOTTOM_MARGIN_PX = 240

_CHARACTER_MASK_FROM_BOTTOM_PX = 50

_CONTENT_HORIZONTAL_MARGIN_PX = 80
_CONTENT_WIDTH_PX = _CANVAS_WIDTH_PX - (_CONTENT_HORIZONTAL_MARGIN_PX * 2)

_BANNER_HEIGHT_PX = _TOP_MARGIN_PX // 2

_SUBTITLE_TOP_PX = _TOP_MARGIN_PX
_CHARACTER_TOP_PX = _SUBTITLE_TOP_PX + _SUBTITLE_HEIGHT_PX
_JOKE_IMAGE_TOP_PX = _CHARACTER_TOP_PX + _CHARACTER_HEIGHT_PX

_BACKGROUND_Z_INDEX = 0
_BANNER_LOGO_Z_INDEX = 10
_JOKE_IMAGE_LAYER_Z_INDEX = 20
_CHARACTER_LAYER_Z_INDEX = 30

_BACKGROUND_GCS_URI = (
  "gs://images.quillsstorybook.com/_joke_assets/blank_paper.png")
_PORTRAIT_BANNER_GCS_URI = (
  "gs://images.quillsstorybook.com/_joke_assets/logos/icon_words_transparent_light.png"
)

_CANVAS_RECT = SceneRect(
  x_px=0,
  y_px=0,
  width_px=_CANVAS_WIDTH_PX,
  height_px=_CANVAS_HEIGHT_PX,
)
_BANNER_LOGO_RECT = SceneRect(
  x_px=_CONTENT_HORIZONTAL_MARGIN_PX,
  y_px=(_TOP_MARGIN_PX - _BANNER_HEIGHT_PX) // 2,
  width_px=_CONTENT_WIDTH_PX,
  height_px=_BANNER_HEIGHT_PX,
)
_SUBTITLE_RECT = SceneRect(
  x_px=_CONTENT_HORIZONTAL_MARGIN_PX,
  y_px=_SUBTITLE_TOP_PX,
  width_px=_CONTENT_WIDTH_PX,
  height_px=_SUBTITLE_HEIGHT_PX,
)
_CHARACTER_RECT = SceneRect(
  x_px=0,
  # This will be adjusted by _align_character_mask_tops_to_image_top
  y_px=_CHARACTER_TOP_PX,
  width_px=_CANVAS_WIDTH_PX,
  height_px=_CHARACTER_HEIGHT_PX + _CHARACTER_MASK_FROM_BOTTOM_PX,
)
_JOKE_IMAGE_RECT = SceneRect(
  x_px=0,
  y_px=_JOKE_IMAGE_TOP_PX,
  width_px=_CANVAS_WIDTH_PX,
  height_px=_JOKE_IMAGE_HEIGHT_PX,
)


def build_script(
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
  """Build the chars-on-top portrait joke `SceneScript`."""
  timeline, character_items = script_utils.build_portrait_timeline_and_character_items(
    teller_character=teller_character,
    teller_voice=teller_voice,
    setup_sequence=setup_sequence,
    punchline_sequence=punchline_sequence,
    z_index=_CHARACTER_LAYER_Z_INDEX,
    actor_band_rect=_CHARACTER_RECT,
    actor_side_margin_px=_CONTENT_HORIZONTAL_MARGIN_PX,
    listener_character=listener_character,
    listener_voice=listener_voice,
    intro_sequence=intro_sequence,
    response_sequence=response_sequence,
    extend_first_sequence=True,
    surface_line_visible=False,
  )

  timed_images: list[TimedImage] = []
  timed_images.extend(
    _build_joke_image_items(
      setup_image_gcs_uri=setup_image_gcs_uri,
      punchline_image_gcs_uri=punchline_image_gcs_uri,
      timeline=timeline,
    ))
  timed_images.extend(_build_background_image_items(timeline=timeline))

  character_items = _align_character_mask_tops_to_image_top(character_items)

  script = SceneScript(
    canvas=SceneCanvas(
      width_px=_CANVAS_WIDTH_PX,
      height_px=_CANVAS_HEIGHT_PX,
    ),
    items=[*timed_images, *character_items],
    duration_sec=timeline.total_duration_sec,
    subtitle_rect=_SUBTITLE_RECT,
  )
  script.validate()
  return script


def _align_character_mask_tops_to_image_top(
  items: list[TimedCharacterSequence], ) -> list[TimedCharacterSequence]:
  """Shift actor rects so each mask top aligns with the joke image top edge."""
  if not items:
    return items

  actor_rects: dict[str, SceneRect] = {}
  for item in items:
    rect = item.rect
    actor_rects[item.actor_id] = SceneRect(
      x_px=rect.x_px,
      y_px=_JOKE_IMAGE_TOP_PX - rect.height_px +
      _CHARACTER_MASK_FROM_BOTTOM_PX,
      width_px=rect.width_px,
      height_px=rect.height_px,
    )

  return [
    dataclasses.replace(item, rect=actor_rects[item.actor_id])
    for item in items
  ]


def _build_background_image_items(
  *,
  timeline: PortraitJokeTimeline,
) -> list[TimedImage]:
  """Build static portrait background layers (banner bg, logo, footer bg)."""
  return [
    script_utils.build_static_image_item(
      gcs_uri=_BACKGROUND_GCS_URI,
      duration_sec=timeline.total_duration_sec,
      z_index=_BACKGROUND_Z_INDEX,
      rect=_CANVAS_RECT,
      fit_mode="fill",
    ),
    script_utils.build_static_image_item(
      gcs_uri=_PORTRAIT_BANNER_GCS_URI,
      duration_sec=timeline.total_duration_sec,
      z_index=_BANNER_LOGO_Z_INDEX,
      rect=_BANNER_LOGO_RECT,
      fit_mode="contain",
    ),
  ]


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
      z_index=_JOKE_IMAGE_LAYER_Z_INDEX,
      rect=_JOKE_IMAGE_RECT,
      fit_mode="fill",
    ),
    TimedImage(
      gcs_uri=punchline_image_gcs_uri,
      start_time_sec=timeline.punchline_start_sec,
      end_time_sec=timeline.total_duration_sec,
      z_index=_JOKE_IMAGE_LAYER_Z_INDEX,
      rect=_JOKE_IMAGE_RECT,
      fit_mode="fill",
    ),
  ]
