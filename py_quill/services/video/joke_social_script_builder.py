"""Build declarative `SceneScript` objects for joke/social portrait videos."""

from __future__ import annotations

from dataclasses import dataclass

from common.posable_character import PosableCharacter
from common.posable_character_sequence import PosableCharacterSequence
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
_VIDEO_TAIL_SEC = 2.0


@dataclass(frozen=True)
class PortraitJokeTimeline:
  """Resolved timeline for a portrait joke scene."""

  intro_start_sec: float | None
  intro_end_sec: float | None
  setup_start_sec: float
  setup_end_sec: float
  response_start_sec: float | None
  response_end_sec: float | None
  punchline_start_sec: float
  punchline_end_sec: float
  intro_drumming_start_sec: float | None
  intro_drumming_end_sec: float | None
  tail_drumming_start_sec: float | None
  tail_drumming_end_sec: float | None
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
  setup_sequence: PosableCharacterSequence,
  punchline_sequence: PosableCharacterSequence,
  listener_character: PosableCharacter | None = None,
  intro_sequence: PosableCharacterSequence | None = None,
  response_sequence: PosableCharacterSequence | None = None,
  drumming_duration_sec: float = 2.0,
) -> SceneScript:
  """Build the portrait joke `SceneScript` from prebuilt character sequences."""
  timeline = _resolve_portrait_timeline(
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
    drumming_duration_sec=drumming_duration_sec,
  )

  timed_images: list[TimedImage] = []
  timed_images.extend(
    _build_joke_image_items(
      setup_image_gcs_uri=str(setup_image_gcs_uri),
      punchline_image_gcs_uri=str(punchline_image_gcs_uri),
      timeline=timeline,
    ))
  timed_images.extend(_build_background_image_items(timeline=timeline))

  character_items = _build_character_dialogs(
    teller_character=teller_character,
    listener_character=listener_character,
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
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
    gcs_uri=str(gcs_uri),
    start_time_sec=0.0,
    end_time_sec=float(duration_sec),
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
      gcs_uri=str(setup_image_gcs_uri),
      start_time_sec=0.0,
      end_time_sec=float(timeline.punchline_start_sec),
      z_index=int(_PORTRAIT_IMAGE_LAYER_Z_INDEX),
      rect=_PORTRAIT_TOP_RECT,
      fit_mode="fill",
    ),
    TimedImage(
      gcs_uri=str(punchline_image_gcs_uri),
      start_time_sec=float(timeline.punchline_start_sec),
      end_time_sec=float(timeline.total_duration_sec),
      z_index=int(_PORTRAIT_IMAGE_LAYER_Z_INDEX),
      rect=_PORTRAIT_TOP_RECT,
      fit_mode="fill",
    ),
  ]


def _resolve_portrait_timeline(
  *,
  intro_sequence: PosableCharacterSequence | None,
  setup_sequence: PosableCharacterSequence,
  response_sequence: PosableCharacterSequence | None,
  punchline_sequence: PosableCharacterSequence,
  drumming_duration_sec: float,
) -> PortraitJokeTimeline:
  """Resolve all key script timestamps, including drumming windows."""
  intro_start: float | None = None
  intro_end: float | None = None
  intro_duration = _sequence_duration_sec(
    intro_sequence) if intro_sequence is not None else 0.0
  if intro_sequence is not None:
    intro_start = 0.0
    intro_end = float(intro_duration)
  setup_duration = _sequence_duration_sec(setup_sequence)
  response_duration = _sequence_duration_sec(
    response_sequence) if response_sequence is not None else 0.0
  punchline_duration = _sequence_duration_sec(punchline_sequence)

  setup_start = float(intro_duration + _JOKE_AUDIO_SETUP_GAP_SEC
                      if intro_sequence is not None else intro_duration)
  setup_end = float(setup_start + setup_duration)
  response_start: float | None = None
  response_end: float | None = None
  punchline_start = float(setup_end + _JOKE_AUDIO_PUNCHLINE_GAP_SEC)
  if response_sequence is not None:
    response_start = float(setup_end + _JOKE_AUDIO_RESPONSE_GAP_SEC)
    response_end = float(response_start + response_duration)
    punchline_start = float(response_end + _JOKE_AUDIO_PUNCHLINE_GAP_SEC)
  punchline_end = float(punchline_start + punchline_duration)
  total_duration = float(punchline_end + _VIDEO_TAIL_SEC)

  intro_drum_start: float | None = None
  intro_drum_end: float | None = None
  if (intro_start is not None and intro_end is not None
      and setup_start > intro_end):
    intro_drum_start = float(intro_end)
    intro_drum_end = float(setup_start)

  tail_drum_start: float | None = None
  tail_drum_end: float | None = None
  if float(drumming_duration_sec) > 0:
    tail_drum_start = max(float(punchline_end),
                          float(total_duration) - float(drumming_duration_sec))
    tail_drum_end = float(total_duration)

  return PortraitJokeTimeline(
    intro_start_sec=intro_start,
    intro_end_sec=intro_end,
    setup_start_sec=float(setup_start),
    setup_end_sec=float(setup_end),
    response_start_sec=float(response_start)
    if response_start is not None else None,
    response_end_sec=float(response_end) if response_end is not None else None,
    punchline_start_sec=float(punchline_start),
    punchline_end_sec=float(punchline_end),
    intro_drumming_start_sec=intro_drum_start,
    intro_drumming_end_sec=intro_drum_end,
    tail_drumming_start_sec=tail_drum_start,
    tail_drumming_end_sec=tail_drum_end,
    total_duration_sec=float(total_duration),
  )


def _build_character_dialogs(
  *,
  teller_character: PosableCharacter,
  listener_character: PosableCharacter | None,
  intro_sequence: PosableCharacterSequence | None,
  setup_sequence: PosableCharacterSequence,
  response_sequence: PosableCharacterSequence | None,
  punchline_sequence: PosableCharacterSequence,
  timeline: PortraitJokeTimeline,
  z_index: int,
) -> list[TimedCharacterSequence]:
  """Build timed character sequence items for teller/listener tracks."""
  tracks: list[tuple[PosableCharacter,
                     list[tuple[float, PosableCharacterSequence]]]] = []

  teller_dialogs: list[tuple[float, PosableCharacterSequence]] = []
  if intro_sequence is not None:
    teller_dialogs.append((0.0, intro_sequence))
  teller_dialogs.extend([
    (float(timeline.setup_start_sec), setup_sequence),
    (float(timeline.punchline_start_sec), punchline_sequence),
  ])
  tracks.append((teller_character, teller_dialogs))

  if listener_character and response_sequence and timeline.response_start_sec:
    listener_dialogs = [(timeline.response_start_sec, response_sequence)]
    tracks.append((listener_character, listener_dialogs))

  items: list[TimedCharacterSequence] = []
  actor_rects = _build_actor_rects_for_tracks(tracks)
  for actor_index, (character, dialogs) in enumerate(tracks):
    actor_id = f"actor_{actor_index}"
    actor_rect = actor_rects[actor_index]
    for start_time, sequence in dialogs:
      duration_sec = _sequence_duration_sec(sequence)
      items.append(
        TimedCharacterSequence(
          actor_id=actor_id,
          character=character,
          sequence=sequence,
          start_time_sec=float(start_time),
          end_time_sec=float(start_time) + float(duration_sec),
          z_index=int(z_index),
          rect=actor_rect,
          fit_mode="contain",
        ))

    if (timeline.intro_drumming_start_sec is not None
        and timeline.intro_drumming_end_sec is not None and
        timeline.intro_drumming_end_sec > timeline.intro_drumming_start_sec):
      intro_drumming_sequence = _build_drumming_sequence(
        duration_sec=float(timeline.intro_drumming_end_sec) -
        float(timeline.intro_drumming_start_sec))
      items.append(
        TimedCharacterSequence(
          actor_id=actor_id,
          character=character,
          sequence=intro_drumming_sequence,
          start_time_sec=float(timeline.intro_drumming_start_sec),
          end_time_sec=float(timeline.intro_drumming_end_sec),
          z_index=int(z_index),
          rect=actor_rect,
          fit_mode="contain",
        ))

    if (timeline.tail_drumming_start_sec is not None
        and timeline.tail_drumming_end_sec is not None
        and timeline.tail_drumming_end_sec > timeline.tail_drumming_start_sec):
      tail_drumming_sequence = _build_drumming_sequence(
        duration_sec=float(timeline.tail_drumming_end_sec) -
        float(timeline.tail_drumming_start_sec))
      items.append(
        TimedCharacterSequence(
          actor_id=actor_id,
          character=character,
          sequence=tail_drumming_sequence,
          start_time_sec=float(timeline.tail_drumming_start_sec),
          end_time_sec=float(timeline.tail_drumming_end_sec),
          z_index=int(z_index),
          rect=actor_rect,
          fit_mode="contain",
        ))

  return items


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
  cursor_x = float(left_bound)
  for width_px, height_px in actor_sizes:
    slot_width = float(available_width) * (float(width_px) /
                                           float(total_width))
    center_x = cursor_x + (slot_width / 2.0)
    y = int(_PORTRAIT_CHARACTER_RECT.y_px + (tallest_height - height_px))
    x = int(round(float(center_x) - (float(width_px) / 2.0)))
    rects.append(
      SceneRect(
        x_px=x,
        y_px=int(y),
        width_px=int(width_px),
        height_px=int(height_px),
      ))
    cursor_x += slot_width
  return rects


def _build_drumming_sequence(
  *,
  duration_sec: float,
  step_sec: float = 0.10,
  amplitude_px: float = 10.0,
) -> PosableCharacterSequence:
  """Build a deterministic hand-drumming sequence."""
  duration_sec = max(0.0, float(duration_sec))
  step_sec = max(0.02, float(step_sec))
  amplitude_px = float(amplitude_px)

  left_events = []
  right_events = []
  t = 0.0
  idx = 0
  while t < duration_sec:
    start = float(t)
    end = min(float(duration_sec), start + float(step_sec))
    if end <= start:
      break
    left_y = -amplitude_px if idx % 2 == 0 else amplitude_px
    right_y = amplitude_px if idx % 2 == 0 else -amplitude_px
    left_events.append({
      "start_time": start,
      "end_time": end,
      "target_transform": {
        "translate_x": 0.0,
        "translate_y": left_y,
        "scale_x": 1.0,
        "scale_y": 1.0,
      },
    })
    right_events.append({
      "start_time": start,
      "end_time": end,
      "target_transform": {
        "translate_x": 0.0,
        "translate_y": right_y,
        "scale_x": 1.0,
        "scale_y": 1.0,
      },
    })
    t = end
    idx += 1

  sequence = PosableCharacterSequence.from_dict({
    "sequence_left_hand_transform":
    left_events,
    "sequence_right_hand_transform":
    right_events,
  })
  sequence.validate()
  return sequence


def _sequence_duration_sec(sequence: PosableCharacterSequence) -> float:
  """Return max end time across all sequence tracks."""
  max_end = 0.0
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
    for event in track:
      max_end = max(max_end, float(event.end_time))
  return max_end
