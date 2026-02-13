"""Tests for posable_character_sequence."""

import unittest

from common.posable_character import MouthState, Transform
from common.posable_character_sequence import (PosableCharacterSequence,
                                               SequenceBooleanEvent,
                                               SequenceFloatEvent,
                                               SequenceMouthEvent,
                                               SequenceSoundEvent,
                                               SequenceTransformEvent)


class PosableCharacterSequenceTest(unittest.TestCase):

  def test_serialization(self):
    seq = PosableCharacterSequence(
      key="seq1",
      sequence_left_eye_open=[
        SequenceBooleanEvent(start_time=0.0, end_time=1.0, value=True),
        SequenceBooleanEvent(start_time=1.0, end_time=2.0, value=False),
      ],
      sequence_mouth_state=[
        SequenceMouthEvent(start_time=0.5,
                           end_time=1.5,
                           mouth_state=MouthState.OPEN),
      ],
      sequence_left_hand_transform=[
        SequenceTransformEvent(start_time=0.0,
                               end_time=1.0,
                               target_transform=Transform(10, 20, 1.0, 1.0)),
      ],
      sequence_surface_line_offset=[
        SequenceFloatEvent(start_time=0.0, end_time=1.0, target_value=50.0),
      ],
      sequence_sound_events=[
        SequenceSoundEvent(start_time=0.0,
                           end_time=1.0,
                           gcs_uri="gs://bucket/sound.wav",
                           volume=0.8),
      ])

    data = seq.to_dict(include_key=True)
    self.assertEqual(data["key"], "seq1")
    self.assertEqual(len(data["sequence_left_eye_open"]), 2)
    self.assertEqual(data["sequence_mouth_state"][0]["mouth_state"], "OPEN")
    self.assertEqual(
      data["sequence_left_hand_transform"][0]["target_transform"]
      ["translate_x"], 10)
    self.assertEqual(data["sequence_surface_line_offset"][0]["target_value"],
                     50.0)

    seq2 = PosableCharacterSequence.from_dict(data)
    self.assertEqual(seq2.key, "seq1")
    self.assertEqual(len(seq2.sequence_left_eye_open), 2)
    self.assertEqual(seq2.sequence_mouth_state[0].mouth_state, MouthState.OPEN)
    self.assertEqual(
      seq2.sequence_left_hand_transform[0].target_transform.translate_x, 10)
    self.assertEqual(seq2.sequence_surface_line_offset[0].target_value, 50.0)
    self.assertEqual(seq2.sequence_sound_events[0].volume, 0.8)

  def test_validation_overlap(self):
    seq = PosableCharacterSequence(sequence_left_eye_open=[
      SequenceBooleanEvent(start_time=0.0, end_time=1.0, value=True),
      SequenceBooleanEvent(start_time=0.5, end_time=1.5,
                           value=False),  # Overlap
    ])
    with self.assertRaises(ValueError):
      seq.validate()

  def test_validation_valid(self):
    seq = PosableCharacterSequence(sequence_left_eye_open=[
      SequenceBooleanEvent(start_time=0.0, end_time=1.0, value=True),
      SequenceBooleanEvent(start_time=1.0, end_time=2.0, value=False),
    ])
    seq.validate()  # Should not raise

  def test_sound_validation(self):
    # Sound events CAN overlap
    seq = PosableCharacterSequence(sequence_sound_events=[
      SequenceSoundEvent(start_time=0.0, end_time=1.0, gcs_uri="uri1"),
      SequenceSoundEvent(start_time=0.5, end_time=1.5, gcs_uri="uri2"),
    ])
    seq.validate()

  def test_sound_validation_rejects_zero_duration(self):
    seq = PosableCharacterSequence(sequence_sound_events=[
      SequenceSoundEvent(start_time=1.0, end_time=1.0, gcs_uri="uri1"),
    ])
    with self.assertRaisesRegex(
      ValueError, "Sound events must have positive duration"):
      seq.validate()


if __name__ == '__main__':
  unittest.main()
