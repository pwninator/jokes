"""Generic scene video renderer driven by `SceneScript`."""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, TypedDict

import numpy as np
from common import models
from common.character_animator import CharacterAnimator
from common.posable_character import PosableCharacter, PoseState
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import VideoClip
from PIL import Image, ImageOps
from services import cloud_storage
from services.video.script import (FitMode, SceneCanvas, SceneRect,
                                   SceneScript, TimedCharacterSequence,
                                   TimedImage)

_DEFAULT_VIDEO_FPS = 24
_AUDIO_DURATION_COMPARISON_TOLERANCE_SEC = 0.001
_AudioScheduleEntry = tuple[str, float, float, float]
_DownloadedAudioEntry = tuple[str, float, float, float, str]


class _ActorEntry(TypedDict):
  source_order: int
  items: list[TimedCharacterSequence]


@dataclass(frozen=True)
class _PreparedImage:
  source_order: int
  start_time_sec: float
  end_time_sec: float
  z_index: int
  sprite: Image.Image
  paste_position: tuple[int, int]


@dataclass(frozen=True)
class _ActorClip:
  start_time_sec: float
  end_time_sec: float
  animator: CharacterAnimator


@dataclass(frozen=True)
class _ActorRender:
  actor_id: str
  source_order: int
  character: PosableCharacter
  clips: list[_ActorClip]
  pre_start_pose: PoseState
  z_index: int
  rect: SceneRect
  fit_mode: FitMode


def generate_scene_video(
  *,
  script: SceneScript,
  output_gcs_uri: str,
  label: str,
  fps: int = _DEFAULT_VIDEO_FPS,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Render a video from a fully declarative `SceneScript`."""
  script.validate()
  if fps <= 0:
    raise ValueError("FPS must be positive")

  start_perf = time.perf_counter()
  video_clip: VideoClip | None = None
  audio_composite: CompositeAudioClip | None = None
  audio_clips: list[AudioFileClip] = []

  try:
    with tempfile.TemporaryDirectory() as temp_dir:
      prepared_images = _prepare_images(script)
      actor_renders = _prepare_actor_renders(script)
      audio_schedule = _extract_audio_schedule(script)
      audio_paths = _download_audio_to_temp(audio_schedule, temp_dir=temp_dir)

      def make_frame(time_sec: float) -> np.ndarray[Any, Any]:
        return _render_scene_frame(
          time_sec=time_sec,
          canvas=script.canvas,
          prepared_images=prepared_images,
          actor_renders=actor_renders,
        )

      video_clip = VideoClip(make_frame, duration=script.duration_sec)
      if audio_paths:
        audio_clips = _build_audio_clips(audio_paths)
        audio_composite = CompositeAudioClip(audio_clips)
        video_clip = video_clip.with_audio(audio_composite)

      output_path = os.path.join(temp_dir, "scene.mp4")
      video_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        logger=None,
      )

      _ = cloud_storage.upload_file_to_gcs(
        output_path,
        output_gcs_uri,
        content_type="video/mp4",
      )

      file_size_bytes = os.path.getsize(output_path)
      generation_time_sec = time.perf_counter() - start_perf
      num_images = len(
        [item for item in script.items if isinstance(item, TimedImage)])
      num_characters = len({
        item.actor_id
        for item in script.items if isinstance(item, TimedCharacterSequence)
      })
      metadata = models.SingleGenerationMetadata(
        label=label,
        model_name="moviepy",
        token_counts={
          "num_images": num_images,
          "num_audio_files": len(audio_schedule),
          "num_characters": num_characters,
          "video_duration_sec": int(script.duration_sec),
          "output_file_size_bytes": file_size_bytes,
          "canvas_width_px": script.canvas.width_px,
          "canvas_height_px": script.canvas.height_px,
        },
        generation_time_sec=generation_time_sec,
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


def _render_with_fit(
  image: Image.Image,
  *,
  rect: SceneRect,
  fit_mode: FitMode,
  allow_upscale: bool,
) -> tuple[Image.Image, int, int]:
  source = image.convert("RGBA")
  rect_x = rect.x_px
  rect_y = rect.y_px
  rect_width = rect.width_px
  rect_height = rect.height_px

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
  width_scale = rect_width / source.width
  height_scale = rect_height / source.height
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
    source = cloud_storage.download_image_from_gcs(
      item.gcs_uri).convert("RGBA")
    sprite, x, y = _render_with_fit(
      source,
      rect=item.rect,
      fit_mode=item.fit_mode,
      allow_upscale=True,
    )
    prepared.append(
      _PreparedImage(
        source_order=index,
        start_time_sec=item.start_time_sec,
        end_time_sec=item.end_time_sec,
        z_index=item.z_index,
        sprite=sprite,
        paste_position=(x, y),
      ))
  prepared.sort(key=lambda entry: (entry.z_index, entry.source_order))
  return prepared


def _prepare_actor_renders(script: SceneScript) -> list[_ActorRender]:
  by_actor: dict[str, _ActorEntry] = {}
  for index, item in enumerate(script.items):
    if isinstance(item, TimedCharacterSequence):
      actor_entry = by_actor.setdefault(item.actor_id, {
        "source_order": index,
        "items": [],
      })
      actor_entry["source_order"] = min(actor_entry["source_order"], index)
      actor_entry["items"].append(item)

  renders: list[_ActorRender] = []
  for actor_id, actor_entry in by_actor.items():
    items = sorted(actor_entry["items"],
                   key=lambda entry: entry.start_time_sec)
    first_item = items[0]
    first_item_animator = CharacterAnimator(first_item.sequence)
    pre_start_pose = first_item_animator.sample_pose(0.0)
    clips = [
      _ActorClip(
        start_time_sec=item.start_time_sec,
        end_time_sec=item.end_time_sec,
        animator=CharacterAnimator(item.sequence),
      ) for item in items
    ]
    character = items[0].character
    z_index = items[0].z_index
    rect = items[0].rect
    fit_mode = items[0].fit_mode
    renders.append(
      _ActorRender(
        actor_id=actor_id,
        source_order=actor_entry["source_order"],
        character=character,
        clips=clips,
        pre_start_pose=pre_start_pose,
        z_index=z_index,
        rect=rect,
        fit_mode=fit_mode,
      ))
  renders.sort(key=lambda entry: (entry.z_index, entry.source_order))
  return renders


def _render_scene_frame(
  *,
  time_sec: float,
  canvas: SceneCanvas,
  prepared_images: list[_PreparedImage],
  actor_renders: list[_ActorRender],
) -> np.ndarray[Any, Any]:
  base = Image.new("RGBA", (canvas.width_px, canvas.height_px),
                   tuple(canvas.background_rgba))

  image_index = 0
  actor_index = 0
  while image_index < len(prepared_images) or actor_index < len(actor_renders):
    render_image = actor_index >= len(actor_renders)
    if image_index < len(prepared_images) and actor_index < len(actor_renders):
      image_key = (
        prepared_images[image_index].z_index,
        prepared_images[image_index].source_order,
      )
      actor_key = (
        actor_renders[actor_index].z_index,
        actor_renders[actor_index].source_order,
      )
      render_image = image_key <= actor_key

    if render_image:
      image = prepared_images[image_index]
      image_index += 1
      if not (image.start_time_sec <= time_sec < image.end_time_sec):
        continue
      x, y = image.paste_position
      base.paste(image.sprite, (x, y), image.sprite)
      continue

    render = actor_renders[actor_index]
    actor_index += 1
    pose = _sample_actor_pose(render=render, time_sec=time_sec)
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


def _sample_actor_pose(*, render: _ActorRender, time_sec: float) -> PoseState:
  """Sample actor pose by selecting the active sequence clip for `time_sec`."""
  if not render.clips:
    raise ValueError(f"Actor '{render.actor_id}' has no clips")

  first_clip = render.clips[0]
  if time_sec < first_clip.start_time_sec:
    return render.pre_start_pose

  for clip_index, clip in enumerate(render.clips):
    next_start_sec = float("inf")
    if clip_index + 1 < len(render.clips):
      next_start_sec = render.clips[clip_index + 1].start_time_sec
    if time_sec < next_start_sec:
      local_time_sec = max(0.0, time_sec - clip.start_time_sec)
      return clip.animator.sample_pose(local_time_sec)

  last_clip = render.clips[-1]
  local_time_sec = max(0.0, time_sec - last_clip.start_time_sec)
  return last_clip.animator.sample_pose(local_time_sec)


def _extract_audio_schedule(
  script: SceneScript, ) -> list[_AudioScheduleEntry]:
  schedule: list[_AudioScheduleEntry] = []
  for item in script.items:
    if not isinstance(item, TimedCharacterSequence):
      continue
    for event in item.sequence.sequence_sound_events:
      schedule.append((
        event.gcs_uri,
        item.start_time_sec + event.start_time,
        item.start_time_sec + event.end_time,
        event.volume,
      ))
  schedule = [entry for entry in schedule if entry[2] > entry[1]]
  schedule.sort(key=lambda entry: entry[1])
  return schedule


def _download_audio_to_temp(
  audio_files: list[_AudioScheduleEntry],
  *,
  temp_dir: str,
) -> list[_DownloadedAudioEntry]:
  out: list[_DownloadedAudioEntry] = []
  for index, (gcs_uri, start_time, end_time, volume) in enumerate(audio_files):
    _, blob_name = cloud_storage.parse_gcs_uri(gcs_uri)
    extension = os.path.splitext(blob_name)[1] or ".wav"
    local_path = os.path.join(temp_dir, f"audio_{index}{extension}")
    content_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)
    with open(local_path, "wb") as file_handle:
      _ = file_handle.write(content_bytes)
    out.append((gcs_uri, start_time, end_time, volume, local_path))
  return out


def _build_audio_clips(
  audio_paths: list[_DownloadedAudioEntry], ) -> list[AudioFileClip]:
  clips: list[AudioFileClip] = []
  for _gcs_uri, start_time, end_time, volume, path in audio_paths:
    requested_duration = end_time - start_time
    if requested_duration <= 0:
      continue
    clip = AudioFileClip(path).with_start(start_time)
    clip = clip.with_volume_scaled(volume)
    source_duration = clip.duration if clip.duration is not None else 0.0

    # Never extend a clip beyond its source media duration; this can cause
    # MoviePy to request out-of-range frames for short files.
    if source_duration > 0:
      if requested_duration > (source_duration +
                               _AUDIO_DURATION_COMPARISON_TOLERANCE_SEC):
        clips.append(clip)
        continue
      if requested_duration >= (source_duration -
                                _AUDIO_DURATION_COMPARISON_TOLERANCE_SEC):
        clips.append(clip)
        continue

    clip = clip.with_duration(requested_duration)
    clips.append(clip)
  return clips
