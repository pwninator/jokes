from __future__ import annotations

from unittest.mock import patch

import pytest
from common import models
from common.posable_character import PosableCharacter
from common.posable_character_sequence import (PosableCharacterSequence,
                                               SequenceSoundEvent)
from PIL import Image
from services import audio_voices
from services.video import joke_video_chars_on_top_script_builder, script_utils
from services.video.script import TimedCharacterSequence, TimedImage


class _SizedCharacter(PosableCharacter):

  def __init__(self, *, width: int, height: int):
    super().__init__(definition=models.PosableCharacterDef(
      width=width,
      height=height,
      head_gcs_uri="gs://test/head.png",
      surface_line_gcs_uri="gs://test/surface_line.png",
      left_hand_gcs_uri="gs://test/left_hand.png",
      right_hand_gcs_uri="gs://test/right_hand.png",
      mouth_open_gcs_uri="gs://test/mouth_open.png",
      mouth_closed_gcs_uri="gs://test/mouth_closed.png",
      mouth_o_gcs_uri="gs://test/mouth_o.png",
      left_eye_open_gcs_uri="gs://test/left_eye_open.png",
      left_eye_closed_gcs_uri="gs://test/left_eye_closed.png",
      right_eye_open_gcs_uri="gs://test/right_eye_open.png",
      right_eye_closed_gcs_uri="gs://test/right_eye_closed.png",
    ))
    self._size: tuple[int, int] = (width, height)

  def get_image(self) -> Image.Image:
    return Image.new("RGBA", self._size, (0, 0, 0, 255))


def _sound_sequence(duration_sec: float,
                    gcs_uri: str) -> PosableCharacterSequence:
  sequence = PosableCharacterSequence(sequence_sound_events=[
    SequenceSoundEvent(
      start_time=0.0,
      end_time=duration_sec,
      gcs_uri=gcs_uri,
      volume=1.0,
    )
  ])
  sequence.validate()
  return sequence


def _load_firestore_sequence(
  sequence_id: str = script_utils.POP_IN_SEQUENCE_ID
) -> PosableCharacterSequence:
  if sequence_id == script_utils.POP_IN_SEQUENCE_ID:
    return _sound_sequence(0.1, "gs://bucket/pop_in.wav")
  if sequence_id == "GEMINI_LEDA_giggle1":
    return _sound_sequence(0.3, "gs://bucket/leda_giggle.wav")
  if sequence_id == "GEMINI_PUCK_giggle1":
    return _sound_sequence(0.3, "gs://bucket/puck_giggle.wav")
  raise AssertionError(f"Unexpected sequence id: {sequence_id}")


def test_chars_on_top_layout_lowers_image_and_uses_footer_margin():
  teller = _SizedCharacter(width=220, height=300)
  listener = _SizedCharacter(width=140, height=220)
  with patch.object(
      script_utils,
      "load_sequence_from_firestore",
      side_effect=_load_firestore_sequence,
  ), patch.object(script_utils.random, "randint", return_value=1):
    script = joke_video_chars_on_top_script_builder.build_script(
      setup_image_gcs_uri="gs://bucket/setup.png",
      punchline_image_gcs_uri="gs://bucket/punchline.png",
      teller_character=teller,
      teller_voice=audio_voices.Voice.GEMINI_LEDA,
      listener_character=listener,
      listener_voice=audio_voices.Voice.GEMINI_PUCK,
      intro_sequence=None,
      setup_sequence=_sound_sequence(0.4, "gs://bucket/setup.wav"),
      response_sequence=_sound_sequence(0.2, "gs://bucket/response.wav"),
      punchline_sequence=_sound_sequence(0.5, "gs://bucket/punchline.wav"),
    )

  image_items = [item for item in script.items if isinstance(item, TimedImage)]
  setup_image_item = next(item for item in image_items
                          if item.gcs_uri == "gs://bucket/setup.png")
  assert setup_image_item.rect.y_px == 590
  assert setup_image_item.rect.height_px == 1080

  background_item = next(item for item in image_items
                         if item.gcs_uri.endswith("blank_paper.png"))
  assert background_item.rect.y_px == 0
  assert background_item.rect.height_px == 1920

  character_items = [
    item for item in script.items if isinstance(item, TimedCharacterSequence)
  ]
  assert len(character_items) > 0
  for character_item in character_items:
    assert character_item.rect.y_px + character_item.rect.height_px - 50 == (
      setup_image_item.rect.y_px)
    assert character_item.z_index > setup_image_item.z_index


def test_chars_on_top_hides_surface_line_for_all_character_sequences():
  teller = _SizedCharacter(width=200, height=260)
  with patch.object(
      script_utils,
      "load_sequence_from_firestore",
      side_effect=_load_firestore_sequence,
  ), patch.object(script_utils.random, "randint", return_value=1):
    script = joke_video_chars_on_top_script_builder.build_script(
      setup_image_gcs_uri="gs://bucket/setup.png",
      punchline_image_gcs_uri="gs://bucket/punchline.png",
      teller_character=teller,
      teller_voice=audio_voices.Voice.GEMINI_LEDA,
      intro_sequence=_sound_sequence(0.1, "gs://bucket/intro.wav"),
      setup_sequence=_sound_sequence(0.2, "gs://bucket/setup.wav"),
      punchline_sequence=_sound_sequence(0.3, "gs://bucket/punchline.wav"),
    )

  character_items = [
    item for item in script.items if isinstance(item, TimedCharacterSequence)
  ]
  assert len(character_items) > 0
  for item in character_items:
    track = item.sequence.sequence_surface_line_visible
    assert len(track) == 1
    assert track[0].start_time == pytest.approx(0.0)
    assert track[0].end_time == pytest.approx(item.sequence.duration_sec)
    assert track[0].value is False


def test_chars_on_top_inserts_leading_filler_for_listener_track():
  teller = _SizedCharacter(width=200, height=260)
  listener = _SizedCharacter(width=140, height=220)
  with patch.object(
      script_utils,
      "load_sequence_from_firestore",
      side_effect=_load_firestore_sequence,
  ), patch.object(script_utils.random, "randint", return_value=1):
    script = joke_video_chars_on_top_script_builder.build_script(
      setup_image_gcs_uri="gs://bucket/setup.png",
      punchline_image_gcs_uri="gs://bucket/punchline.png",
      teller_character=teller,
      teller_voice=audio_voices.Voice.GEMINI_LEDA,
      listener_character=listener,
      listener_voice=audio_voices.Voice.GEMINI_PUCK,
      intro_sequence=None,
      setup_sequence=_sound_sequence(0.2, "gs://bucket/setup.wav"),
      response_sequence=_sound_sequence(0.2, "gs://bucket/response.wav"),
      punchline_sequence=_sound_sequence(0.3, "gs://bucket/punchline.wav"),
    )

  listener_items = sorted([
    item for item in script.items
    if isinstance(item, TimedCharacterSequence) and item.actor_id == "actor_1"
  ],
                          key=lambda item: item.start_time_sec)
  assert listener_items
  first_item = listener_items[0]
  assert first_item.start_time_sec == pytest.approx(0.0)
  assert first_item.end_time_sec == pytest.approx(
    0.1 + script_utils.LISTENER_POP_IN_DELAY_AFTER_TELLER_POP_IN_END_SEC)
  assert first_item.sequence.sequence_sound_events == []
  surface_line_track = first_item.sequence.sequence_surface_line_visible
  assert len(surface_line_track) == 1
  assert surface_line_track[0].value is False
