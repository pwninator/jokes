"""Unit tests for PosableCharacter."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from common import models
from common.posable_character import (MouthState, PoseState, PosableCharacter,
                                      Transform)
from PIL import Image


def _make_image(
  color: tuple[int, int, int, int], size: tuple[int, int] = (4, 4)
) -> Image.Image:
  return Image.new("RGBA", size, color=color)


_SAMPLE_DEF = models.PosableCharacterDef(
  width=4,
  height=4,
  head_gcs_uri="gs://test/head.png",
  left_hand_gcs_uri="gs://test/left_hand.png",
  right_hand_gcs_uri="gs://test/right_hand.png",
  mouth_open_gcs_uri="gs://test/mouth_open.png",
  mouth_closed_gcs_uri="gs://test/mouth_closed.png",
  mouth_o_gcs_uri="gs://test/mouth_o.png",
  left_eye_open_gcs_uri="gs://test/left_eye_open.png",
  left_eye_closed_gcs_uri="gs://test/left_eye_closed.png",
  right_eye_open_gcs_uri="gs://test/right_eye_open.png",
  right_eye_closed_gcs_uri="gs://test/right_eye_closed.png",
)


class SampleCharacter(PosableCharacter):

  def __init__(self):
    super().__init__(definition=_SAMPLE_DEF)


class TransformTest(unittest.TestCase):

  def test_defaults_and_hashable(self):
    transform = Transform()
    self.assertEqual(transform.translate_x, 0.0)
    self.assertEqual(transform.translate_y, 0.0)
    self.assertEqual(transform.scale_x, 1.0)
    self.assertEqual(transform.scale_y, 1.0)
    cache = {transform: "ok"}
    self.assertEqual(cache[transform], "ok")

  def test_from_tuple(self):
    transform = Transform.from_tuple((2.0, -3.0))
    self.assertEqual(transform, Transform(translate_x=2.0, translate_y=-3.0))

    transform_full = Transform.from_tuple((1.0, 2.0, 0.5, 0.25))
    self.assertEqual(
      transform_full,
      Transform(translate_x=1.0, translate_y=2.0, scale_x=0.5, scale_y=0.25),
    )


class PosableCharacterTest(unittest.TestCase):

  def _build_character(self) -> SampleCharacter:
    return SampleCharacter()

  def _default_images(self) -> dict[str, Image.Image]:
    return {
      _SAMPLE_DEF.head_gcs_uri: _make_image((255, 0, 0, 255)),
      _SAMPLE_DEF.left_eye_open_gcs_uri: _make_image((0, 255, 0, 255)),
      _SAMPLE_DEF.right_eye_open_gcs_uri: _make_image((0, 0, 255, 255)),
      _SAMPLE_DEF.left_eye_closed_gcs_uri: _make_image((0, 255, 0, 255)),
      _SAMPLE_DEF.right_eye_closed_gcs_uri: _make_image((0, 0, 255, 255)),
      _SAMPLE_DEF.mouth_open_gcs_uri: _make_image((255, 255, 0, 255)),
      _SAMPLE_DEF.mouth_closed_gcs_uri: _make_image((255, 255, 0, 255)),
      _SAMPLE_DEF.mouth_o_gcs_uri: _make_image((255, 255, 0, 255)),
      _SAMPLE_DEF.left_hand_gcs_uri: _make_image((255, 0, 255, 255)),
      _SAMPLE_DEF.right_hand_gcs_uri: _make_image((0, 255, 255, 255)),
    }

  def test_set_pose_updates_only_provided_values(self):
    character = self._build_character()
    character.set_pose(left_eye_open=False)
    self.assertFalse(character.left_eye_open)
    self.assertTrue(character.right_eye_open)
    self.assertEqual(character.mouth_state, MouthState.OPEN)

  def test_set_pose_accepts_transform_tuples(self):
    character = self._build_character()
    character.set_pose(
      left_hand_transform=(2.0, -1.0),
      head_transform=(1.0, 2.0, 0.5, 0.25),
    )
    self.assertEqual(character.left_hand_transform,
                     Transform(translate_x=2.0, translate_y=-1.0))
    self.assertEqual(
      character.head_transform,
      Transform(translate_x=1.0, translate_y=2.0, scale_x=0.5, scale_y=0.25),
    )

  def test_pose_state_updates_with_set_pose(self):
    character = self._build_character()
    self.assertEqual(character.pose_state, PoseState())

    character.set_pose(mouth_state=MouthState.CLOSED, left_hand_visible=False)
    self.assertEqual(character.pose_state.mouth_state, MouthState.CLOSED)
    self.assertFalse(character.pose_state.left_hand_visible)

  def test_apply_pose_state_replaces_all_pose_fields(self):
    character = self._build_character()
    target = PoseState(
      left_eye_open=False,
      right_eye_open=False,
      mouth_state=MouthState.O,
      left_hand_visible=False,
      right_hand_visible=False,
      left_hand_transform=Transform(translate_x=2.0),
      right_hand_transform=Transform(translate_y=-3.0),
      head_transform=Transform(scale_x=0.5, scale_y=0.5),
    )

    character.apply_pose_state(target)
    self.assertEqual(character.pose_state, target)
    self.assertFalse(character.left_eye_open)
    self.assertEqual(character.mouth_state, MouthState.O)

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_get_image_layers_hands_last(self, mock_download):
    images = self._default_images()
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    composed = character.get_image()

    self.assertEqual(composed.getpixel((2, 2)), (0, 255, 255, 255))

    character.set_pose(right_hand_visible=False)
    composed_no_right_hand = character.get_image()
    self.assertEqual(composed_no_right_hand.getpixel((2, 2)),
                     (255, 0, 255, 255))

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_hand_transform_translation_and_scale(self, mock_download):
    images = self._default_images()
    transparent = _make_image((0, 0, 0, 0))
    images[_SAMPLE_DEF.head_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_o_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_hand_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_hand_gcs_uri] = _make_image((200, 10, 10, 255))
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    character.set_pose(
      left_hand_transform=(1.0, 0.0, 0.5, 0.5),
      right_hand_visible=False,
    )
    composed = character.get_image()

    self.assertEqual(composed.getpixel((2, 1)), (200, 10, 10, 255))
    self.assertEqual(composed.getpixel((1, 1)), (0, 0, 0, 0))

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_head_transform_applies_to_eyes_and_mouth(self, mock_download):
    images = self._default_images()
    transparent = _make_image((0, 0, 0, 0))
    images[_SAMPLE_DEF.head_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_o_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_closed_gcs_uri] = transparent
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    character.set_pose(
      head_transform=Transform(
        translate_x=1,
        translate_y=0,
        scale_x=0.5,
        scale_y=0.5,
      ),
      right_hand_visible=False,
      left_hand_visible=False,
    )
    composed = character.get_image()

    self.assertEqual(composed.getpixel((2, 1)), (0, 255, 0, 255))
    self.assertEqual(composed.getpixel((1, 1)), (0, 0, 0, 0))

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_get_image_uses_pose_cache(self, mock_download):
    images = self._default_images()
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    image_one = character.get_image()
    image_two = character.get_image()

    self.assertIs(image_one, image_two)
    self.assertEqual(mock_download.call_count, 6)

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_pose_change_returns_new_image(self, mock_download):
    images = self._default_images()
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    image_one = character.get_image()
    character.set_pose(right_eye_open=False)
    image_two = character.get_image()

    self.assertIsNot(image_one, image_two)

  def test_initialization_with_definition(self):
    definition = models.PosableCharacterDef(
      width=10,
      height=20,
      head_gcs_uri="gs://test/model_head.png",
      left_hand_gcs_uri="gs://test/model_left_hand.png",
      right_hand_gcs_uri="gs://test/model_right_hand.png",
      mouth_open_gcs_uri="gs://test/model_mouth_open.png",
      mouth_closed_gcs_uri="gs://test/model_mouth_closed.png",
      mouth_o_gcs_uri="gs://test/model_mouth_o.png",
      left_eye_open_gcs_uri="gs://test/model_left_eye_open.png",
      left_eye_closed_gcs_uri="gs://test/model_left_eye_closed.png",
      right_eye_open_gcs_uri="gs://test/model_right_eye_open.png",
      right_eye_closed_gcs_uri="gs://test/model_right_eye_closed.png",
    )
    character = PosableCharacter.from_def(definition)
    self.assertEqual(character.definition.width, 10)
    self.assertEqual(character.definition.height, 20)
    self.assertEqual(character.definition.head_gcs_uri,
                     "gs://test/model_head.png")

    # Verify transient fields are initialized
    self.assertTrue(character.left_eye_open)
    self.assertEqual(character.mouth_state, MouthState.OPEN)
    self.assertIsInstance(character._image_cache, dict)

    # Verify it works with get_image (mocking download)
    with patch("common.posable_character.cloud_storage.download_image_from_gcs"
               ) as mock_download:
      mock_download.return_value = _make_image((255, 0, 0, 255), size=(10, 20))
      character.get_image()
      mock_download.assert_any_call("gs://test/model_head.png")


if __name__ == "__main__":
  unittest.main()
