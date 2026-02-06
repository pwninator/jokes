"""Mouth event detection entrypoint.

`detect_mouth_events()` delegates to a specific detection methodology based on
the provided `mode`.
"""

from __future__ import annotations

from common import audio_timing
from common.mouth_events import MouthEvent
from services import transcript_alignment
from services.mouth_event_detection_librosa import detect_mouth_events_librosa
from services.mouth_event_detection_parselmouth import \
    detect_mouth_events_parselmouth
from services.mouth_event_detection_tts_timing import \
    detect_mouth_events_tts_timing


def detect_mouth_events(
  wav_bytes: bytes,
  *,
  mode: str,
  transcript: str | None = None,
  timing: list[audio_timing.WordTiming] | None = None,
) -> list[MouthEvent]:
  """Detect mouth events for lip-sync animation.

  Args:
    wav_bytes: WAV audio data (required for audio-based modes).
    mode: One of: "librosa", "parselmouth", "timing".
    transcript: Optional transcript for audio-to-text refinement.
    timing: Optional word timings (required for "timing").

  Returns:
    List of MouthEvent objects sorted by start_time.
  """
  if mode in ("timing", "tts_timing"):
    if timing is None:
      return []
    return detect_mouth_events_tts_timing(timing)

  if mode == "librosa":
    segments = detect_mouth_events_librosa(wav_bytes)
  elif mode == "parselmouth":
    segments = detect_mouth_events_parselmouth(wav_bytes)
  else:
    raise ValueError(f"Unknown mouth detection mode: {mode}")

  if not segments:
    return []

  transcript = transcript.strip() if transcript else ""
  if not transcript:
    return segments

  return transcript_alignment.align_with_text(transcript, segments)
