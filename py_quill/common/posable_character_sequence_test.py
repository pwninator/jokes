"""Tests for posable_character_sequence."""

import unittest

from common.posable_character import MouthState, Transform
from common.posable_character_sequence import (
  PosableCharacterSequence, SequenceBooleanEvent, SequenceFloatEvent,
  SequenceMouthEvent, SequenceSoundEvent, SequenceTransformEvent)


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
    with self.assertRaisesRegex(ValueError,
                                "Sound events must have positive duration"):
      seq.validate()

  def test_duration_sec_returns_max_end_time_across_all_tracks(self):
    seq = PosableCharacterSequence(
      sequence_mouth_state=[
        SequenceMouthEvent(start_time=0.0,
                           end_time=0.8,
                           mouth_state=MouthState.OPEN),
      ],
      sequence_sound_events=[
        SequenceSoundEvent(start_time=0.0, end_time=1.2, gcs_uri="gs://a.wav"),
      ],
      sequence_surface_line_offset=[
        SequenceFloatEvent(start_time=0.0, end_time=2.4, target_value=12.0),
      ],
    )

    self.assertEqual(seq.duration_sec, 2.4)

  def test_duration_sec_empty_sequence_is_zero(self):
    seq = PosableCharacterSequence()
    self.assertEqual(seq.duration_sec, 0.0)

  def test_append_merges_and_offsets_all_tracks(self):
    base = PosableCharacterSequence(
      sequence_left_eye_open=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
      ],
      sequence_surface_line_offset=[
        SequenceFloatEvent(start_time=0.0, end_time=0.5, target_value=40.0),
      ],
      sequence_mask_boundary_offset=[
        SequenceFloatEvent(start_time=0.0, end_time=0.5, target_value=30.0),
      ],
      sequence_head_masking_enabled=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
      ],
      sequence_left_hand_masking_enabled=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=True),
      ],
      sequence_right_hand_masking_enabled=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=True),
      ],
      sequence_surface_line_visible=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
      ],
      sequence_sound_events=[
        SequenceSoundEvent(
          start_time=0.0,
          end_time=0.5,
          gcs_uri="gs://bucket/base.wav",
          volume=1.0,
        ),
      ],
    )
    other = PosableCharacterSequence(
      sequence_right_eye_open=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
      ],
      sequence_mouth_state=[
        SequenceMouthEvent(
          start_time=0.0,
          end_time=0.5,
          mouth_state=MouthState.O,
        ),
      ],
      sequence_left_hand_visible=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
      ],
      sequence_right_hand_visible=[
        SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
      ],
      sequence_left_hand_transform=[
        SequenceTransformEvent(
          start_time=0.0,
          end_time=0.5,
          target_transform=Transform(translate_x=5.0, translate_y=-2.0),
        ),
      ],
      sequence_right_hand_transform=[
        SequenceTransformEvent(
          start_time=0.0,
          end_time=0.5,
          target_transform=Transform(translate_x=-3.0, translate_y=4.0),
        ),
      ],
      sequence_head_transform=[
        SequenceTransformEvent(
          start_time=0.0,
          end_time=0.5,
          target_transform=Transform(scale_x=0.8, scale_y=0.8),
        ),
      ],
      sequence_sound_events=[
        SequenceSoundEvent(
          start_time=0.0,
          end_time=0.5,
          gcs_uri="gs://bucket/other.wav",
          volume=0.7,
        ),
      ],
    )

    merged = base.append([(other, 1.0)])

    self.assertEqual(len(merged.sequence_left_eye_open), 1)
    self.assertEqual(merged.sequence_left_eye_open[0].start_time, 0.0)
    self.assertEqual(len(merged.sequence_right_eye_open), 1)
    self.assertEqual(merged.sequence_right_eye_open[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_mouth_state), 1)
    self.assertEqual(merged.sequence_mouth_state[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_left_hand_visible), 1)
    self.assertEqual(merged.sequence_left_hand_visible[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_right_hand_visible), 1)
    self.assertEqual(merged.sequence_right_hand_visible[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_left_hand_transform), 1)
    self.assertEqual(merged.sequence_left_hand_transform[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_right_hand_transform), 1)
    self.assertEqual(merged.sequence_right_hand_transform[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_head_transform), 1)
    self.assertEqual(merged.sequence_head_transform[0].start_time, 1.0)
    self.assertEqual(len(merged.sequence_surface_line_offset), 1)
    self.assertEqual(merged.sequence_surface_line_offset[0].start_time, 0.0)
    self.assertEqual(len(merged.sequence_mask_boundary_offset), 1)
    self.assertEqual(merged.sequence_mask_boundary_offset[0].start_time, 0.0)
    self.assertEqual(len(merged.sequence_surface_line_visible), 1)
    self.assertEqual(merged.sequence_surface_line_visible[0].start_time, 0.0)
    self.assertEqual(len(merged.sequence_head_masking_enabled), 1)
    self.assertEqual(merged.sequence_head_masking_enabled[0].start_time, 0.0)
    self.assertEqual(len(merged.sequence_left_hand_masking_enabled), 1)
    self.assertEqual(
      merged.sequence_left_hand_masking_enabled[0].start_time,
      0.0,
    )
    self.assertEqual(len(merged.sequence_right_hand_masking_enabled), 1)
    self.assertEqual(
      merged.sequence_right_hand_masking_enabled[0].start_time,
      0.0,
    )
    self.assertEqual(len(merged.sequence_sound_events), 2)
    self.assertEqual(merged.sequence_sound_events[0].start_time, 0.0)
    self.assertEqual(merged.sequence_sound_events[1].start_time, 1.0)

  def test_append_does_not_mutate_input_sequences(self):
    base = PosableCharacterSequence(sequence_left_eye_open=[
      SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=True),
    ])
    other = PosableCharacterSequence(sequence_right_eye_open=[
      SequenceBooleanEvent(start_time=0.0, end_time=0.5, value=False),
    ])

    _ = base.append([(other, 2.0)])

    self.assertEqual(base.sequence_left_eye_open[0].start_time, 0.0)
    self.assertEqual(other.sequence_right_eye_open[0].start_time, 0.0)


if __name__ == '__main__':
  unittest.main()
