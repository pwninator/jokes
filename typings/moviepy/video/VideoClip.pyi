from __future__ import annotations

from collections.abc import Callable

from moviepy.audio.AudioClip import CompositeAudioClip


class ImageClip:
  size: tuple[int, int]

  def __init__(self, img: str) -> None:
    ...

  def with_start(self, t: float) -> ImageClip:
    ...

  def with_duration(self, duration: float) -> ImageClip:
    ...

  def resized(self, *, new_size: tuple[int, int]) -> ImageClip:
    ...

  def close(self) -> None:
    ...


class VideoClip:

  def __init__(
    self,
    make_frame: Callable[[float], object],
    duration: float | None = ...,
  ) -> None:
    ...

  def with_audio(self, audio: CompositeAudioClip) -> VideoClip:
    ...

  def write_videofile(
    self,
    filename: str,
    *,
    codec: str = ...,
    audio_codec: str = ...,
    fps: int = ...,
    logger: object | None = ...,
  ) -> None:
    ...

  def close(self) -> None:
    ...
