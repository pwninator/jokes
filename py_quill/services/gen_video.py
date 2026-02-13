"""Video generation service using moviepy."""

from __future__ import annotations

import os
import random
import tempfile
import time
import traceback

from common import audio_timing, models, utils
from common.posable_character import PosableCharacter
from firebase_functions import logger
from moviepy import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                     ImageClip)
from services import cloud_storage
from services import mouth_event_detection
from services.video.scene_video_renderer import generate_scene_video
from services.video import joke_social_script_builder

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
      video_clip = CompositeVideoClip(image_clips,
                                      size=base_size).with_duration(
                                        float(total_duration_sec))

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
          "video_duration_sec": int(float(total_duration_sec)),
          "output_file_size_bytes": file_size_bytes,
        },
        generation_time_sec=generation_time_sec,
        cost=0.0,
      )
      _log_video_response(images=normalized_images,
                          audio_files=normalized_audio,
                          gcs_uri=output_gcs_uri,
                          metadata=metadata)
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


def create_portrait_character_video(
  joke_images: list[tuple[str, float]],
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[
    str,
    float,
    str,
    list[audio_timing.WordTiming] | None,
  ]]]],
  footer_background_gcs_uri: str,
  total_duration_sec: float,
  output_filename_base: str,
  temp_output: bool = False,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Create a portrait video with animated character(s) in the footer.

  Args:
    joke_images: List of (gcs_uri, start_time_sec) for joke images.
    character_dialogs: List of (character, [(audio_gcs_uri, start_time, transcript)]) tuples.
    footer_background_gcs_uri: GCS URI for the footer background image.
    total_duration_sec: Total video duration in seconds.
    output_filename_base: Base filename for the output video.
    temp_output: Whether to output to the temp bucket.

  Returns:
    (gcs_uri, metadata) tuple for the generated video.
  """
  if utils.is_emulator():
    logger.info('Running in emulator mode. Returning a test video file.')
    random_suffix = f"{random.randint(1, 10):02d}"
    test_uri = f"gs://test_story_video_data/test_portrait_video_{random_suffix}.mp4"
    return test_uri, models.SingleGenerationMetadata()

  normalized_images = _normalize_timed_assets(joke_images,
                                              label="image",
                                              allow_empty=False)
  normalized_dialogs = _normalize_character_dialogs(character_dialogs)
  flattened_audio = _flatten_character_audio(normalized_dialogs)
  normalized_audio = _normalize_timed_assets(flattened_audio,
                                             label="audio",
                                             allow_empty=True)

  _validate_video_duration(total_duration_sec)
  _validate_output_filename(output_filename_base)
  _validate_image_timing(normalized_images, total_duration_sec)
  _validate_audio_timing(normalized_audio, total_duration_sec)

  output_gcs_uri = cloud_storage.get_video_gcs_uri(
    output_filename_base,
    "mp4",
    temp=temp_output,
  )

  try:
    script = joke_social_script_builder.build_portrait_joke_scene_script(
      joke_images=normalized_images,
      character_dialogs=normalized_dialogs,
      footer_background_gcs_uri=str(footer_background_gcs_uri),
      total_duration_sec=float(total_duration_sec),
      detect_mouth_events_fn=mouth_event_detection.detect_mouth_events,
      include_drumming=True,
      drumming_duration_sec=2.0,
    )
    gcs_uri, metadata = generate_scene_video(
      script=script,
      output_gcs_uri=output_gcs_uri,
      label="create_portrait_character_video",
      fps=_DEFAULT_VIDEO_FPS,
    )
    _log_video_response(
      images=normalized_images,
      audio_files=normalized_audio,
      gcs_uri=gcs_uri,
      metadata=metadata,
      extra_log_data={
        "num_characters":
        len([c for c, _ in normalized_dialogs if c is not None]),
      })
    return gcs_uri, metadata
  except Exception as e:
    logger.error("Portrait video generation failed:\n"
                 f"{traceback.format_exc()}")
    raise GenVideoError(f"Portrait video generation failed: {e}") from e


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

  normalized.sort(key=lambda item: float(item[1]))
  return normalized


def _validate_video_duration(total_duration_sec: float) -> None:
  """Validate that total duration exists, is numeric, and is positive."""
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
  """Validate output filename base is non-empty."""
  if not str(output_filename_base).strip():
    raise GenVideoError("Output filename base must be non-empty")


def _validate_image_timing(images: list[tuple[str, float]],
                           total_duration_sec: float) -> None:
  """Validate image schedule starts at 0 and is strictly increasing."""
  if images[0][1] > 0:
    raise GenVideoError("First image must start at 0 seconds")
  if images[-1][1] >= float(total_duration_sec):
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
  """Validate each audio start falls before video end."""
  for index, (_, start_time) in enumerate(audio_files):
    if float(start_time) >= float(total_duration_sec):
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
  """Create timed image clips that fill the entire slideshow canvas."""
  clips: list[ImageClip] = []
  for index, (gcs_uri, start_time) in enumerate(images):
    path = image_paths[index]
    duration = float(total_duration_sec) - float(start_time)
    if index < len(images) - 1:
      duration = float(images[index + 1][1]) - float(start_time)
    clip = ImageClip(path).with_start(
      float(start_time)).with_duration(duration)
    clip = clip.resized(new_size=base_size)
    clips.append(clip)
  return clips


def _create_audio_clips(
  audio_files: list[tuple[str, float]],
  audio_paths: list[str],
) -> list[AudioFileClip]:
  """Create started `AudioFileClip`s aligned to audio start times."""
  clips: list[AudioFileClip] = []
  for index, (_gcs_uri, start_time) in enumerate(audio_files):
    path = audio_paths[index]
    clips.append(AudioFileClip(path).with_start(float(start_time)))
  return clips


def _log_video_response(
  *,
  images: list[tuple[str, float]],
  audio_files: list[tuple[str, float]],
  gcs_uri: str,
  metadata: models.SingleGenerationMetadata,
  extra_log_data: dict[str, object] | None = None,
) -> None:
  """Log a structured summary of video inputs/outputs."""
  try:
    image_lines = "\n".join(f"- {uri} @ {t}" for uri, t in images)
    audio_lines = "\n".join(f"- {uri} @ {t}" for uri, t in audio_files)
    usage_str = ", ".join(
      f"{k}={v}" for k, v in sorted((metadata.token_counts or {}).items()))
    combined_log = "\n".join([
      f"Video done: {metadata.label} ({metadata.model_name})",
      f"Images ({len(images)}):\n{image_lines or '(none)'}",
      f"Audio ({len(audio_files)}):\n{audio_lines or '(none)'}",
      f"Output: {gcs_uri}",
      f"Metadata: time={metadata.generation_time_sec:.2f}s cost=${metadata.cost:.6f} {usage_str}",
    ])
    logger.info(
      combined_log,
      extra={
        "json_fields": {
          "generation_time_sec": metadata.generation_time_sec,
          "model_name": metadata.model_name,
          "label": metadata.label,
          **(metadata.token_counts or {}),
          **(extra_log_data or {}),
        }
      },
    )
  except Exception:
    # Logging should never fail video generation.
    pass


def _normalize_character_dialogs(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[
    str,
    float,
    str,
    list[audio_timing.WordTiming] | None,
  ]]]],
) -> list[tuple[PosableCharacter | None, list[tuple[
    str,
    float,
    str,
    list[audio_timing.WordTiming] | None,
]]]]:
  """Normalize dialog entries and enforce transcript consistency per clip key."""
  if character_dialogs is None:
    raise GenVideoError("character_dialogs must be provided")

  normalized: list[tuple[PosableCharacter | None, list[tuple[
    str,
    float,
    str,
    list[audio_timing.WordTiming] | None,
  ]]]] = []
  for index, entry in enumerate(character_dialogs):
    try:
      character, dialogs = entry
    except (TypeError, ValueError) as exc:
      raise GenVideoError(
        f"Invalid character dialog entry at index {index}: {entry}") from exc

    transcript_by_key: dict[tuple[str, float], str] = {}
    timing_by_key: dict[tuple[str, float],
                        list[audio_timing.WordTiming] | None] = {}
    timed_audio: list[tuple[str, float]] = []
    for dialog_index, dialog_entry in enumerate(dialogs):
      try:
        gcs_uri, start_time, transcript, timing = dialog_entry
      except (TypeError, ValueError) as exc:
        raise GenVideoError(
          "Invalid dialog entry for character at index "
          f"{index} (dialog {dialog_index}): {dialog_entry}") from exc
      if transcript is None:
        raise GenVideoError(
          "Transcript must be provided for character dialog "
          f"{gcs_uri} @ {start_time} (character index {index})")
      transcript_str = str(transcript)
      key = (str(gcs_uri), float(start_time))
      if key in transcript_by_key and transcript_by_key[key] != transcript_str:
        raise GenVideoError(
          "Duplicate (gcs_uri, start_time) with different transcripts for "
          f"{gcs_uri} @ {start_time} (character index {index})")
      transcript_by_key[key] = transcript_str
      timing_by_key[key] = timing
      timed_audio.append((str(gcs_uri), float(start_time)))

    normalized_timed_audio = _normalize_timed_assets(
      timed_audio,
      label="character audio",
      allow_empty=True,
    )
    normalized_dialogs_with_transcripts = [
      (gcs_uri, start_time, transcript_by_key[(gcs_uri, start_time)],
       timing_by_key[(gcs_uri, start_time)])
      for (gcs_uri, start_time) in normalized_timed_audio
    ]
    normalized.append((character, normalized_dialogs_with_transcripts))

  return normalized


def _flatten_character_audio(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[
    str,
    float,
    str,
    list[audio_timing.WordTiming] | None,
  ]]]],
) -> list[tuple[str, float]]:
  """Flatten normalized character dialogs into `(gcs_uri, start_time)` audio."""
  flattened: list[tuple[str, float]] = []
  for _, dialogs in character_dialogs:
    flattened.extend(
      (gcs_uri, float(start_time)) for gcs_uri, start_time, _, _ in dialogs)
  return flattened

