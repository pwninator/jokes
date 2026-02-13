"""Build declarative `SceneScript` objects for joke/social portrait videos."""

from __future__ import annotations

from collections.abc import Callable

from common import audio_timing
from common.mouth_events import MouthEvent
from common.posable_character import MouthState, PosableCharacter
from common.posable_character_sequence import (PosableCharacterSequence,
                                               SequenceMouthEvent,
                                               SequenceSoundEvent)
from services.video.script import (SceneCanvas, SceneRect, SceneScript,
                                   TimedCharacterSequence, TimedImage)

_PORTRAIT_VIDEO_WIDTH_PX = 1080
_PORTRAIT_VIDEO_HEIGHT_PX = 1920
_PORTRAIT_IMAGE_LAYER_Z_INDEX = 20
_PORTRAIT_CHARACTER_LAYER_Z_INDEX = 30
_PORTRAIT_BANNER_BACKGROUND_Z_INDEX = 30
_PORTRAIT_BANNER_LOGO_Z_INDEX = 40
_PORTRAIT_FOOTER_BACKGROUND_Z_INDEX = 10

_PORTRAIT_BANNER_HEIGHT_PX = 240
_PORTRAIT_BANNER_HORIZONTAL_MARGIN_PX = 80
_PORTRAIT_IMAGE_HEIGHT_PX = 1080
_PORTRAIT_CHARACTER_GAP_PX = 120
_PORTRAIT_CHARACTER_BAND_HEIGHT_PX = 300
_PORTRAIT_BOTTOM_SAFE_MARGIN_PX = 120

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
  width_px=_PORTRAIT_VIDEO_WIDTH_PX - (_PORTRAIT_BANNER_HORIZONTAL_MARGIN_PX * 2),
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
_INTRO_DIALOG_TRANSCRIPT = "hey... want to hear a joke?"

CharacterDialog = tuple[
  str,
  float,
  str,
  list[audio_timing.WordTiming] | None,
]
CharacterDialogTracks = list[tuple[PosableCharacter | None,
                                   list[CharacterDialog]]]
DetectMouthEventsFn = Callable[..., list[MouthEvent]]


def _validate_portrait_layout() -> None:
  """Validate static portrait layout constants once at import time."""
  if _PORTRAIT_ACTUAL_BOTTOM_MARGIN_PX < _PORTRAIT_BOTTOM_SAFE_MARGIN_PX:
    raise ValueError("Portrait layout violates bottom safe margin")


_validate_portrait_layout()


def build_portrait_joke_scene_script(
  *,
  joke_images: list[tuple[str, float]],
  character_dialogs: CharacterDialogTracks,
  footer_background_gcs_uri: str,
  total_duration_sec: float,
  detect_mouth_events_fn: DetectMouthEventsFn,
  include_drumming: bool = True,
  drumming_duration_sec: float = 2.0,
) -> SceneScript:
  """Build the portrait joke `SceneScript` with timed images and characters."""
  image_items = _build_timed_image_items(
    joke_images,
    total_duration_sec=float(total_duration_sec),
    rect=_PORTRAIT_TOP_RECT,
    fit_mode="fill",
    z_index=_PORTRAIT_IMAGE_LAYER_Z_INDEX,
  )
  image_items.extend(
    _build_portrait_background_image_items(
      footer_background_gcs_uri=str(footer_background_gcs_uri),
      total_duration_sec=float(total_duration_sec),
    ))
  return _build_portrait_scene_script(
    image_items=image_items,
    character_dialogs=character_dialogs,
    duration_sec=float(total_duration_sec),
    include_drumming=bool(include_drumming),
    drumming_duration_sec=float(drumming_duration_sec),
    detect_mouth_events_fn=detect_mouth_events_fn,
  )


def _build_portrait_scene_script(
  *,
  image_items: list[TimedImage],
  character_dialogs: CharacterDialogTracks,
  duration_sec: float,
  include_drumming: bool,
  drumming_duration_sec: float,
  detect_mouth_events_fn: DetectMouthEventsFn,
) -> SceneScript:
  """Build a portrait script by composing image and character layers."""
  actor_rects = _build_portrait_actor_rects(character_dialogs)
  character_items = _build_timed_character_sequence_items(
    character_dialogs,
    actor_rects=actor_rects,
    total_duration_sec=float(duration_sec),
    include_drumming=bool(include_drumming),
    drumming_duration_sec=float(drumming_duration_sec),
    z_index=_PORTRAIT_CHARACTER_LAYER_Z_INDEX,
    detect_mouth_events_fn=detect_mouth_events_fn,
  )
  script = SceneScript(
    canvas=SceneCanvas(
      width_px=_PORTRAIT_VIDEO_WIDTH_PX,
      height_px=_PORTRAIT_VIDEO_HEIGHT_PX,
    ),
    items=[*image_items, *character_items],
    duration_sec=float(duration_sec),
  )
  script.validate()
  return script


def _build_portrait_background_image_items(
  *,
  footer_background_gcs_uri: str,
  total_duration_sec: float,
) -> list[TimedImage]:
  """Build static portrait background layers (banner bg, logo, footer bg)."""
  return [
    _build_static_image_item(
      gcs_uri=str(footer_background_gcs_uri),
      duration_sec=float(total_duration_sec),
      z_index=_PORTRAIT_BANNER_BACKGROUND_Z_INDEX,
      rect=_PORTRAIT_BANNER_RECT,
      fit_mode="fill",
    ),
    _build_static_image_item(
      gcs_uri=_PORTRAIT_BANNER_GCS_URI,
      duration_sec=float(total_duration_sec),
      z_index=_PORTRAIT_BANNER_LOGO_Z_INDEX,
      rect=_PORTRAIT_BANNER_LOGO_RECT,
      fit_mode="contain",
    ),
    _build_static_image_item(
      gcs_uri=str(footer_background_gcs_uri),
      duration_sec=float(total_duration_sec),
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
  fit_mode: str,
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


def _build_timed_image_items(
  images: list[tuple[str, float]],
  *,
  total_duration_sec: float,
  rect: SceneRect,
  fit_mode: str,
  z_index: int,
) -> list[TimedImage]:
  """Convert ordered image starts into timed image items."""
  items: list[TimedImage] = []
  for index, (gcs_uri, start_time) in enumerate(images):
    end_time = float(total_duration_sec)
    if index < len(images) - 1:
      end_time = float(images[index + 1][1])
    items.append(
      TimedImage(
        gcs_uri=str(gcs_uri),
        start_time_sec=float(start_time),
        end_time_sec=float(end_time),
        z_index=int(z_index),
        rect=rect,
        fit_mode=fit_mode,
      ))
  return items


def _build_timed_character_sequence_items(
  character_dialogs: CharacterDialogTracks,
  *,
  actor_rects: dict[int, SceneRect],
  total_duration_sec: float,
  include_drumming: bool,
  drumming_duration_sec: float,
  z_index: int,
  detect_mouth_events_fn: DetectMouthEventsFn,
) -> list[TimedCharacterSequence]:
  """Compile dialog clips into timed character sequence items."""
  items: list[TimedCharacterSequence] = []
  intro_drumming_window = (_resolve_intro_drumming_window(character_dialogs)
                           if include_drumming else None)
  for actor_index, (character, dialogs) in enumerate(character_dialogs):
    if character is None:
      continue
    actor_id = f"actor_{actor_index}"
    actor_rect = actor_rects[actor_index]
    latest_actor_end = 0.0
    for gcs_uri, start_time, transcript, timing in dialogs:
      sequence = _build_lipsync_sequence_for_dialog(
        audio_gcs_uri=str(gcs_uri),
        transcript=str(transcript),
        timing=timing,
        detect_mouth_events_fn=detect_mouth_events_fn,
      )
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
      latest_actor_end = max(latest_actor_end,
                             float(start_time) + float(duration_sec))

    if intro_drumming_window is not None:
      intro_start, intro_end = intro_drumming_window
      if float(intro_end) > float(intro_start):
        intro_drumming_sequence = _build_drumming_sequence(
          duration_sec=float(intro_end) - float(intro_start))
        items.append(
          TimedCharacterSequence(
            actor_id=actor_id,
            character=character,
            sequence=intro_drumming_sequence,
            start_time_sec=float(intro_start),
            end_time_sec=float(intro_end),
            z_index=int(z_index),
            rect=actor_rect,
            fit_mode="contain",
          ))

    if include_drumming and float(drumming_duration_sec) > 0:
      start = max(float(latest_actor_end),
                  float(total_duration_sec) - float(drumming_duration_sec))
      end = float(total_duration_sec)
      if end > start:
        drumming_sequence = _build_drumming_sequence(duration_sec=float(end -
                                                                        start))
        items.append(
          TimedCharacterSequence(
            actor_id=actor_id,
            character=character,
            sequence=drumming_sequence,
            start_time_sec=float(start),
            end_time_sec=float(end),
            z_index=int(z_index),
            rect=actor_rect,
            fit_mode="contain",
          ))

  return items


def _resolve_intro_drumming_window(
  character_dialogs: CharacterDialogTracks, ) -> tuple[float, float] | None:
  """Return the `[start, end)` window between intro and setup line, if present."""
  intro_token = _normalize_dialog_transcript(_INTRO_DIALOG_TRANSCRIPT)
  for _character, dialogs in character_dialogs:
    if len(dialogs) < 2:
      continue
    for index in range(len(dialogs) - 1):
      _intro_gcs_uri, intro_start, intro_transcript, intro_timing = dialogs[
        index]
      _setup_gcs_uri, setup_start, _setup_transcript, _setup_timing = dialogs[
        index + 1]
      if _normalize_dialog_transcript(intro_transcript) != intro_token:
        continue
      intro_end = float(intro_start) + _estimate_dialog_duration_sec(
        intro_timing)
      if float(setup_start) > float(intro_end):
        return float(intro_end), float(setup_start)
  return None


def _normalize_dialog_transcript(transcript: str) -> str:
  letters = [ch for ch in str(transcript).lower() if ch.isalnum()]
  return "".join(letters)


def _build_lipsync_sequence_for_dialog(
  *,
  audio_gcs_uri: str,
  transcript: str,
  timing: list[audio_timing.WordTiming] | None,
  detect_mouth_events_fn: DetectMouthEventsFn,
) -> PosableCharacterSequence:
  """Build a single-dialog sequence with local-time mouth and sound events."""
  sound_end = _estimate_dialog_duration_sec(timing)
  sound_events = [
    SequenceSoundEvent(
      start_time=0.0,
      end_time=float(sound_end),
      gcs_uri=str(audio_gcs_uri),
      volume=1.0,
    )
  ]

  mouth_events: list[SequenceMouthEvent] = []
  if timing:
    detected_events = detect_mouth_events_fn(
      b"",
      mode="timing",
      transcript=str(transcript),
      timing=timing,
    )
    for event in detected_events:
      start_time = max(0.0, float(event.start_time))
      end_time = min(float(sound_end), float(event.end_time))
      if end_time <= start_time:
        continue
      mouth_events.append(
        SequenceMouthEvent(
          start_time=start_time,
          end_time=end_time,
          mouth_state=event.mouth_shape,
        ))

  sequence = PosableCharacterSequence(
    sequence_mouth_state=mouth_events,
    sequence_sound_events=sound_events,
  )
  sequence.validate()
  return sequence


def _build_portrait_actor_rects(
  character_dialogs: CharacterDialogTracks, ) -> dict[int, SceneRect]:
  """Resolve deterministic actor rects for footer character placement."""
  actor_entries = [(index, character)
                   for index, (character,
                               _dialogs) in enumerate(character_dialogs)
                   if character is not None]
  if not actor_entries:
    return {}

  spacing = float(
    _PORTRAIT_CHARACTER_RECT.width_px) / float(len(actor_entries) + 1)
  actor_rects: dict[int, SceneRect] = {}
  for slot_index, (actor_index, character) in enumerate(actor_entries):
    center_x = float(
      _PORTRAIT_CHARACTER_RECT.x_px) + (spacing * float(slot_index + 1))
    pose_before = character.pose_state
    try:
      character.set_pose(mouth_state=MouthState.OPEN)
      sprite = character.get_image()
    finally:
      character.pose_state = pose_before

    scale = 1.0
    if sprite.height > _PORTRAIT_CHARACTER_RECT.height_px:
      scale = float(_PORTRAIT_CHARACTER_RECT.height_px) / float(sprite.height)
    target_width = max(1, int(round(float(sprite.width) * float(scale))))
    target_height = max(1, int(round(float(sprite.height) * float(scale))))
    x = int(round(center_x - (float(target_width) / 2.0)))
    # Keep the top of each character aligned to a fixed offset below the image.
    y = int(_PORTRAIT_CHARACTER_RECT.y_px)
    actor_rects[actor_index] = SceneRect(
      x_px=x,
      y_px=y,
      width_px=target_width,
      height_px=target_height,
    )
  return actor_rects


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


def _estimate_dialog_duration_sec(
  timing: list[audio_timing.WordTiming] | None, ) -> float:
  """Estimate clip duration in seconds from provider timing metadata."""
  if not timing:
    return 0.01
  latest_end = 0.0
  for word_timing in timing:
    latest_end = max(latest_end, float(word_timing.end_time))
  return max(0.01, latest_end)
