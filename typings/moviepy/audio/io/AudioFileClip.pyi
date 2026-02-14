from __future__ import annotations


class AudioFileClip:
  start: float
  duration: float | None

  def __init__(self, filename: str) -> None:
    ...

  def with_start(self, start: float) -> AudioFileClip:
    ...

  def with_volume_scaled(self, factor: float) -> AudioFileClip:
    ...

  def with_duration(self, duration: float) -> AudioFileClip:
    ...

  def close(self) -> None:
    ...
