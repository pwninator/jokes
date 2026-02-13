from __future__ import annotations

from collections.abc import Sequence

from moviepy.audio.io.AudioFileClip import AudioFileClip


class CompositeAudioClip:

  def __init__(self, clips: Sequence[AudioFileClip]) -> None:
    ...

  def close(self) -> None:
    ...
