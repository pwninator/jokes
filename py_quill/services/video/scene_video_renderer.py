"""Generic scene video renderer driven by `SceneScript`."""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass

import numpy as np
from common import models
from common.character_animator import CharacterAnimator
from common.posable_character import PosableCharacter
from common.posable_character_sequence import PosableCharacterSequence
from moviepy import AudioFileClip, CompositeAudioClip, VideoClip
from PIL import Image, ImageOps
from services import cloud_storage
from services.video.script import (SceneCanvas, SceneRect, SceneScript,
                                   TimedCharacterSequence, TimedImage)

_DEFAULT_VIDEO_FPS = 24


@dataclass(frozen=True)
class _PreparedImage:
  source_order: int
  start_time_sec: float
  end_time_sec: float
  z_index: int
  sprite: Image.Image
  paste_position: tuple[int, int]


@dataclass(frozen=True)
class _ActorRender:
  actor_id: str
  source_order: int
  character: PosableCharacter
  animator: CharacterAnimator
  z_index: int
  rect: SceneRect
  fit_mode: str


def _render_with_fit(
  image: Image.Image,
  *,
  rect: SceneRect,
  fit_mode: str,
  allow_upscale: bool,
) -> tuple[Image.Image, int, int]:
  source = image.convert("RGBA")
  rect_x = int(rect.x_px)
  rect_y = int(rect.y_px)
  rect_width = int(rect.width_px)
  rect_height = int(rect.height_px)

  if fit_mode == "fill":
    fitted = source.resize((rect_width, rect_height),
                           resample=Image.Resampling.LANCZOS)
    return fitted, rect_x, rect_y

  if fit_mode == "cover":
    fitted = ImageOps.fit(
      source,
      (rect_width, rect_height),
      method=Image.Resampling.LANCZOS,
    )
    return fitted, rect_x, rect_y

  # contain (default)
  width_scale = rect_width / float(source.width)
  height_scale = rect_height / float(source.height)
  scale = min(width_scale, height_scale)
  if not allow_upscale:
    scale = min(1.0, scale)
  target_width = max(1, int(round(source.width * scale)))
  target_height = max(1, int(round(source.height * scale)))
  fitted = source
  if (target_width, target_height) != source.size:
    fitted = source.resize((target_width, target_height),
                           resample=Image.Resampling.LANCZOS)
  x = rect_x + int(round((rect_width - target_width) / 2.0))
  y = rect_y + int(round((rect_height - target_height) / 2.0))
  return fitted, x, y


def _prepare_images(script: SceneScript) -> list[_PreparedImage]:
  prepared: list[_PreparedImage] = []
  for index, item in enumerate(script.items):
    if not isinstance(item, TimedImage):
      continue
    source = cloud_storage.download_image_from_gcs(item.gcs_uri).convert("RGBA")
    sprite, x, y = _render_with_fit(
      source,
      rect=item.rect,
      fit_mode=item.fit_mode,
      allow_upscale=True,
    )
    prepared.append(
      _PreparedImage(
        source_order=int(index),
        start_time_sec=float(item.start_time_sec),
        end_time_sec=float(item.end_time_sec),
        z_index=int(item.z_index),
        sprite=sprite,
        paste_position=(x, y),
      ))
  prepared.sort(key=lambda entry: (int(entry.z_index), int(entry.source_order)))
  return prepared


def _prepare_actor_renders(script: SceneScript) -> list[_ActorRender]:
  by_actor: dict[str, dict[str, object]] = {}
  for index, item in enumerate(script.items):
    if isinstance(item, TimedCharacterSequence):
      actor_entry = by_actor.setdefault(
        item.actor_id, {
          "source_order": int(index),
          "items": [],
        })
      actor_entry["source_order"] = min(
        int(actor_entry["source_order"]), int(index))
      actor_entry["items"].append(item)

  renders: list[_ActorRender] = []
  for actor_id, actor_entry in by_actor.items():
    items = sorted(actor_entry["items"], key=lambda entry: entry.start_time_sec)
    character = items[0].character
    z_index = int(items[0].z_index)
    rect = items[0].rect
    fit_mode = items[0].fit_mode
    sequence = _merge_shifted_sequences(items)
    animator = CharacterAnimator(sequence)
    renders.append(
      _ActorRender(
        actor_id=actor_id,
        source_order=int(actor_entry["source_order"]),
        character=character,
        animator=animator,
        z_index=z_index,
        rect=rect,
        fit_mode=fit_mode,
      ))
  renders.sort(key=lambda entry: (int(entry.z_index), int(entry.source_order)))
  return renders


def _merge_shifted_sequences(
  items: list[TimedCharacterSequence],
) -> PosableCharacterSequence:
  """Merge local-time sequence clips into one absolute-time sequence."""
  out = PosableCharacterSequence()
  for item in items:
    offset = float(item.start_time_sec)
    sequence = item.sequence
    out.sequence_left_eye_open.extend(
      _shift_boolean_events(sequence.sequence_left_eye_open, offset))
    out.sequence_right_eye_open.extend(
      _shift_boolean_events(sequence.sequence_right_eye_open, offset))
    out.sequence_mouth_state.extend(
      _shift_mouth_events(sequence.sequence_mouth_state, offset))
    out.sequence_left_hand_visible.extend(
      _shift_boolean_events(sequence.sequence_left_hand_visible, offset))
    out.sequence_right_hand_visible.extend(
      _shift_boolean_events(sequence.sequence_right_hand_visible, offset))
    out.sequence_left_hand_transform.extend(
      _shift_transform_events(sequence.sequence_left_hand_transform, offset))
    out.sequence_right_hand_transform.extend(
      _shift_transform_events(sequence.sequence_right_hand_transform, offset))
    out.sequence_head_transform.extend(
      _shift_transform_events(sequence.sequence_head_transform, offset))
    out.sequence_sound_events.extend(
      _shift_sound_events(sequence.sequence_sound_events, offset))

  out.validate()
  return out


def _shift_boolean_events(events, offset: float):
  return [event.__class__(
    start_time=float(event.start_time) + float(offset),
    end_time=float(event.end_time) + float(offset),
    value=bool(event.value),
  ) for event in events]


def _shift_mouth_events(events, offset: float):
  return [event.__class__(
    start_time=float(event.start_time) + float(offset),
    end_time=float(event.end_time) + float(offset),
    mouth_state=event.mouth_state,
  ) for event in events]


def _shift_transform_events(events, offset: float):
  return [event.__class__(
    start_time=float(event.start_time) + float(offset),
    end_time=float(event.end_time) + float(offset),
    target_transform=event.target_transform,
  ) for event in events]


def _shift_sound_events(events, offset: float):
  return [event.__class__(
    start_time=float(event.start_time) + float(offset),
    end_time=float(event.end_time) + float(offset),
    gcs_uri=event.gcs_uri,
    volume=float(event.volume),
  ) for event in events]


def _render_scene_frame(
  *,
  time_sec: float,
  canvas: SceneCanvas,
  prepared_images: list[_PreparedImage],
  actor_renders: list[_ActorRender],
) -> np.ndarray:
  base = Image.new("RGBA", (int(canvas.width_px), int(canvas.height_px)),
                   tuple(canvas.background_rgba))

  image_index = 0
  actor_index = 0
  while image_index < len(prepared_images) or actor_index < len(actor_renders):
    render_image = actor_index >= len(actor_renders)
    if image_index < len(prepared_images) and actor_index < len(actor_renders):
      image_key = (
        int(prepared_images[image_index].z_index),
        int(prepared_images[image_index].source_order),
      )
      actor_key = (
        int(actor_renders[actor_index].z_index),
        int(actor_renders[actor_index].source_order),
      )
      render_image = image_key <= actor_key

    if render_image:
      image = prepared_images[image_index]
      image_index += 1
      if not (float(image.start_time_sec) <= float(time_sec) < float(
          image.end_time_sec)):
        continue
      x, y = image.paste_position
      base.paste(image.sprite, (x, y), image.sprite)
      continue

    render = actor_renders[actor_index]
    actor_index += 1
    pose = render.animator.sample_pose(float(time_sec))
    render.character.apply_pose_state(pose)
    sprite = render.character.get_image()
    fitted, x, y = _render_with_fit(
      sprite,
      rect=render.rect,
      fit_mode=render.fit_mode,
      allow_upscale=False,
    )
    base.paste(fitted, (x, y), fitted)

  return np.asarray(base.convert("RGB"))


def _extract_audio_schedule(
  script: SceneScript, ) -> list[tuple[str, float, float]]:
  schedule: list[tuple[str, float, float]] = []
  for item in script.items:
    if not isinstance(item, TimedCharacterSequence):
      continue
    for event in item.sequence.sequence_sound_events:
      schedule.append(
        (
          str(event.gcs_uri),
          float(item.start_time_sec) + float(event.start_time),
          float(item.start_time_sec) + float(event.end_time),
        ))
  schedule = [entry for entry in schedule if float(entry[2]) > float(entry[1])]
  schedule.sort(key=lambda entry: float(entry[1]))
  return schedule


def _download_audio_to_temp(
  audio_files: list[tuple[str, float, float]],
  *,
  temp_dir: str,
) -> list[tuple[str, float, float, str]]:
  out: list[tuple[str, float, float, str]] = []
  for index, (gcs_uri, start_time, end_time) in enumerate(audio_files):
    _, blob_name = cloud_storage.parse_gcs_uri(gcs_uri)
    extension = os.path.splitext(blob_name)[1] or ".wav"
    local_path = os.path.join(temp_dir, f"audio_{index}{extension}")
    content_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)
    with open(local_path, "wb") as file_handle:
      file_handle.write(content_bytes)
    out.append((gcs_uri, float(start_time), float(end_time), local_path))
  return out


def _build_audio_clips(
  audio_paths: list[tuple[str, float, float, str]], ) -> list[AudioFileClip]:
  clips: list[AudioFileClip] = []
  for _gcs_uri, start_time, end_time, path in audio_paths:
    duration = float(end_time) - float(start_time)
    if duration <= 0:
      continue
    clip = AudioFileClip(path).with_start(float(start_time))
    if hasattr(clip, "with_duration"):
      clip = clip.with_duration(duration)
    elif hasattr(clip, "set_duration"):
      clip = clip.set_duration(duration)
    clips.append(clip)
  return clips


def generate_scene_video(
  *,
  script: SceneScript,
  output_gcs_uri: str,
  label: str,
  fps: int = _DEFAULT_VIDEO_FPS,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Render a video from a fully declarative `SceneScript`."""
  script.validate()
  if int(fps) <= 0:
    raise ValueError("FPS must be positive")

  start_perf = float(time.perf_counter())
  video_clip = None
  audio_composite = None
  audio_clips: list[AudioFileClip] = []

  try:
    with tempfile.TemporaryDirectory() as temp_dir:
      prepared_images = _prepare_images(script)
      actor_renders = _prepare_actor_renders(script)
      audio_schedule = _extract_audio_schedule(script)
      audio_paths = _download_audio_to_temp(audio_schedule, temp_dir=temp_dir)

      def make_frame(time_sec: float) -> np.ndarray:
        return _render_scene_frame(
          time_sec=float(time_sec),
          canvas=script.canvas,
          prepared_images=prepared_images,
          actor_renders=actor_renders,
        )

      video_clip = VideoClip(make_frame, duration=float(script.duration_sec))
      if audio_paths:
        audio_clips = _build_audio_clips(audio_paths)
        audio_composite = CompositeAudioClip(audio_clips)
        video_clip = video_clip.with_audio(audio_composite)

      output_path = os.path.join(temp_dir, "scene.mp4")
      video_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=int(fps),
        logger=None,
      )

      cloud_storage.upload_file_to_gcs(
        output_path,
        output_gcs_uri,
        content_type="video/mp4",
      )

      file_size_bytes = os.path.getsize(output_path)
      generation_time_sec = float(time.perf_counter()) - float(start_perf)
      num_images = len([item for item in script.items if isinstance(item, TimedImage)])
      num_characters = len({
        item.actor_id for item in script.items
        if isinstance(item, TimedCharacterSequence)
      })
      metadata = models.SingleGenerationMetadata(
        label=label,
        model_name="moviepy",
        token_counts={
          "num_images": int(num_images),
          "num_audio_files": int(len(audio_schedule)),
          "num_characters": int(num_characters),
          "video_duration_sec": int(float(script.duration_sec)),
          "output_file_size_bytes": int(file_size_bytes),
          "canvas_width_px": int(script.canvas.width_px),
          "canvas_height_px": int(script.canvas.height_px),
        },
        generation_time_sec=float(generation_time_sec),
        cost=0.0,
      )
      return output_gcs_uri, metadata
  finally:
    for clip in audio_clips:
      try:
        clip.close()
      except Exception:
        pass
    if audio_composite is not None:
      try:
        audio_composite.close()
      except Exception:
        pass
    if video_clip is not None:
      try:
        video_clip.close()
      except Exception:
        pass
