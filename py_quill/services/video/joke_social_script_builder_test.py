from __future__ import annotations

from unittest.mock import patch

import pytest
from common import models
from common.posable_character import PosableCharacter
from common.posable_character_sequence import (PosableCharacterSequence,
                                               SequenceSoundEvent)
from PIL import Image
from services import audio_voices
from services.video import joke_social_script_builder
from services.video.script import TimedCharacterSequence


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
    self._size: tuple[int, int] = (int(width), int(height))

  def get_image(self) -> Image.Image:
    return Image.new("RGBA", self._size, (0, 0, 0, 255))


def _sound_sequence(duration_sec: float,
                    gcs_uri: str) -> PosableCharacterSequence:
  sequence = PosableCharacterSequence(sequence_sound_events=[
    SequenceSoundEvent(
      start_time=0.0,
      end_time=float(duration_sec),
      gcs_uri=gcs_uri,
      volume=1.0,
    )
  ])
  sequence.validate()
  return sequence


def _spoken_items(script) -> list[TimedCharacterSequence]:
  return [
    item for item in script.items if isinstance(item, TimedCharacterSequence)
    and item.sequence.sequence_sound_events
  ]


def _load_firestore_sequence(sequence_id: str) -> PosableCharacterSequence:
  if sequence_id == "pop_in":
    return _sound_sequence(0.1, "gs://bucket/pop_in.wav")
  if sequence_id == "GEMINI_LEDA_giggle1":
    return _sound_sequence(0.3, "gs://bucket/leda_giggle.wav")
  if sequence_id == "GEMINI_PUCK_giggle1":
    return _sound_sequence(0.3, "gs://bucket/puck_giggle.wav")
  raise AssertionError(f"Unexpected sequence id: {sequence_id}")


def test_portrait_character_layout_bottom_aligns_to_tallest():
  teller = _SizedCharacter(width=220, height=300)
  listener = _SizedCharacter(width=120, height=140)
  with patch.object(
      joke_social_script_builder,
      "_load_sequence_from_firestore",
      side_effect=_load_firestore_sequence,
  ), patch.object(joke_social_script_builder.random, "randint",
                  return_value=1):
    script = joke_social_script_builder.build_portrait_joke_scene_script(
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

  spoken_by_actor: dict[str, TimedCharacterSequence] = {}
  for item in _spoken_items(script):
    spoken_by_actor.setdefault(item.actor_id, item)

  teller_rect = spoken_by_actor["actor_0"].rect
  listener_rect = spoken_by_actor["actor_1"].rect
  assert teller_rect.y_px + teller_rect.height_px == (listener_rect.y_px +
                                                      listener_rect.height_px)
  assert teller_rect.y_px == joke_social_script_builder._PORTRAIT_CHARACTER_RECT.y_px  # pylint: disable=protected-access


def test_portrait_character_layout_uses_proportional_horizontal_slots():
  teller = _SizedCharacter(width=200, height=240)
  listener = _SizedCharacter(width=100, height=240)
  with patch.object(
      joke_social_script_builder,
      "_load_sequence_from_firestore",
      side_effect=_load_firestore_sequence,
  ), patch.object(joke_social_script_builder.random, "randint",
                  return_value=1):
    script = joke_social_script_builder.build_portrait_joke_scene_script(
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

  spoken_by_actor: dict[str, TimedCharacterSequence] = {}
  for item in _spoken_items(script):
    spoken_by_actor.setdefault(item.actor_id, item)

  teller_rect = spoken_by_actor["actor_0"].rect
  listener_rect = spoken_by_actor["actor_1"].rect
  teller_center = teller_rect.x_px + (teller_rect.width_px / 2.0)
  listener_center = listener_rect.x_px + (listener_rect.width_px / 2.0)

  left_bound = (
    joke_social_script_builder._PORTRAIT_CHARACTER_RECT.x_px +  # pylint: disable=protected-access
    joke_social_script_builder._PORTRAIT_CHARACTER_SIDE_MARGIN_PX)  # pylint: disable=protected-access
  right_bound = (
    joke_social_script_builder._PORTRAIT_CHARACTER_RECT.x_px +  # pylint: disable=protected-access
    joke_social_script_builder._PORTRAIT_CHARACTER_RECT.width_px -  # pylint: disable=protected-access
    joke_social_script_builder._PORTRAIT_CHARACTER_SIDE_MARGIN_PX)  # pylint: disable=protected-access
  available = float(right_bound - left_bound)
  width_ratio = 200.0 / (200.0 + 100.0)
  expected_teller_center = float(left_bound) + (available * width_ratio * 0.5)
  expected_listener_center = float(left_bound) + (available * width_ratio +
                                                  (available *
                                                   (1.0 - width_ratio) * 0.5))

  assert teller_center == pytest.approx(expected_teller_center, abs=1.0)
  assert listener_center == pytest.approx(expected_listener_center, abs=1.0)
