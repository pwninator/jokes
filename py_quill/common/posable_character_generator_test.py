"""Tests for posable_character.generate_frames."""

import unittest
from unittest.mock import MagicMock, patch

from common.posable_character import PosableCharacter, generate_frames, MouthState, Transform
from common.posable_character_sequence import (
    PosableCharacterSequence,
    SequenceBooleanEvent,
    SequenceMouthEvent,
    SequenceSoundEvent,
    SequenceTransformEvent,
)
from common import models
from PIL import Image

class PosableCharacterGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.char_def = models.PosableCharacterDef(
            width=100,
            height=100,
            head_gcs_uri="gs://test/head",
        )
        self.char = PosableCharacter.from_def(self.char_def)
        # Mock get_image to return dummy image
        self.char.get_image = MagicMock(return_value=Image.new("RGBA", (100, 100)))

    def test_generate_frames_duration(self):
        # 1 second duration
        seq = PosableCharacterSequence(
            sequence_left_eye_open=[SequenceBooleanEvent(0.0, 1.0, True)]
        )
        fps = 10
        frames = list(generate_frames(self.char, seq, fps))

        # 1.0 duration -> 11 frames (0.0 to 1.0 inclusive)
        self.assertEqual(len(frames), 11)
        self.assertAlmostEqual(frames[-1][0], 1.0)

    def test_sound_events(self):
        # Sound at 0.5
        seq = PosableCharacterSequence(
            sequence_sound_events=[SequenceSoundEvent(0.5, "uri", volume=1.0)]
        )
        fps = 10 # dt = 0.1. Frames: 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, ...

        frames = list(generate_frames(self.char, seq, fps))

        # Check frame 5 (t=0.5)
        sounds_at_0_5 = frames[5][2]
        self.assertAlmostEqual(frames[5][0], 0.5)
        self.assertEqual(len(sounds_at_0_5), 1)
        self.assertEqual(sounds_at_0_5[0].gcs_uri, "uri")

        # Check other frames
        self.assertEqual(len(frames[0][2]), 0)

    def test_interpolation(self):
        # Transform 0.0 -> 1.0. X: 0 -> 10.
        seq = PosableCharacterSequence(
            sequence_left_hand_transform=[
                SequenceTransformEvent(0.0, 1.0, Transform(translate_x=10))
            ]
        )
        fps = 2 # dt = 0.5. Frames: 0.0, 0.5, 1.0.

        gen = generate_frames(self.char, seq, fps)

        # Frame 0 (t=0.0): Start of event. Previous value default (0). Target 10. t_rel=0. Value 0.
        t, _, _ = next(gen)
        self.assertEqual(t, 0.0)
        self.assertEqual(self.char.left_hand_transform.translate_x, 0.0)

        # Frame 1 (t=0.5): lerp(0, 10, 0.5) = 5.
        t, _, _ = next(gen)
        self.assertEqual(t, 0.5)
        self.assertEqual(self.char.left_hand_transform.translate_x, 5.0)

        # Frame 2 (t=1.0): lerp(0, 10, 1.0) = 10.
        t, _, _ = next(gen)
        self.assertEqual(t, 1.0)
        self.assertEqual(self.char.left_hand_transform.translate_x, 10.0)

    def test_gap_behavior(self):
        # Transform 1: 0.0-1.0 -> X=10.
        # Gap: 1.0-2.0.
        # Transform 2: 2.0-3.0 -> X=20.

        seq = PosableCharacterSequence(
            sequence_left_hand_transform=[
                SequenceTransformEvent(0.0, 1.0, Transform(translate_x=10)),
                SequenceTransformEvent(2.0, 3.0, Transform(translate_x=20)),
            ]
        )
        fps = 1 # dt=1.0. Frames: 0, 1, 2, 3.

        gen = generate_frames(self.char, seq, fps)

        # t=0: Start E1. lerp(0, 10, 0). X=0.
        next(gen)
        self.assertEqual(self.char.left_hand_transform.translate_x, 0.0)

        # t=1: End E1 / Start Gap. lerp(0, 10, 1). X=10.
        next(gen)
        self.assertEqual(self.char.left_hand_transform.translate_x, 10.0)

        # t=2: End Gap / Start E2.
        # In gap (1.0 < t < 2.0): Hold last value (10).
        # At t=2.0, we enter E2. Start value = prev E1 target = 10. Target = 20. t_rel=0.
        # lerp(10, 20, 0) = 10.
        next(gen)
        self.assertEqual(self.char.left_hand_transform.translate_x, 10.0)

        # t=3: End E2. lerp(10, 20, 1). X=20.
        next(gen)
        self.assertEqual(self.char.left_hand_transform.translate_x, 20.0)

    def test_mouth_gap_behavior(self):
        # Mouth: 0.0-1.0 Open. Gap. 2.0-3.0 O.
        seq = PosableCharacterSequence(
            sequence_mouth_state=[
                SequenceMouthEvent(0.0, 1.0, MouthState.OPEN),
                SequenceMouthEvent(2.0, 3.0, MouthState.O),
            ]
        )
        fps = 2 # dt=0.5. 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0.

        gen = generate_frames(self.char, seq, fps)

        # t=0.0: Inside E1. Open.
        next(gen)
        self.assertEqual(self.char.mouth_state, MouthState.OPEN)

        # t=0.5: Inside E1. Open.
        next(gen)
        self.assertEqual(self.char.mouth_state, MouthState.OPEN)

        # t=1.0: E1 ends. (Inclusive). Open.
        next(gen)
        self.assertEqual(self.char.mouth_state, MouthState.OPEN)

        # t=1.5: Gap. Default (Closed).
        next(gen)
        self.assertEqual(self.char.mouth_state, MouthState.CLOSED)

        # t=2.0: E2 starts. O.
        next(gen)
        self.assertEqual(self.char.mouth_state, MouthState.O)

if __name__ == '__main__':
    unittest.main()
