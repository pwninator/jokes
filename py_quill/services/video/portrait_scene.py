"""Portrait joke video rendering via scriptable scene infrastructure (phase 1)."""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from random import Random

import numpy as np
from common import models
from common.mouth_events import MouthEvent
from common.posable_character import MouthState, PosableCharacter, Transform
from moviepy import AudioFileClip, CompositeAudioClip, VideoClip
from PIL import Image, ImageDraw, ImageFont
from services import cloud_storage, mouth_event_detection
from services.video import mouth as mouth_utils
from services.video.script import (CharacterTrackSpec, PortraitJokeVideoScript,
                                   PortraitMouthTestVideoScript)
from services.video.timeline import SegmentTimeline

_DEFAULT_VIDEO_FPS = 24
_PORTRAIT_VIDEO_SIZE = (1080, 1920)
_PORTRAIT_IMAGE_SIZE = (1080, 1080)
_PORTRAIT_FOOTER_SIZE = (
  _PORTRAIT_VIDEO_SIZE[0],
  _PORTRAIT_VIDEO_SIZE[1] - _PORTRAIT_IMAGE_SIZE[1],
)


@dataclass(frozen=True)
class _CharacterRender:
  """Resolved per-character render state used by frame generation.

  These timelines are precomputed once so `make_frame` only samples state and
  asks the character to render that pose.
  """
  character: PosableCharacter
  position: tuple[int, int]  # in footer coordinates (0,0 at footer top-left)
  mouth_timeline: SegmentTimeline[MouthState]
  scale: float
  blink_timeline: SegmentTimeline[bool]
  left_hand_timeline: SegmentTimeline[Transform]
  right_hand_timeline: SegmentTimeline[Transform]


@dataclass(frozen=True)
class _GridRender:
  """Resolved character state for the diagnostic mouth-test grid."""
  character: PosableCharacter
  position: tuple[int, int]  # absolute canvas position
  mouth_timeline: SegmentTimeline[MouthState]
  scale: float


def _resize_image(image: Image.Image, target_size: tuple[int,
                                                         int]) -> Image.Image:
  """Convert to RGBA and resize only when dimensions do not already match."""
  if image.size == target_size:
    return image.convert("RGBA")
  return image.convert("RGBA").resize(target_size,
                                      resample=Image.Resampling.LANCZOS)


def _build_mouth_timeline_for_character(
  character_spec: CharacterTrackSpec,
  *,
  forced_closures: bool,
) -> SegmentTimeline[MouthState]:
  """Build a global mouth timeline from dialog-local timings.

  Each clip's detected mouth events are offset by the clip start time so a
  character can have multiple non-contiguous dialog segments in one timeline.
  """
  syllables: list[MouthEvent] = []
  for dialog in character_spec.dialogs:
    if not dialog.timing:
      continue
    clip_events = mouth_event_detection.detect_mouth_events(
      b"",
      mode="timing",
      transcript=dialog.transcript,
      timing=dialog.timing,
    )
    for event in clip_events:
      syllables.append(
        MouthEvent(
          start_time=float(event.start_time) + float(dialog.start_time_sec),
          end_time=float(event.end_time) + float(dialog.start_time_sec),
          mouth_shape=event.mouth_shape,
          confidence=event.confidence,
          mean_centroid=event.mean_centroid,
          mean_rms=event.mean_rms,
        ))

  syllables.sort(key=lambda entry: float(entry.start_time))
  if not syllables:
    return SegmentTimeline()

  if forced_closures:
    segments = mouth_utils.apply_forced_closures(syllables)
  else:
    segments = [(s.mouth_shape, s.start_time, s.end_time) for s in syllables]

  return SegmentTimeline.from_value_segments(segments)


def _prepare_character_renders(
  characters: list[CharacterTrackSpec],
  *,
  footer_height: int,
  footer_width: int,
  forced_closures: bool,
  duration_sec: float,
  blink_seed: int,
  enable_blinking: bool,
  drum_window: tuple[float, float] | None,
) -> list[_CharacterRender]:
  """Layout characters and precompute all per-character timelines.

  The returned list is frame-loop ready: x/y placement, scale, mouth state,
  optional blink schedule, and optional hand transforms for drumming.
  """
  if not characters:
    return []

  spacing = footer_width / (len(characters) + 1)
  centers = [spacing * (index + 1) for index in range(len(characters))]

  renders: list[_CharacterRender] = []
  for index, spec in enumerate(characters):
    character = spec.character
    center_x = float(centers[index])
    # Pre-warm component cache (and pose cache for the default pose).
    try:
      character.get_image()
    except Exception:
      # Rendering will raise again later; keep this warm-up best-effort.
      pass

    mouth_timeline = _build_mouth_timeline_for_character(
      spec,
      forced_closures=forced_closures,
    )

    # Use OPEN pose to measure size.
    character.set_pose(mouth_state=MouthState.OPEN)
    rendered = character.get_image()
    scale = 1.0
    if rendered.height > footer_height:
      scale = footer_height / float(rendered.height)
      target_size = (
        max(1, int(round(rendered.width * scale))),
        max(1, int(round(rendered.height * scale))),
      )
      rendered = rendered.resize(target_size, Image.Resampling.LANCZOS)

    x = int(round(center_x - (rendered.width / 2)))
    y = int(round((footer_height - rendered.height) / 2))

    blink_timeline = (SegmentTimeline()
                      if not enable_blinking else _build_blink_timeline(
                        duration_sec=float(duration_sec),
                        seed=int(blink_seed) + int(index),
                      ))

    left_hand_timeline = SegmentTimeline()
    right_hand_timeline = SegmentTimeline()
    if drum_window is not None:
      drum_start, drum_end = drum_window
      left_hand_timeline, right_hand_timeline = _build_drumming_hand_timelines(
        start_time_sec=float(drum_start),
        end_time_sec=float(drum_end),
      )

    renders.append(
      _CharacterRender(
        character=character,
        position=(x, y),
        mouth_timeline=mouth_timeline,
        scale=scale,
        blink_timeline=blink_timeline,
        left_hand_timeline=left_hand_timeline,
        right_hand_timeline=right_hand_timeline,
      ))
  return renders


def _active_timed_image(
  images: list[tuple[float, Image.Image]],
  time_sec: float,
) -> Image.Image:
  """Return the last image whose start time is <= `time_sec`."""
  # images are sorted by start_time
  active = images[0][1]
  for start, image in images:
    if time_sec >= float(start):
      active = image
    else:
      break
  return active


def _render_portrait_frame(
  *,
  time_sec: float,
  joke_images: list[tuple[float, Image.Image]],
  footer_background: Image.Image,
  character_renders: list[_CharacterRender],
) -> np.ndarray:
  """Render one portrait frame at `time_sec`.

  Composition order is stable: active joke image, footer background, then
  character sprites. This keeps character overlays deterministic.
  """
  base = Image.new("RGBA", _PORTRAIT_VIDEO_SIZE, (0, 0, 0, 0))
  active_image = _active_timed_image(joke_images, time_sec)
  base.paste(active_image, (0, 0))
  base.paste(footer_background, (0, _PORTRAIT_IMAGE_SIZE[1]))

  for render in character_renders:
    mouth_state = render.mouth_timeline.value_at(
      time_sec,
      default=MouthState.CLOSED,
    )
    eyes_open = render.blink_timeline.value_at(time_sec, default=True)
    left_hand_transform = render.left_hand_timeline.value_at(
      time_sec, default=Transform())
    right_hand_transform = render.right_hand_timeline.value_at(
      time_sec, default=Transform())
    render.character.set_pose(
      mouth_state=mouth_state,
      left_eye_open=eyes_open,
      right_eye_open=eyes_open,
      left_hand_transform=left_hand_transform,
      right_hand_transform=right_hand_transform,
    )
    sprite = render.character.get_image()
    x, y = render.position
    if render.scale != 1.0:
      target_size = (
        max(1, int(round(sprite.width * render.scale))),
        max(1, int(round(sprite.height * render.scale))),
      )
      sprite = sprite.resize(target_size, Image.Resampling.LANCZOS)
    base.paste(sprite, (x, _PORTRAIT_IMAGE_SIZE[1] + y), sprite)

  return np.asarray(base.convert("RGB"))


def _download_audio_to_temp(
  audio_files: list[tuple[str, float]],
  *,
  temp_dir: str,
) -> list[tuple[str, float, str]]:
  """Download GCS audio files and return `(gcs_uri, start_time, local_path)`."""
  out: list[tuple[str, float, str]] = []
  for index, (gcs_uri, start_time) in enumerate(audio_files):
    _, blob_name = cloud_storage.parse_gcs_uri(gcs_uri)
    extension = os.path.splitext(blob_name)[1] or ".wav"
    local_path = os.path.join(temp_dir, f"audio_{index}{extension}")
    content_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)
    with open(local_path, "wb") as file_handle:
      file_handle.write(content_bytes)
    out.append((gcs_uri, float(start_time), local_path))
  return out


def _build_audio_clips(
  audio_paths: list[tuple[str, float, str]], ) -> list[AudioFileClip]:
  """Create started `AudioFileClip` objects from downloaded audio paths."""
  clips: list[AudioFileClip] = []
  for _gcs_uri, start_time, path in audio_paths:
    clips.append(AudioFileClip(path).with_start(float(start_time)))
  return clips


def _build_blink_timeline(
  *,
  duration_sec: float,
  seed: int,
  min_interval_sec: float = 3.0,
  max_interval_sec: float = 5.0,
  blink_duration_sec: float = 0.12,
) -> SegmentTimeline[bool]:
  """Return a timeline that is False during blink windows.

  Uses a deterministic RNG seeded by the caller so tests and rerenders are
  stable. The first blink is jittered slightly to avoid synchronized blinking
  across characters that share the same intervals.
  """
  duration_sec = float(duration_sec)
  if duration_sec <= 0:
    return SegmentTimeline()

  rng = Random(int(seed))
  t = float(rng.uniform(1.0, 2.0))
  segments: list[tuple[bool, float, float]] = []
  while t < duration_sec:
    t0 = float(t)
    t1 = min(duration_sec, t0 + float(blink_duration_sec))
    if t1 > t0:
      segments.append((False, t0, t1))
    t = t0 + float(
      rng.uniform(float(min_interval_sec), float(max_interval_sec)))
  return SegmentTimeline.from_value_segments(segments)


def _build_drumming_hand_timelines(
  *,
  start_time_sec: float,
  end_time_sec: float,
  step_sec: float = 0.10,
  amplitude_px: float = 10.0,
) -> tuple[SegmentTimeline[Transform], SegmentTimeline[Transform]]:
  """Build opposed hand motion timelines for a short "drumming" animation.

  Left and right hands alternate between up/down transforms on each step so
  they move in opposite directions over the window.
  """
  start_time_sec = float(start_time_sec)
  end_time_sec = float(end_time_sec)
  if end_time_sec <= start_time_sec:
    return SegmentTimeline(), SegmentTimeline()

  step_sec = max(0.02, float(step_sec))
  up = Transform(translate_y=-float(amplitude_px))
  down = Transform(translate_y=float(amplitude_px))

  left_segments: list[tuple[Transform, float, float]] = []
  right_segments: list[tuple[Transform, float, float]] = []
  i = 0
  t = start_time_sec
  while t < end_time_sec:
    t0 = float(t)
    t1 = min(end_time_sec, t0 + step_sec)
    if t1 <= t0:
      break
    left_value = up if (i % 2 == 0) else down
    right_value = down if (i % 2 == 0) else up
    left_segments.append((left_value, t0, t1))
    right_segments.append((right_value, t0, t1))
    t = t1
    i += 1

  return (
    SegmentTimeline.from_value_segments(left_segments),
    SegmentTimeline.from_value_segments(right_segments),
  )


def _load_font(*, size: int) -> ImageFont.ImageFont:
  """Load a readable sans font with safe fallback for server environments."""
  try:
    return ImageFont.truetype("DejaVuSans.ttf", size=size)
  except Exception:
    return ImageFont.load_default()


def _tile_background(
  *,
  tile: Image.Image,
  target_size: tuple[int, int],
) -> Image.Image:
  """Repeat `tile` vertically to fill `target_size`."""
  base = Image.new("RGBA", target_size, (0, 0, 0, 255))
  y = 0
  while y < target_size[1]:
    base.paste(tile, (0, y))
    y += tile.size[1]
  return base


def generate_portrait_joke_video(
  *,
  script: PortraitJokeVideoScript,
  output_gcs_uri: str,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Generate the portrait joke video defined by `script`.

  Phase-1 behavior intentionally enables deterministic blinking and appends a
  fixed 2-second drumming window at the tail of the clip.
  """
  total_duration_sec = float(script.duration_sec)
  fps = int(script.fps or _DEFAULT_VIDEO_FPS)
  if fps <= 0:
    raise ValueError("FPS must be positive")

  start_perf = 0.0
  video_clip = None
  audio_composite = None
  audio_clips: list[AudioFileClip] = []

  try:
    start_perf = float(time.perf_counter())
    with tempfile.TemporaryDirectory() as temp_dir:
      # Assets
      joke_images: list[tuple[float, Image.Image]] = []
      for entry in script.joke_images:
        image = cloud_storage.download_image_from_gcs(
          entry.gcs_uri).convert("RGBA")
        joke_images.append((float(entry.start_time_sec),
                            _resize_image(image, _PORTRAIT_IMAGE_SIZE)))
      joke_images.sort(key=lambda item: float(item[0]))

      footer_background = cloud_storage.download_image_from_gcs(
        script.footer_background_gcs_uri).convert("RGBA")
      footer_background = _resize_image(footer_background,
                                        _PORTRAIT_FOOTER_SIZE)

      drum_end = float(total_duration_sec)
      drum_start = max(0.0, float(drum_end) - 2.0)
      character_renders = _prepare_character_renders(
        script.characters,
        footer_height=_PORTRAIT_FOOTER_SIZE[1],
        footer_width=_PORTRAIT_FOOTER_SIZE[0],
        forced_closures=True,
        duration_sec=total_duration_sec,
        blink_seed=int(script.seed),
        enable_blinking=True,
        drum_window=(drum_start, drum_end),
      )

      # Audio
      flattened_audio: list[tuple[str, float]] = []
      for spec in script.characters:
        flattened_audio.extend(
          (dialog.audio_gcs_uri, float(dialog.start_time_sec))
          for dialog in spec.dialogs)
      flattened_audio.sort(key=lambda item: float(item[1]))
      audio_paths = _download_audio_to_temp(flattened_audio, temp_dir=temp_dir)

      make_frame = lambda t: _render_portrait_frame(
        time_sec=float(t),
        joke_images=joke_images,
        footer_background=footer_background,
        character_renders=character_renders,
      )

      video_clip = VideoClip(make_frame, duration=total_duration_sec)
      if audio_paths:
        audio_clips = _build_audio_clips(audio_paths)
        audio_composite = CompositeAudioClip(audio_clips)
        video_clip = video_clip.with_audio(audio_composite)

      output_path = os.path.join(temp_dir, "portrait.mp4")
      video_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        logger=None,
      )

      cloud_storage.upload_file_to_gcs(
        output_path,
        output_gcs_uri,
        content_type="video/mp4",
      )

      file_size_bytes = os.path.getsize(output_path)
      generation_time_sec = float(time.perf_counter()) - float(start_perf)

      metadata = models.SingleGenerationMetadata(
        label="create_portrait_character_video",
        model_name="moviepy",
        token_counts={
          "num_images": len(script.joke_images),
          "num_audio_files": len(flattened_audio),
          "num_characters": len(script.characters),
          "video_duration_sec": int(total_duration_sec),
          "output_file_size_bytes": file_size_bytes,
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


def generate_portrait_mouth_test_video(
  *,
  script: PortraitMouthTestVideoScript,
  output_gcs_uri: str,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Generate a diagnostic grid for timing-based mouth animation.

  The output compares raw timing and timing+forced-closure variants with shared
  audio so mouth behavior differences can be inspected visually.
  """
  total_duration_sec = float(script.duration_sec)
  fps = int(script.fps or _DEFAULT_VIDEO_FPS)
  if fps <= 0:
    raise ValueError("FPS must be positive")

  # Two rows: raw timing vs timing+forced closures.
  variants = [
    {
      "label": "timing | forced=off",
      "forced_closures": False
    },
    {
      "label": "timing | forced=on",
      "forced_closures": True
    },
  ]

  video_clip = None
  audio_composite = None
  audio_clips: list[AudioFileClip] = []

  try:
    start_perf = float(time.perf_counter())
    with tempfile.TemporaryDirectory() as temp_dir:
      footer_background = cloud_storage.download_image_from_gcs(
        script.footer_background_gcs_uri).convert("RGBA")
      footer_background = _resize_image(footer_background,
                                        _PORTRAIT_FOOTER_SIZE)

      row_height = _PORTRAIT_VIDEO_SIZE[1] / float(len(variants))
      background = _tile_background(tile=footer_background,
                                    target_size=_PORTRAIT_VIDEO_SIZE)

      # Build mouth timelines and renders for each (row, character).
      label_width = 360
      usable_width = max(1, _PORTRAIT_VIDEO_SIZE[0] - label_width)
      spacing = usable_width / (len(script.characters) + 1)
      centers = [
        label_width + spacing * (index + 1)
        for index in range(len(script.characters))
      ]
      char_max_height = max(10, int(row_height - 8))

      renders: list[_GridRender] = []
      for row_index, variant in enumerate(variants):
        forced = bool(variant["forced_closures"])
        for char_index, spec in enumerate(script.characters):
          character = spec.character
          mouth_timeline = _build_mouth_timeline_for_character(
            spec,
            forced_closures=forced,
          )
          character.set_pose(mouth_state=MouthState.OPEN)
          rendered = character.get_image()
          scale = 1.0
          if rendered.height > char_max_height:
            scale = char_max_height / float(rendered.height)

          target_width = float(rendered.width) * float(scale)
          target_height = float(rendered.height) * float(scale)
          x = int(round(float(centers[char_index]) - (target_width / 2)))
          y = int(
            round(row_index * row_height + (row_height - target_height) / 2))
          renders.append(
            _GridRender(
              character=character,
              position=(x, y),
              mouth_timeline=mouth_timeline,
              scale=scale,
            ))

      # Draw row labels.
      draw = ImageDraw.Draw(background)
      font = _load_font(size=22)
      for row_index, variant in enumerate(variants):
        label = str(variant["label"])
        y = int(round(row_index * row_height + 14))
        draw.text((12, y), label, font=font, fill=(255, 255, 255, 255))

      # Audio: include all dialog audio clips once (flattened).
      flattened_audio: list[tuple[str, float]] = []
      for spec in script.characters:
        flattened_audio.extend(
          (dialog.audio_gcs_uri, float(dialog.start_time_sec))
          for dialog in spec.dialogs)
      flattened_audio.sort(key=lambda item: float(item[1]))
      audio_paths = _download_audio_to_temp(flattened_audio, temp_dir=temp_dir)

      def make_frame(time_sec: float) -> np.ndarray:
        base = background.copy()
        for render in renders:
          mouth_state = render.mouth_timeline.value_at(
            time_sec,
            default=MouthState.CLOSED,
          )
          render.character.set_pose(mouth_state=mouth_state)
          sprite = render.character.get_image()
          if render.scale != 1.0:
            target_size = (
              max(1, int(round(sprite.width * render.scale))),
              max(1, int(round(sprite.height * render.scale))),
            )
            sprite = sprite.resize(target_size, Image.Resampling.LANCZOS)
          x, y = render.position
          base.paste(sprite, (x, y), sprite)
        return np.asarray(base.convert("RGB"))

      video_clip = VideoClip(make_frame, duration=total_duration_sec)
      if audio_paths:
        audio_clips = _build_audio_clips(audio_paths)
        audio_composite = CompositeAudioClip(audio_clips)
        video_clip = video_clip.with_audio(audio_composite)

      output_path = os.path.join(temp_dir, "portrait_test.mp4")
      video_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        logger=None,
      )

      cloud_storage.upload_file_to_gcs(
        output_path,
        output_gcs_uri,
        content_type="video/mp4",
      )

      file_size_bytes = os.path.getsize(output_path)
      generation_time_sec = float(time.perf_counter()) - float(start_perf)
      metadata = models.SingleGenerationMetadata(
        label="create_portrait_character_test_video",
        model_name="moviepy",
        token_counts={
          "num_audio_files": len(flattened_audio),
          "num_characters": len(script.characters) * len(variants),
          "num_rows": len(variants),
          "video_duration_sec": int(total_duration_sec),
          "output_file_size_bytes": file_size_bytes,
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
