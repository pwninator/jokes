"""Mouth event generation using character-level timing data.

This module is kept as a thin wrapper for backwards compatibility.
Prefer `services.mouth_event_detection_tts_timing`.
"""

from __future__ import annotations

from common import audio_timing
from common.mouth_events import MouthEvent
from services.mouth_event_detection_tts_timing import detect_mouth_events_tts_timing


def detect_mouth_events_from_timing(
  timing: audio_timing.CharacterAlignment,
) -> list[MouthEvent]:
  return detect_mouth_events_tts_timing(timing)
