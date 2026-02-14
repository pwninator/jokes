from __future__ import annotations

from collections.abc import Sequence

from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.video.VideoClip import ImageClip


class CompositeVideoClip:

  def __init__(
    self,
    clips: Sequence[ImageClip],
    size: tuple[int, int] | None = ...,
  ) -> None:
    ...

  def with_duration(self, duration: float) -> CompositeVideoClip:
    ...

  def with_audio(self, audio: CompositeAudioClip) -> CompositeVideoClip:
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
