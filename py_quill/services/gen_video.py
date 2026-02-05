"""Video generation service using moviepy."""

from __future__ import annotations

import math
import os
import random
import tempfile
import time
import traceback
from bisect import bisect_right
from typing import Any

import numpy as np
from common import models, utils
from common.posable_character import MouthState, PosableCharacter
from firebase_functions import logger
from moviepy import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                     ImageClip, VideoClip)
from PIL import Image
from common.mouth_events import MouthEvent
from services import cloud_storage, syllable_detection

_DEFAULT_VIDEO_FPS = 24
_PORTRAIT_VIDEO_SIZE = (1080, 1920)
_PORTRAIT_IMAGE_SIZE = (1080, 1080)
_PORTRAIT_FOOTER_SIZE = (
  _PORTRAIT_VIDEO_SIZE[0],
  _PORTRAIT_VIDEO_SIZE[1] - _PORTRAIT_IMAGE_SIZE[1],
)


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
      image_download_start = time.perf_counter()
      image_paths = _download_assets_to_temp(
        normalized_images,
        temp_dir,
        prefix="image",
        default_extension=".png",
      )
      image_download_time = time.perf_counter() - image_download_start
      logger.info(
        f"Downloaded {len(image_paths)} images in {image_download_time:.2f}s")

      audio_download_start = time.perf_counter()
      audio_paths = _download_assets_to_temp(
        normalized_audio,
        temp_dir,
        prefix="audio",
        default_extension=".wav",
      )
      audio_download_time = time.perf_counter() - audio_download_start
      logger.info(
        f"Downloaded {len(audio_paths)} audio files in {audio_download_time:.2f}s"
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


def create_portrait_character_video(
  joke_images: list[tuple[str, float]],
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                                    str]]]],
  footer_background_gcs_uri: str,
  total_duration_sec: float,
  output_filename_base: str,
  temp_output: bool = False,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Create a portrait video with animated character(s) in the footer.

  Args:
    joke_images: List of (gcs_uri, start_time_sec) for joke images.
    character_dialogs: List of (character, [(audio_gcs_uri, start_time, transcript)]) pairs.
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

  normalized_images = _normalize_timed_assets(
    joke_images,
    label="image",
    allow_empty=False,
  )
  normalized_dialogs = _normalize_character_dialogs(character_dialogs)
  primary_dialog = _find_first_character_dialog(normalized_dialogs)

  # Side-by-side compare mode: render two instances of the first character,
  # one driven by librosa-based detection and one by parselmouth-based
  # detection. Audio is only included once.
  render_dialogs = normalized_dialogs
  flattened_audio: list[tuple[str, float]] = _flatten_character_audio(
    normalized_dialogs)
  if primary_dialog is not None:
    primary_character, primary_clips = primary_dialog
    render_dialogs = [
      (primary_character, primary_clips),
      (primary_character, primary_clips),
    ]
    flattened_audio = [(gcs_uri, start_time)
                       for gcs_uri, start_time, _ in primary_clips]

  normalized_audio = _normalize_timed_assets(
    flattened_audio,
    label="audio",
    allow_empty=True,
  )
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
    "Starting portrait video generation: "
    f"{len(normalized_images)} images, {len(normalized_audio)} audio files, "
    f"{len([c for c, _ in render_dialogs if c is not None])} characters, "
    f"duration={total_duration_sec}s, output={output_gcs_uri}")

  video_clip = None
  audio_composite = None
  audio_clips: list[AudioFileClip] = []

  try:
    with tempfile.TemporaryDirectory() as temp_dir:
      image_download_start = time.perf_counter()
      image_paths = _download_assets_to_temp(
        normalized_images,
        temp_dir,
        prefix="image",
        default_extension=".png",
      )
      image_download_time = time.perf_counter() - image_download_start
      logger.info(
        f"Downloaded {len(image_paths)} images in {image_download_time:.2f}s")

      audio_download_start = time.perf_counter()
      audio_paths = _download_assets_to_temp(
        normalized_audio,
        temp_dir,
        prefix="audio",
        default_extension=".wav",
      )
      audio_download_time = time.perf_counter() - audio_download_start
      logger.info(
        f"Downloaded {len(audio_paths)} audio files in {audio_download_time:.2f}s"
      )

      audio_path_by_key = {
        (gcs_uri, start_time): path
        for (gcs_uri, start_time), path in zip(normalized_audio, audio_paths)
      }
      syllable_start = time.perf_counter()
      syllable_data = _build_character_syllable_data(
        normalized_dialogs,
        audio_path_by_key,
      )
      mouth_timelines = [
        _apply_forced_closures(syllables) for syllables in syllable_data
      ]
      syllable_time = time.perf_counter() - syllable_start
      logger.info(
        f"Built syllable timing for {len(mouth_timelines)} dialogs in {syllable_time:.2f}s"
      )

      image_load_start = time.perf_counter()
      image_frames = _load_resized_images(
        normalized_images,
        image_paths,
        target_size=_PORTRAIT_IMAGE_SIZE,
      )
      image_load_time = time.perf_counter() - image_load_start
      logger.info(
        f"Prepared {len(image_frames)} resized images in {image_load_time:.2f}s"
      )
      footer_start = time.perf_counter()
      footer_background = _load_resized_image(
        footer_background_gcs_uri,
        target_size=_PORTRAIT_FOOTER_SIZE,
      )
      footer_time = time.perf_counter() - footer_start
      logger.info(
        f"Loaded footer background in {footer_time:.2f}s ({footer_background.size[0]}x{footer_background.size[1]})"
      )
      render_prep_start = time.perf_counter()
      character_renders = _prepare_character_renders(
        render_dialogs,
        footer_height=_PORTRAIT_FOOTER_SIZE[1],
        footer_width=_PORTRAIT_FOOTER_SIZE[0],
      )
      render_prep_time = time.perf_counter() - render_prep_start
      logger.info(
        f"Prepared {len(character_renders)} character renders in {render_prep_time:.2f}s"
      )

      total_frames = int(math.ceil(total_duration_sec * _DEFAULT_VIDEO_FPS))
      logger.info(f"Creating VideoClip renderer for {total_frames} frames")
      make_frame = _build_portrait_frame_renderer(
        images=image_frames,
        footer_background=footer_background,
        character_renders=character_renders,
        mouth_timelines=mouth_timelines,
        fps=_DEFAULT_VIDEO_FPS,
        total_duration_sec=total_duration_sec,
      )
      encode_start = time.perf_counter()
      video_clip = VideoClip(make_frame, duration=total_duration_sec)
      if audio_paths:
        audio_clips = _create_audio_clips(normalized_audio, audio_paths)
        audio_composite = CompositeAudioClip(audio_clips)
        video_clip = video_clip.with_audio(audio_composite)

      output_path = os.path.join(temp_dir, "portrait.mp4")
      logger.info(f"Writing video clip to {output_path}")
      video_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=_DEFAULT_VIDEO_FPS,
        logger=None,
      )
      encode_time = time.perf_counter() - encode_start
      logger.info(f"Encoded video in {encode_time:.2f}s")

      logger.info(f"Uploading video clip to {output_gcs_uri}")
      cloud_storage.upload_file_to_gcs(
        output_path,
        output_gcs_uri,
        content_type="video/mp4",
      )

      file_size_bytes = os.path.getsize(output_path)
      generation_time_sec = time.perf_counter() - start_time

      metadata = models.SingleGenerationMetadata(
        label="create_portrait_character_video",
        model_name="moviepy",
        token_counts={
          "num_images":
          len(normalized_images),
          "num_audio_files":
          len(normalized_audio),
          "num_characters":
          len([character for character, _ in render_dialogs if character]),
          "video_duration_sec":
          int(total_duration_sec),
          "output_file_size_bytes":
          file_size_bytes,
        },
        generation_time_sec=generation_time_sec,
        cost=0.0,
      )

      _log_video_response(
        normalized_images,
        normalized_audio,
        output_gcs_uri,
        metadata,
        extra_log_data={
          "num_characters":
          len([character for character, _ in normalized_dialogs if character]),
        },
      )
      return output_gcs_uri, metadata

  except Exception as e:
    logger.error("Portrait video generation failed:\n"
                 f"{traceback.format_exc()}")
    raise GenVideoError(f"Portrait video generation failed: {e}") from e
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
    logger.info(f"Downloading asset to temp directory: {gcs_uri}")
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


def _normalize_character_dialogs(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                                    str]]]]
) -> list[tuple[PosableCharacter | None, list[tuple[str, float, str]]]]:
  if character_dialogs is None:
    raise GenVideoError("character_dialogs must be provided")

  normalized: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                             str]]]] = []
  for index, entry in enumerate(character_dialogs):
    try:
      character, dialogs = entry
    except (TypeError, ValueError) as exc:
      raise GenVideoError(
        f"Invalid character dialog entry at index {index}: {entry}") from exc

    transcript_by_key: dict[tuple[str, float], str] = {}
    timed_audio: list[tuple[str, float]] = []
    for dialog_index, dialog_entry in enumerate(dialogs):
      try:
        gcs_uri, start_time, transcript = dialog_entry
      except (TypeError, ValueError) as exc:
        raise GenVideoError(
          "Invalid dialog entry for character at index "
          f"{index} (dialog {dialog_index}): {dialog_entry}") from exc
      if transcript is None:
        raise GenVideoError(
          "Transcript must be provided for character dialog "
          f"{gcs_uri} @ {start_time} (character index {index})")
      transcript_str = str(transcript)
      key = (gcs_uri, start_time)
      if key in transcript_by_key and transcript_by_key[key] != transcript_str:
        raise GenVideoError(
          "Duplicate (gcs_uri, start_time) with different transcripts for "
          f"{gcs_uri} @ {start_time} (character index {index})")
      transcript_by_key[key] = transcript_str
      timed_audio.append((gcs_uri, start_time))

    normalized_timed_audio = _normalize_timed_assets(
      timed_audio,
      label="character audio",
      allow_empty=True,
    )
    normalized_dialogs_with_transcripts = [
      (gcs_uri, start_time, transcript_by_key[(gcs_uri, start_time)])
      for (gcs_uri, start_time) in normalized_timed_audio
    ]
    normalized.append((character, normalized_dialogs_with_transcripts))
  return normalized


def _flatten_character_audio(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                                    str]]]]
) -> list[tuple[str, float]]:
  flattened: list[tuple[str, float]] = []
  for _, dialogs in character_dialogs:
    flattened.extend(
      (gcs_uri, start_time) for gcs_uri, start_time, _ in dialogs)
  return flattened


def _find_first_character_dialog(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                                    str]]]]
) -> tuple[PosableCharacter, list[tuple[str, float, str]]] | None:
  for character, dialogs in character_dialogs:
    if character is None:
      continue
    return character, dialogs
  return None


def _build_character_syllable_data(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                                    str]]]],
  audio_path_by_key: dict[tuple[str, float], str],
) -> list[list[MouthEvent]]:
  """Build syllable data for side-by-side compare of the first character.

  Args:
    character_dialogs: List of (character, [(audio_gcs_uri, start_time, transcript)]).
    audio_path_by_key: Map from (gcs_uri, start_time) to local file path.

  Returns:
    Two MouthEvent lists: [librosa_events, parselmouth_events].
  """
  primary = _find_first_character_dialog(character_dialogs)
  if primary is None:
    return [[], []]

  _character, dialogs = primary

  librosa_syllables: list[MouthEvent] = []
  parselmouth_syllables: list[MouthEvent] = []

  for gcs_uri, start_time, transcript in dialogs:
    audio_path = audio_path_by_key.get((gcs_uri, start_time))
    if not audio_path:
      raise GenVideoError("Missing audio path for character dialog "
                          f"{gcs_uri} @ {start_time}")
    with open(audio_path, "rb") as audio_handle:
      wav_bytes = audio_handle.read()

    logger.info(f"Detecting syllables (librosa + parselmouth) for {gcs_uri} @ {start_time}")
    librosa_clip, parselmouth_clip = syllable_detection.detect_syllables_for_lip_sync(
      wav_bytes,
      transcript=transcript,
    )

    for syllable in librosa_clip:
      librosa_syllables.append(
        MouthEvent(
          start_time=syllable.start_time + start_time,
          end_time=syllable.end_time + start_time,
          mouth_shape=syllable.mouth_shape,
          confidence=syllable.confidence,
          mean_centroid=syllable.mean_centroid,
          mean_rms=syllable.mean_rms,
        ))

    for syllable in parselmouth_clip:
      parselmouth_syllables.append(
        MouthEvent(
          start_time=syllable.start_time + start_time,
          end_time=syllable.end_time + start_time,
          mouth_shape=syllable.mouth_shape,
          confidence=syllable.confidence,
          mean_centroid=syllable.mean_centroid,
          mean_rms=syllable.mean_rms,
        ))

  librosa_syllables.sort(key=lambda entry: entry.start_time)
  parselmouth_syllables.sort(key=lambda entry: entry.start_time)

  return [librosa_syllables, parselmouth_syllables]


def _apply_forced_closures(
  syllables: list[MouthEvent],
  *,
  min_syllable_for_closure_sec: float = 0.05,
  closure_fraction: float = 0.25,
  min_closure_sec: float = 0.015,
  max_closure_sec: float = 0.04,
  max_gap_sec: float = 0.15,
) -> list[tuple[MouthState, float, float]]:
  """Apply forced mouth closures between consecutive same-shape syllables.

  This ensures each syllable has a visible effect by inserting brief CLOSED
  states between adjacent syllables with the same mouth shape.

  Args:
    syllables: List of detected syllables.
    min_syllable_for_closure_sec: Minimum syllable duration to consider for
      forced closures. Very short syllables skip closure insertion to avoid
      strobe effects.
    closure_fraction: Closure duration as a fraction of the shorter syllable.
    min_closure_sec: Minimum closure duration.
    max_closure_sec: Maximum closure duration.
    max_gap_sec: Maximum gap to insert a closure. Larger gaps are natural
      silence and don't need forced closures.

  Returns:
    Timeline of (MouthState, start_time, end_time) tuples, sorted by start_time.
  """
  if not syllables:
    return []

  timeline: list[tuple[MouthState, float, float]] = []

  for index, syllable in enumerate(syllables):
    syl_start = syllable.start_time
    syl_end = syllable.end_time
    syl_duration = syl_end - syl_start

    # Check if we need to insert a closure before this syllable
    if index > 0:
      prev_syllable = syllables[index - 1]
      prev_duration = prev_syllable.end_time - prev_syllable.start_time
      gap = syl_start - prev_syllable.end_time

      # Conditions for inserting a forced closure:
      # 1. Same mouth shape as previous syllable
      # 2. Both syllables are long enough to warrant closure
      # 3. Gap is not too large (natural silence doesn't need forced closure)
      should_insert_closure = (
        syllable.mouth_shape == prev_syllable.mouth_shape
        and syl_duration >= min_syllable_for_closure_sec
        and prev_duration >= min_syllable_for_closure_sec
        and gap <= max_gap_sec)

      if should_insert_closure:
        # Calculate dynamic closure duration based on shorter syllable
        shorter_duration = min(syl_duration, prev_duration)
        closure_duration = shorter_duration * closure_fraction
        closure_duration = max(min_closure_sec,
                               min(closure_duration, max_closure_sec))

        if gap >= closure_duration:
          # Enough space in the gap - place closure in the middle
          mid_point = prev_syllable.end_time + gap / 2
          closure_start = mid_point - closure_duration / 2
          closure_end = mid_point + closure_duration / 2
          timeline.append((MouthState.CLOSED, closure_start, closure_end))
        elif gap >= 0:
          # Not enough gap - steal time from both syllables
          needed_space = closure_duration - gap
          steal_each = needed_space / 2

          # Shrink previous syllable's end (already added to timeline)
          if timeline and timeline[-1][0] == prev_syllable.mouth_shape:
            prev_entry = timeline[-1]
            new_prev_end = prev_entry[2] - steal_each
            if new_prev_end > prev_entry[1] + min_syllable_for_closure_sec:
              timeline[-1] = (prev_entry[0], prev_entry[1], new_prev_end)
              # Insert closure
              closure_start = new_prev_end
              closure_end = closure_start + closure_duration
              timeline.append((MouthState.CLOSED, closure_start, closure_end))
              # Adjust current syllable start
              syl_start = closure_end

    timeline.append((syllable.mouth_shape, syl_start, syl_end))

  timeline.sort(key=lambda entry: entry[1])
  return timeline


def _load_resized_images(
  images: list[tuple[str, float]],
  image_paths: list[str],
  *,
  target_size: tuple[int, int],
) -> list[tuple[float, Image.Image]]:
  frames: list[tuple[float, Image.Image]] = []
  for (_, start_time), image_path in zip(images, image_paths):
    with Image.open(image_path) as image:
      frames.append((start_time, _resize_image(image, target_size)))
  return frames


def _load_resized_image(gcs_uri: str, *,
                        target_size: tuple[int, int]) -> Image.Image:
  image = cloud_storage.download_image_from_gcs(gcs_uri).convert("RGBA")
  return _resize_image(image, target_size)


def _resize_image(image: Image.Image, target_size: tuple[int,
                                                         int]) -> Image.Image:
  if image.size == target_size:
    return image.convert("RGBA")
  return image.convert("RGBA").resize(
    target_size,
    resample=Image.Resampling.LANCZOS,
  )


def _prepare_character_renders(
  character_dialogs: list[tuple[PosableCharacter | None, list[tuple[str, float,
                                                                    str]]]],
  *,
  footer_height: int,
  footer_width: int,
) -> list[dict[str, Any]]:
  characters = [
    character for character, _ in character_dialogs if character is not None
  ]
  logger.info(f"Preparing character renders for {len(characters)} characters")
  if not characters:
    return []

  spacing = footer_width / (len(characters) + 1)
  centers = [spacing * (index + 1) for index in range(len(characters))]

  renders: list[dict[str, Any]] = []
  center_index = 0
  for dialog_index, (character, _dialogs) in enumerate(character_dialogs):
    if character is None:
      continue
    center_x = centers[center_index]
    center_index += 1
    mouth_images = _build_character_images(character, max_height=footer_height)
    width, height = mouth_images[MouthState.OPEN].size
    x = int(round(center_x - (width / 2)))
    y = int(round((footer_height - height) / 2))
    renders.append({
      "character": character,
      "mouth_images": mouth_images,
      "position": (x, y),
      "dialog_index": dialog_index,
    })
  return renders


def _build_character_images(
  character: PosableCharacter,
  *,
  max_height: int,
) -> dict[MouthState, Image.Image]:
  images: dict[MouthState, Image.Image] = {}
  for mouth_state in (MouthState.CLOSED, MouthState.OPEN, MouthState.O):
    character.set_pose(mouth_state=mouth_state)
    rendered = character.get_image()
    if rendered.height > max_height:
      scale = max_height / rendered.height
      target_size = (max(1, int(round(rendered.width * scale))),
                     max(1, int(round(rendered.height * scale))))
      rendered = rendered.resize(target_size, Image.Resampling.LANCZOS)
    images[mouth_state] = rendered
  return images


def _build_portrait_frame_renderer(
  *,
  images: list[tuple[float, Image.Image]],
  footer_background: Image.Image,
  character_renders: list[dict[str, Any]],
  mouth_timelines: list[list[tuple[MouthState, float, float]]],
  fps: int,
  total_duration_sec: float,
) -> callable:
  if fps <= 0:
    raise GenVideoError("FPS must be positive")

  base_frames = _build_portrait_base_frames(images, footer_background)
  base_starts = [start for start, _ in base_frames]
  timing_index = _build_mouth_timeline_index(mouth_timelines)
  total_frames = int(math.ceil(total_duration_sec * fps))
  progress_interval = 50
  last_logged = {"frame": -1}

  def make_frame(time_sec: float) -> np.ndarray:
    base_index = bisect_right(base_starts, time_sec) - 1
    if base_index < 0:
      base_index = 0
    base = base_frames[base_index][1].copy()

    for render in character_renders:
      dialog_index = render["dialog_index"]
      starts, ends, states = timing_index[dialog_index]
      mouth_state = MouthState.CLOSED
      if starts:
        idx = bisect_right(starts, time_sec) - 1
        if idx >= 0 and time_sec <= ends[idx]:
          mouth_state = states[idx]
      image = render["mouth_images"].get(mouth_state)
      if image is None:
        image = render["mouth_images"][MouthState.CLOSED]
      x, y = render["position"]
      base.paste(
        image,
        (x, _PORTRAIT_IMAGE_SIZE[1] + y),
        image,
      )

    frame_index = int(time_sec * fps)
    if frame_index >= 0 and frame_index - last_logged[
        "frame"] >= progress_interval:
      last_logged["frame"] = frame_index
      logger.info(
        f"Rendered {min(frame_index + 1, total_frames)}/{total_frames} frames "
        f"({min(frame_index + 1, total_frames) / total_frames:.0%})")

    return np.asarray(base.convert("RGB"))

  return make_frame


def _build_portrait_base_frames(
  images: list[tuple[float, Image.Image]],
  footer_background: Image.Image,
) -> list[tuple[float, Image.Image]]:
  base_frames: list[tuple[float, Image.Image]] = []
  for start_time, image in images:
    base = Image.new("RGBA", _PORTRAIT_VIDEO_SIZE, (0, 0, 0, 0))
    base.paste(image, (0, 0))
    base.paste(footer_background, (0, _PORTRAIT_IMAGE_SIZE[1]))
    base_frames.append((start_time, base))
  return base_frames


def _build_mouth_timeline_index(
  mouth_timelines: list[list[tuple[MouthState, float, float]]]
) -> list[tuple[list[float], list[float], list[MouthState]]]:
  index: list[tuple[list[float], list[float], list[MouthState]]] = []
  for timeline in mouth_timelines:
    starts = [start for _, start, _ in timeline]
    ends = [end for _, _, end in timeline]
    states = [state for state, _, _ in timeline]
    index.append((starts, ends, states))
  return index
