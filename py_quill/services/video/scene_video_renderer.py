"""Generic scene video renderer driven by `SceneScript`."""

from __future__ import annotations

import os
import tempfile
import time
import math
from dataclasses import dataclass
from typing import Any, TypedDict

import numpy as np
from common import image_operations, models
from common.character_animator import CharacterAnimator
from common.posable_character import PosableCharacter, PoseState
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import VideoClip
from PIL import Image, ImageDraw, ImageOps
from services import cloud_storage
from services.video.script import (FitMode, SceneCanvas, SceneRect,
                                   SceneScript, TimedCharacterSequence,
                                   TimedImage)

_DEFAULT_VIDEO_FPS = 24
_TERMINAL_SAMPLE_EPSILON_SEC = 1e-6
_AUDIO_DURATION_COMPARISON_TOLERANCE_SEC = 0.001
_AudioScheduleEntry = tuple[str, float, float, float]
_DownloadedAudioEntry = tuple[str, float, float, float, str]
_SubtitleScheduleEntry = tuple[float, float, str]
_SUBTITLE_FONT_SIZE_PX = 72
_SUBTITLE_TEXT_FILL = (33, 33, 33, 255)
_SUBTITLE_STROKE_FILL = (255, 255, 255, 255)
_SUBTITLE_STROKE_WIDTH_PX = 3
_SUBTITLE_LINE_SPACING_PX = 4


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
  print(f"Generating scene video for script: {script}")

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
      subtitle_schedule = _extract_subtitle_schedule(script)
      audio_paths = _download_audio_to_temp(audio_schedule, temp_dir=temp_dir)

      def make_frame(time_sec: float) -> np.ndarray[Any, Any]:
        return _render_scene_frame(
          time_sec=time_sec,
          canvas=script.canvas,
          prepared_images=prepared_images,
          actor_renders=actor_renders,
          subtitle_schedule=subtitle_schedule,
          subtitle_rect=script.subtitle_rect,
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


def _fit_scale(
  *,
  fit_mode: FitMode,
  source_width: int,
  source_height: int,
  rect_width: int,
  rect_height: int,
  allow_upscale: bool,
) -> tuple[float, float]:
  if fit_mode == "fill":
    return rect_width / source_width, rect_height / source_height

  width_scale = rect_width / source_width
  height_scale = rect_height / source_height
  if fit_mode == "cover":
    scale = max(width_scale, height_scale)
    return scale, scale

  scale = min(width_scale, height_scale)
  if not allow_upscale:
    scale = min(1.0, scale)
  return scale, scale


def _render_actor_with_fit(
  image: Image.Image,
  *,
  rect: SceneRect,
  fit_mode: FitMode,
  allow_upscale: bool,
  logical_origin_x: int,
  logical_origin_y: int,
  logical_width: int,
  logical_height: int,
) -> tuple[Image.Image, int, int]:
  source = image.convert("RGBA")
  if logical_width <= 0 or logical_height <= 0:
    raise ValueError("Actor logical dimensions must be > 0, got "
                     f"({logical_width}, {logical_height})")

  scale_x, scale_y = _fit_scale(
    fit_mode=fit_mode,
    source_width=logical_width,
    source_height=logical_height,
    rect_width=rect.width_px,
    rect_height=rect.height_px,
    allow_upscale=allow_upscale,
  )
  target_width = max(1, int(round(source.width * scale_x)))
  target_height = max(1, int(round(source.height * scale_y)))
  fitted = source
  if (target_width, target_height) != source.size:
    fitted = source.resize((target_width, target_height),
                           resample=Image.Resampling.LANCZOS)

  if fit_mode == "fill":
    logical_x = rect.x_px
    logical_y = rect.y_px
  else:
    target_logical_width = logical_width * scale_x
    target_logical_height = logical_height * scale_y
    logical_x = rect.x_px + int(
      round((rect.width_px - target_logical_width) / 2.0))
    logical_y = rect.y_px + int(
      round((rect.height_px - target_logical_height) / 2.0))

  paste_x = logical_x - int(round(logical_origin_x * scale_x))
  paste_y = logical_y - int(round(logical_origin_y * scale_y))
  return fitted, paste_x, paste_y


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
  subtitle_schedule: list[_SubtitleScheduleEntry],
  subtitle_rect: SceneRect | None,
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
      times_are_valid = image.start_time_sec <= time_sec < image.end_time_sec
      if not times_are_valid:
        continue
      x, y = image.paste_position
      base.paste(image.sprite, (x, y), image.sprite)
      continue

    render = actor_renders[actor_index]
    actor_index += 1
    pose = _sample_actor_pose(render=render, time_sec=time_sec)
    render.character.apply_pose_state(pose)
    sprite = render.character.get_image()
    (
      logical_origin_x,
      logical_origin_y,
      logical_width,
      logical_height,
    ) = render.character.get_render_frame_info()
    fitted, x, y = _render_actor_with_fit(
      sprite,
      rect=render.rect,
      fit_mode=render.fit_mode,
      allow_upscale=False,
      logical_origin_x=logical_origin_x,
      logical_origin_y=logical_origin_y,
      logical_width=logical_width,
      logical_height=logical_height,
    )
    base.paste(fitted, (x, y), fitted)

  _render_subtitle_overlay(
    base=base,
    time_sec=time_sec,
    subtitle_schedule=subtitle_schedule,
    subtitle_rect=subtitle_rect,
  )
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
      safe_local_time_sec = _terminal_safe_sample_time(
        local_time_sec=local_time_sec,
        sequence_duration_sec=clip.animator.duration_sec,
      )
      return clip.animator.sample_pose(safe_local_time_sec)

  last_clip = render.clips[-1]
  local_time_sec = max(0.0, time_sec - last_clip.start_time_sec)
  safe_local_time_sec = _terminal_safe_sample_time(
    local_time_sec=local_time_sec,
    sequence_duration_sec=last_clip.animator.duration_sec,
  )
  return last_clip.animator.sample_pose(safe_local_time_sec)


def _terminal_safe_sample_time(
  *,
  local_time_sec: float,
  sequence_duration_sec: float,
) -> float:
  """Avoid exact end-time sampling to preserve final half-open event frame."""
  if sequence_duration_sec <= 0:
    return local_time_sec
  if local_time_sec < sequence_duration_sec:
    return local_time_sec
  if abs(local_time_sec -
         sequence_duration_sec) <= _TERMINAL_SAMPLE_EPSILON_SEC:
    return max(0.0, sequence_duration_sec - _TERMINAL_SAMPLE_EPSILON_SEC)
  return local_time_sec


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


def _extract_subtitle_schedule(
    script: SceneScript) -> list[_SubtitleScheduleEntry]:
  schedule: list[_SubtitleScheduleEntry] = []
  for item in script.items:
    if not isinstance(item, TimedCharacterSequence):
      continue
    for event in item.sequence.sequence_subtitle_events:
      text = str(event.text or "").strip()
      if not text:
        continue
      start_time = item.start_time_sec + event.start_time
      end_time = item.start_time_sec + event.end_time
      if end_time <= start_time:
        continue
      schedule.append((start_time, end_time, text))
  schedule.sort(key=lambda entry: entry[0])
  return schedule


def _render_subtitle_overlay(
  *,
  base: Image.Image,
  time_sec: float,
  subtitle_schedule: list[_SubtitleScheduleEntry],
  subtitle_rect: SceneRect | None,
) -> None:
  if subtitle_rect is None:
    return

  active_text: str | None = None
  for start_time, end_time, text in subtitle_schedule:
    if start_time <= time_sec < end_time:
      active_text = text
      break
  if not active_text:
    return

  draw = ImageDraw.Draw(base)
  font = image_operations.get_text_font(_SUBTITLE_FONT_SIZE_PX)
  wrapped_lines = _wrap_subtitle_lines(
    draw=draw,
    font=font,
    text=active_text,
    max_width_px=subtitle_rect.width_px,
  )

  text_y = subtitle_rect.y_px
  for line in wrapped_lines:
    line_bbox = draw.textbbox(
      (0, 0),
      line,
      font=font,
      stroke_width=_SUBTITLE_STROKE_WIDTH_PX,
    )
    line_width = line_bbox[2] - line_bbox[0]
    line_height = line_bbox[3] - line_bbox[1]
    text_x = subtitle_rect.x_px + int((subtitle_rect.width_px - line_width) / 2)
    draw.text(
      (text_x, text_y),
      line,
      fill=_SUBTITLE_TEXT_FILL,
      font=font,
      stroke_width=_SUBTITLE_STROKE_WIDTH_PX,
      stroke_fill=_SUBTITLE_STROKE_FILL,
    )
    text_y += line_height + _SUBTITLE_LINE_SPACING_PX


def _subtitle_line_width_px(
  draw: ImageDraw.ImageDraw,
  *,
  font: Any,
  text: str,
) -> int:
  bbox = draw.textbbox(
    (0, 0),
    text,
    font=font,
    stroke_width=_SUBTITLE_STROKE_WIDTH_PX,
  )
  return int(round(bbox[2] - bbox[0]))


def _split_words_evenly_by_chars(words: list[str], line_count: int) -> list[str]:
  if line_count <= 1 or len(words) <= 1:
    return [" ".join(words)] if words else []

  lines: list[str] = []
  remaining_words = words[:]
  remaining_chars = len(" ".join(remaining_words))

  for line_index in range(line_count):
    lines_left = line_count - line_index
    if not remaining_words:
      break
    if lines_left == 1:
      lines.append(" ".join(remaining_words))
      break

    target_chars = int(math.ceil(remaining_chars / lines_left))
    current_words: list[str] = [remaining_words.pop(0)]

    while remaining_words:
      candidate = " ".join([*current_words, remaining_words[0]])
      words_left_after_add = len(remaining_words) - 1
      min_words_needed_after_add = lines_left - 1
      if words_left_after_add < min_words_needed_after_add:
        break
      if len(candidate) > target_chars:
        break
      current_words.append(remaining_words.pop(0))

    line_text = " ".join(current_words)
    lines.append(line_text)
    remaining_chars -= len(line_text)
    if remaining_words:
      remaining_chars -= 1

  return [line for line in lines if line]


def _wrap_subtitle_lines(
  *,
  draw: ImageDraw.ImageDraw,
  font: Any,
  text: str,
  max_width_px: int,
) -> list[str]:
  normalized_text = " ".join(text.split())
  if not normalized_text:
    return []
  if max_width_px <= 0:
    return [normalized_text]

  full_width = _subtitle_line_width_px(draw, font=font, text=normalized_text)
  if full_width <= max_width_px:
    return [normalized_text]

  words = normalized_text.split(" ")
  if len(words) <= 1:
    return [normalized_text]

  line_count = max(2, int(math.ceil(full_width / max_width_px)))
  line_count = min(line_count, len(words))
  last_lines: list[str] = [normalized_text]

  while line_count <= len(words):
    lines = _split_words_evenly_by_chars(words, line_count)
    if not lines:
      return [normalized_text]
    last_lines = lines

    widths = [
      _subtitle_line_width_px(draw, font=font, text=line_text)
      for line_text in lines
    ]
    if max(widths) <= max_width_px:
      return lines
    if any(width > max_width_px and len(line_text.split(" ")) == 1
           for line_text, width in zip(lines, widths)):
      return lines

    line_count += 1

  return last_lines


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
