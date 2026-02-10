"""Canonical fixture tests for `common.character_animator`."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from common.character_animator import CharacterAnimator
from common.posable_character import MouthState
from common.posable_character_sequence import PosableCharacterSequence
from common.posable_character_sequence import SequenceMouthEvent


def _fixture_path() -> Path:
  return Path(__file__).resolve().parent / "testdata" / "character_animator_canonical_v1.json"


class CharacterAnimatorTest(unittest.TestCase):

  def test_canonical_fixture_samples_and_sounds(self):
    with _fixture_path().open("r", encoding="utf-8") as file_handle:
      fixture = json.load(file_handle)

    sequence = PosableCharacterSequence.from_dict(fixture["sequence"])
    animator = CharacterAnimator(sequence)

    self.assertAlmostEqual(float(animator.duration_sec),
                           float(fixture["expected_duration_sec"]))

    expected_samples_by_time = {
      float(item["time_sec"]): item for item in fixture["expected_samples"]
    }
    for time_sec in fixture["sample_times_sec"]:
      time_sec = float(time_sec)
      expected = expected_samples_by_time[time_sec]
      sample = animator.sample_pose(time_sec)

      self.assertEqual(sample.left_eye_open, expected["left_eye_open"])
      self.assertEqual(sample.right_eye_open, expected["right_eye_open"])
      self.assertEqual(sample.mouth_state.value, expected["mouth_state"])
      self.assertEqual(sample.left_hand_visible, expected["left_hand_visible"])
      self.assertEqual(sample.right_hand_visible, expected["right_hand_visible"])

      self.assertAlmostEqual(
        float(sample.left_hand_transform.translate_x),
        float(expected["left_hand_transform"]["translate_x"]),
      )
      self.assertAlmostEqual(
        float(sample.left_hand_transform.translate_y),
        float(expected["left_hand_transform"]["translate_y"]),
      )
      self.assertAlmostEqual(
        float(sample.left_hand_transform.scale_x),
        float(expected["left_hand_transform"]["scale_x"]),
      )
      self.assertAlmostEqual(
        float(sample.left_hand_transform.scale_y),
        float(expected["left_hand_transform"]["scale_y"]),
      )

      self.assertAlmostEqual(
        float(sample.right_hand_transform.translate_x),
        float(expected["right_hand_transform"]["translate_x"]),
      )
      self.assertAlmostEqual(
        float(sample.right_hand_transform.translate_y),
        float(expected["right_hand_transform"]["translate_y"]),
      )
      self.assertAlmostEqual(
        float(sample.right_hand_transform.scale_x),
        float(expected["right_hand_transform"]["scale_x"]),
      )
      self.assertAlmostEqual(
        float(sample.right_hand_transform.scale_y),
        float(expected["right_hand_transform"]["scale_y"]),
      )

      self.assertAlmostEqual(
        float(sample.head_transform.translate_x),
        float(expected["head_transform"]["translate_x"]),
      )
      self.assertAlmostEqual(
        float(sample.head_transform.translate_y),
        float(expected["head_transform"]["translate_y"]),
      )
      self.assertAlmostEqual(
        float(sample.head_transform.scale_x),
        float(expected["head_transform"]["scale_x"]),
      )
      self.assertAlmostEqual(
        float(sample.head_transform.scale_y),
        float(expected["head_transform"]["scale_y"]),
      )

    for window in fixture["sound_windows"]:
      sounds = animator.sound_events_between(
        float(window["start_time_sec"]),
        float(window["end_time_sec"]),
        include_start=True,
        include_end=False,
      )
      sound_starts = [float(event.start_time) for event in sounds]
      expected_starts = [float(value) for value in window["expected_sound_starts"]]
      self.assertEqual(sound_starts, expected_starts)

  def test_adjacent_mouth_events_use_half_open_windows(self):
    sequence = PosableCharacterSequence(
      sequence_mouth_state=[
        SequenceMouthEvent(
          start_time=0.0,
          end_time=1.0,
          mouth_state=MouthState.OPEN,
        ),
        SequenceMouthEvent(
          start_time=1.0,
          end_time=2.0,
          mouth_state=MouthState.O,
        ),
      ])
    animator = CharacterAnimator(sequence)

    self.assertEqual(animator.sample_pose(0.999).mouth_state, MouthState.OPEN)
    self.assertEqual(animator.sample_pose(1.0).mouth_state, MouthState.O)


if __name__ == "__main__":
  unittest.main()
