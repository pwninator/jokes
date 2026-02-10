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
_PORTRAIT_IMAGE_HEIGHT_PX = 1080
_PORTRAIT_FOOTER_HEIGHT_PX = _PORTRAIT_VIDEO_HEIGHT_PX - _PORTRAIT_IMAGE_HEIGHT_PX
_PORTRAIT_TOP_RECT = SceneRect(
  x_px=0,
  y_px=0,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX,
  height_px=_PORTRAIT_IMAGE_HEIGHT_PX,
)
_PORTRAIT_FOOTER_RECT = SceneRect(
  x_px=0,
  y_px=_PORTRAIT_IMAGE_HEIGHT_PX,
  width_px=_PORTRAIT_VIDEO_WIDTH_PX,
  height_px=_PORTRAIT_FOOTER_HEIGHT_PX,
)

CharacterDialog = tuple[
  str,
  float,
  str,
  list[audio_timing.WordTiming] | None,
]
CharacterDialogTracks = list[tuple[PosableCharacter | None, list[CharacterDialog]]]
DetectMouthEventsFn = Callable[..., list[MouthEvent]]


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
    z_index=20,
  )
  image_items.append(
    TimedImage(
      gcs_uri=str(footer_background_gcs_uri),
      start_time_sec=0.0,
      end_time_sec=float(total_duration_sec),
      z_index=10,
      rect=_PORTRAIT_FOOTER_RECT,
      fit_mode="fill",
    ))

  actor_rects = _build_portrait_actor_rects(character_dialogs)
  character_items = _build_timed_character_sequence_items(
    character_dialogs,
    actor_rects=actor_rects,
    total_duration_sec=float(total_duration_sec),
    include_drumming=bool(include_drumming),
    drumming_duration_sec=float(drumming_duration_sec),
    z_index=30,
    detect_mouth_events_fn=detect_mouth_events_fn,
  )

  script = SceneScript(
    canvas=SceneCanvas(
      width_px=_PORTRAIT_VIDEO_WIDTH_PX,
      height_px=_PORTRAIT_VIDEO_HEIGHT_PX,
    ),
    items=[*image_items, *character_items],
    duration_sec=float(total_duration_sec),
  )
  script.validate()
  return script


def build_portrait_test_scene_script(
  *,
  character_dialogs: CharacterDialogTracks,
  footer_background_gcs_uri: str,
  total_duration_sec: float,
  detect_mouth_events_fn: DetectMouthEventsFn,
) -> SceneScript:
  """Build the portrait lip-sync test `SceneScript`."""
  image_items = [
    TimedImage(
      gcs_uri=str(footer_background_gcs_uri),
      start_time_sec=0.0,
      end_time_sec=float(total_duration_sec),
      z_index=10,
      rect=_PORTRAIT_FOOTER_RECT,
      fit_mode="fill",
    )
  ]
  actor_rects = _build_portrait_actor_rects(character_dialogs)
  character_items = _build_timed_character_sequence_items(
    character_dialogs,
    actor_rects=actor_rects,
    total_duration_sec=float(total_duration_sec),
    include_drumming=False,
    drumming_duration_sec=0.0,
    z_index=30,
    detect_mouth_events_fn=detect_mouth_events_fn,
  )
  script = SceneScript(
    canvas=SceneCanvas(
      width_px=_PORTRAIT_VIDEO_WIDTH_PX,
      height_px=_PORTRAIT_VIDEO_HEIGHT_PX,
    ),
    items=[*image_items, *character_items],
    duration_sec=float(total_duration_sec),
  )
  script.validate()
  return script


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

    if include_drumming and float(drumming_duration_sec) > 0:
      start = max(float(latest_actor_end),
                  float(total_duration_sec) - float(drumming_duration_sec))
      end = float(total_duration_sec)
      if end > start:
        drumming_sequence = _build_drumming_sequence(duration_sec=float(end - start))
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
      mouth_events.append(
        SequenceMouthEvent(
          start_time=float(event.start_time),
          end_time=float(event.end_time),
          mouth_state=event.mouth_shape,
        ))

  sequence = PosableCharacterSequence(
    sequence_mouth_state=mouth_events,
    sequence_sound_events=sound_events,
  )
  sequence.validate()
  return sequence


def _build_portrait_actor_rects(
  character_dialogs: CharacterDialogTracks,
) -> dict[int, SceneRect]:
  """Resolve deterministic actor rects for footer character placement."""
  actor_entries = [(index, character)
                   for index, (character, _dialogs) in enumerate(character_dialogs)
                   if character is not None]
  if not actor_entries:
    return {}

  spacing = float(_PORTRAIT_FOOTER_RECT.width_px) / float(len(actor_entries) + 1)
  actor_rects: dict[int, SceneRect] = {}
  for slot_index, (actor_index, character) in enumerate(actor_entries):
    center_x = float(_PORTRAIT_FOOTER_RECT.x_px) + (
      spacing * float(slot_index + 1))
    pose_before = character.pose_state
    try:
      character.set_pose(mouth_state=MouthState.OPEN)
      sprite = character.get_image()
    finally:
      character.pose_state = pose_before

    scale = 1.0
    if sprite.height > _PORTRAIT_FOOTER_RECT.height_px:
      scale = float(_PORTRAIT_FOOTER_RECT.height_px) / float(sprite.height)
    target_width = max(1, int(round(float(sprite.width) * float(scale))))
    target_height = max(1, int(round(float(sprite.height) * float(scale))))
    x = int(round(center_x - (float(target_width) / 2.0)))
    y = _PORTRAIT_FOOTER_RECT.y_px + int(
      round((float(_PORTRAIT_FOOTER_RECT.height_px) - float(target_height)) / 2.0))
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
    left_events.append(
      {
        "start_time": start,
        "end_time": end,
        "target_transform": {
          "translate_x": 0.0,
          "translate_y": left_y,
          "scale_x": 1.0,
          "scale_y": 1.0,
        },
      })
    right_events.append(
      {
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
    "sequence_left_hand_transform": left_events,
    "sequence_right_hand_transform": right_events,
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
  timing: list[audio_timing.WordTiming] | None,
) -> float:
  """Estimate clip duration in seconds from provider timing metadata."""
  if not timing:
    return 0.01
  latest_end = 0.0
  for word_timing in timing:
    latest_end = max(latest_end, float(word_timing.end_time))
  return max(0.01, latest_end)
