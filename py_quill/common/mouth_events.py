"""Timed mouth-shape events for lip-sync animation."""

from __future__ import annotations

from dataclasses import dataclass

from common.posable_character import MouthState


@dataclass(frozen=True)
class MouthEvent:
  """A timed mouth-shape segment, optionally with audio-derived metadata."""

  start_time: float
  end_time: float
  mouth_shape: MouthState
  confidence: float | None = None
  mean_centroid: float | None = None
  mean_rms: float | None = None

