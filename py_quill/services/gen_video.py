"""Video generation service using moviepy."""

from __future__ import annotations

import os
import random
import tempfile
import time
import traceback
from typing import Any

from common import models, utils
from firebase_functions import logger
from moviepy import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                     ImageClip)
from services import cloud_storage

_DEFAULT_VIDEO_FPS = 24


class Error(Exception):
  """Base class for exceptions in this module."""


class GenVideoError(Error):
  """Exception raised for errors during video generation."""


def create_slideshow_video(
  images: list[tuple[str, float]],
  audio_files: list[tuple[str, float]],
  total_duration_sec: float,
  output_filename_base: str,
  temp_output: bool = False,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Create a slideshow video with timed images and audio.

  Args:
    images: List of (gcs_uri, start_time_sec) tuples for images.
    audio_files: List of (gcs_uri, start_time_sec) tuples for audio WAV files.
    total_duration_sec: Total duration of the video in seconds.
    output_filename_base: Base filename for the output video in GCS.
    temp_output: Whether to upload to the temp bucket.

  Returns:
    (gcs_uri, metadata) for the generated MP4 video.
  """
  if utils.is_emulator():
    logger.info('Running in emulator mode. Returning a test video file.')
    random_suffix = f"{random.randint(1, 10):02d}"
    test_uri = f"gs://test_story_video_data/test_slideshow_video_{random_suffix}.mp4"
    return test_uri, models.SingleGenerationMetadata()

  normalized_images = _normalize_timed_assets(images,
                                              label="image",
                                              allow_empty=False)
  normalized_audio = _normalize_timed_assets(audio_files,
                                             label="audio",
                                             allow_empty=True)
  _validate_video_duration(total_duration_sec)
  _validate_output_filename(output_filename_base)
  _validate_image_timing(normalized_images, total_duration_sec)
  _validate_audio_timing(normalized_audio, total_duration_sec)

  start_time = time.perf_counter()
  output_gcs_uri = cloud_storage.get_video_gcs_uri(
    output_filename_base,
    "mp4",
    temp=temp_output,
  )

  logger.info(
    "Starting slideshow video generation: "
    f"{len(normalized_images)} images, {len(normalized_audio)} audio files, "
    f"duration={total_duration_sec}s, output={output_gcs_uri}")

  image_clips: list[ImageClip] = []
  audio_clips: list[AudioFileClip] = []
  video_clip = None
  audio_composite = None

  try:
    with tempfile.TemporaryDirectory() as temp_dir:
      image_paths = _download_assets_to_temp(
        normalized_images,
        temp_dir,
        prefix="image",
        default_extension=".png",
      )
      audio_paths = _download_assets_to_temp(
        normalized_audio,
        temp_dir,
        prefix="audio",
        default_extension=".wav",
      )

      base_size = _extract_base_size(image_paths)
      image_clips = _create_image_clips(normalized_images, image_paths,
                                        base_size, total_duration_sec)

      video_clip = CompositeVideoClip(
        image_clips, size=base_size).with_duration(total_duration_sec)

      if audio_paths:
        audio_clips = _create_audio_clips(normalized_audio, audio_paths)
        audio_composite = CompositeAudioClip(audio_clips)
        video_clip = video_clip.with_audio(audio_composite)

      output_path = os.path.join(temp_dir, "slideshow.mp4")
      video_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=_DEFAULT_VIDEO_FPS,
        logger=None,
      )

      cloud_storage.upload_file_to_gcs(
        output_path,
        output_gcs_uri,
        content_type="video/mp4",
      )

      file_size_bytes = os.path.getsize(output_path)
      generation_time_sec = time.perf_counter() - start_time

      metadata = models.SingleGenerationMetadata(
        label="create_slideshow_video",
        model_name="moviepy",
        token_counts={
          "num_images": len(normalized_images),
          "num_audio_files": len(normalized_audio),
          "video_duration_sec": int(total_duration_sec),
          "output_file_size_bytes": file_size_bytes,
        },
        generation_time_sec=generation_time_sec,
        cost=0.0,
      )

      _log_video_response(normalized_images, normalized_audio, output_gcs_uri,
                          metadata)
      return output_gcs_uri, metadata

  except Exception as e:
    logger.error("Video generation failed:\n"
                 f"{traceback.format_exc()}")
    raise GenVideoError(f"Video generation failed: {e}") from e
  finally:
    for clip in image_clips:
      try:
        clip.close()
      except Exception:
        pass
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


def _normalize_timed_assets(
  assets: list[tuple[str, float]] | None,
  *,
  label: str,
  allow_empty: bool,
) -> list[tuple[str, float]]:
  """Validate and normalize a list of timed assets."""
  if not assets:
    if allow_empty:
      return []
    raise GenVideoError(f"At least one {label} must be provided")

  normalized: list[tuple[str, float]] = []
  for index, item in enumerate(assets):
    try:
      gcs_uri, start_time = item
    except (TypeError, ValueError) as e:
      raise GenVideoError(
        f"Invalid {label} entry at index {index}: {item}") from e

    gcs_uri = str(gcs_uri).strip()
    if not gcs_uri:
      raise GenVideoError(f"{label.title()} GCS URI must be non-empty")
    cloud_storage.parse_gcs_uri(gcs_uri)

    try:
      start_time = float(start_time)
    except (TypeError, ValueError) as e:
      raise GenVideoError(
        f"Invalid {label} start time at index {index}: {start_time}") from e
    if start_time < 0:
      raise GenVideoError(
        f"{label.title()} start time must be >= 0 (index {index})")

    normalized.append((gcs_uri, start_time))

  normalized.sort(key=lambda item: item[1])
  return normalized


def _validate_video_duration(total_duration_sec: float) -> None:
  if total_duration_sec is None:
    raise GenVideoError("Total duration must be provided")
  try:
    total_duration_sec = float(total_duration_sec)
  except (TypeError, ValueError) as e:
    raise GenVideoError(
      f"Total duration must be a number: {total_duration_sec}") from e
  if total_duration_sec <= 0:
    raise GenVideoError("Total duration must be greater than 0")


def _validate_output_filename(output_filename_base: str) -> None:
  if not str(output_filename_base).strip():
    raise GenVideoError("Output filename base must be non-empty")


def _validate_image_timing(images: list[tuple[str, float]],
                           total_duration_sec: float) -> None:
  if images[0][1] > 0:
    raise GenVideoError("First image must start at 0 seconds")
  if images[-1][1] >= total_duration_sec:
    raise GenVideoError(
      "Last image start time must be less than total duration")

  for index in range(len(images) - 1):
    current_start = images[index][1]
    next_start = images[index + 1][1]
    if next_start <= current_start:
      raise GenVideoError(
        "Image start times must be strictly increasing (index "
        f"{index} -> {index + 1})")


def _validate_audio_timing(audio_files: list[tuple[str, float]],
                           total_duration_sec: float) -> None:
  for index, (_, start_time) in enumerate(audio_files):
    if start_time >= total_duration_sec:
      raise GenVideoError(
        f"Audio start time must be less than total duration (index {index})")


def _download_assets_to_temp(
  assets: list[tuple[str, float]],
  temp_dir: str,
  *,
  prefix: str,
  default_extension: str,
) -> list[str]:
  """Download assets from GCS into a temporary directory."""
  paths: list[str] = []
  for index, (gcs_uri, _) in enumerate(assets):
    _, blob_name = cloud_storage.parse_gcs_uri(gcs_uri)
    extension = os.path.splitext(blob_name)[1] or default_extension
    local_path = os.path.join(temp_dir, f"{prefix}_{index}{extension}")
    content_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)
    with open(local_path, "wb") as file_handle:
      file_handle.write(content_bytes)
    paths.append(local_path)
  return paths


def _extract_base_size(image_paths: list[str]) -> tuple[int, int]:
  """Get the base size from the first image."""
  if not image_paths:
    raise GenVideoError("No image paths to determine base size")
  clip = ImageClip(image_paths[0])
  try:
    return clip.size
  finally:
    clip.close()


def _create_image_clips(
  images: list[tuple[str, float]],
  image_paths: list[str],
  base_size: tuple[int, int],
  total_duration_sec: float,
) -> list[ImageClip]:
  """Create ImageClip objects with computed durations."""
  clips: list[ImageClip] = []
  for index, ((_, start_time),
              image_path) in enumerate(zip(images, image_paths)):
    if index < len(images) - 1:
      duration = images[index + 1][1] - start_time
    else:
      duration = total_duration_sec - start_time

    if duration <= 0:
      raise GenVideoError(f"Image duration must be positive (index {index})")

    clip = ImageClip(image_path).with_start(start_time).with_duration(duration)
    if clip.size != base_size:
      clip = clip.resized(new_size=base_size)
    clips.append(clip)

  return clips


def _create_audio_clips(
  audio_files: list[tuple[str, float]],
  audio_paths: list[str],
) -> list[AudioFileClip]:
  """Create AudioFileClip objects with start times."""
  clips: list[AudioFileClip] = []
  for (gcs_uri, start_time), audio_path in zip(audio_files, audio_paths):
    try:
      clip = AudioFileClip(audio_path).with_start(start_time)
    except Exception as e:
      raise GenVideoError(f"Failed to load audio file: {gcs_uri}") from e
    clips.append(clip)
  return clips


def _log_video_response(
  images: list[tuple[str, float]],
  audio_files: list[tuple[str, float]],
  gcs_uri: str,
  metadata: models.SingleGenerationMetadata,
  extra_log_data: dict[str, Any] | None = None,
) -> None:
  """Log the video response and metadata."""
  image_lines = "\n".join(f"- {uri} @ {start:.2f}s" for uri, start in images)
  audio_lines = "\n".join(f"- {uri} @ {start:.2f}s"
                          for uri, start in audio_files)
  usage_str = "\n".join(f"{k}: {v}" for k, v in metadata.token_counts.items())

  log_parts = []
  log_parts.append(f"""
============================== Input Images ({len(images)}) ==============================
{image_lines}
""")
  log_parts.append(f"""
============================== Input Audio ({len(audio_files)}) ==============================
{audio_lines or '(none)'}
""")
  log_parts.append(f"""
============================== Output GCS URI ==============================
{gcs_uri}
""")
  log_parts.append(f"""
============================== Metadata ==============================
Tool: {metadata.model_name}
Generation time: {metadata.generation_time_sec:.2f} seconds
Generation cost: ${metadata.cost:.6f}
{usage_str}
""")

  header = f"Video done: {metadata.label} ({metadata.model_name})"
  combined_log = header + "\n" + "\n\n".join(log_parts)

  log_extra_data = {
    "generation_time_sec": metadata.generation_time_sec,
    "model_name": metadata.model_name,
    "label": metadata.label,
    **metadata.token_counts,
    **(extra_log_data or {}),
  }

  if len(combined_log) <= 65_000:
    logger.info(combined_log, extra={"json_fields": log_extra_data})
  else:
    for i, part in enumerate(log_parts):
      if i == len(log_parts) - 1:
        logger.info(f"{header}\n{part}", extra={"json_fields": log_extra_data})
      else:
        logger.info(f"{header}\n{part}")
