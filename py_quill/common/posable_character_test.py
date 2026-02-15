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
      _SAMPLE_DEF.surface_line_gcs_uri: _make_image((0, 0, 0, 0), size=(4, 1)),
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
    self.assertEqual(character.mouth_state, MouthState.CLOSED)

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
      head_masking_enabled=False,
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
    self.assertEqual(mock_download.call_count, 7)

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_pose_change_returns_new_image(self, mock_download):
    images = self._default_images()
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    image_one = character.get_image()
    character.set_pose(right_eye_open=False)
    image_two = character.get_image()

    self.assertIsNot(image_one, image_two)

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_head_masking_clips_pixels_below_boundary(self, mock_download):
    images = self._default_images()
    transparent = _make_image((0, 0, 0, 0))
    images[_SAMPLE_DEF.head_gcs_uri] = _make_image((255, 0, 0, 255))
    images[_SAMPLE_DEF.left_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_o_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_hand_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_hand_gcs_uri] = transparent
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    character.set_pose(mask_boundary_offset=2.0)
    composed = character.get_image()

    self.assertEqual(composed.getpixel((2, 1)), (255, 0, 0, 255))
    self.assertEqual(composed.getpixel((2, 3)), (0, 0, 0, 0))

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_hand_masking_disabled_by_default(self, mock_download):
    images = self._default_images()
    transparent = _make_image((0, 0, 0, 0))
    images[_SAMPLE_DEF.head_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_o_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_hand_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_hand_gcs_uri] = _make_image((200, 10, 10, 255))
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    character.set_pose(mask_boundary_offset=2.0, right_hand_visible=False)
    composed = character.get_image()

    self.assertEqual(composed.getpixel((2, 3)), (200, 10, 10, 255))

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_hand_masking_enabled_clips_pixels(self, mock_download):
    images = self._default_images()
    transparent = _make_image((0, 0, 0, 0))
    images[_SAMPLE_DEF.head_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_eye_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_open_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_closed_gcs_uri] = transparent
    images[_SAMPLE_DEF.mouth_o_gcs_uri] = transparent
    images[_SAMPLE_DEF.right_hand_gcs_uri] = transparent
    images[_SAMPLE_DEF.left_hand_gcs_uri] = _make_image((200, 10, 10, 255))
    mock_download.side_effect = lambda uri: images[uri]

    character = self._build_character()
    character.set_pose(
      mask_boundary_offset=2.0,
      left_hand_masking_enabled=True,
      right_hand_visible=False,
    )
    composed = character.get_image()

    self.assertEqual(composed.getpixel((2, 3)), (0, 0, 0, 0))

  @patch("common.posable_character.cloud_storage.download_image_from_gcs")
  def test_hand_masking_updates_with_transform_and_surface_line_not_masked(
    self,
    mock_download,
  ):
    definition = models.PosableCharacterDef(
      width=100,
      height=100,
      head_gcs_uri="gs://test2/head.png",
      surface_line_gcs_uri="gs://test2/surface_line.png",
      left_hand_gcs_uri="gs://test2/left_hand.png",
      right_hand_gcs_uri="gs://test2/right_hand.png",
      mouth_open_gcs_uri="gs://test2/mouth_open.png",
      mouth_closed_gcs_uri="gs://test2/mouth_closed.png",
      mouth_o_gcs_uri="gs://test2/mouth_o.png",
      left_eye_open_gcs_uri="gs://test2/left_eye_open.png",
      left_eye_closed_gcs_uri="gs://test2/left_eye_closed.png",
      right_eye_open_gcs_uri="gs://test2/right_eye_open.png",
      right_eye_closed_gcs_uri="gs://test2/right_eye_closed.png",
    )
    transparent = _make_image((0, 0, 0, 0), size=(100, 100))
    hand = _make_image((200, 10, 10, 255), size=(20, 20))
    surface_line = _make_image((10, 200, 10, 255), size=(100, 2))

    images: dict[str, Image.Image] = {
      definition.head_gcs_uri: transparent,
      definition.left_eye_open_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.right_eye_open_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.left_eye_closed_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.right_eye_closed_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.mouth_open_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.mouth_closed_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.mouth_o_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.left_hand_gcs_uri: hand,
      definition.right_hand_gcs_uri: _make_image((0, 0, 0, 0)),
      definition.surface_line_gcs_uri: surface_line,
    }
    mock_download.side_effect = lambda uri: images[uri]

    character = PosableCharacter.from_def(definition)
    # Place the surface line well below the mask boundary; it must remain visible.
    character.set_pose(
      head_masking_enabled=False,
      right_hand_visible=False,
      left_hand_masking_enabled=True,
      mask_boundary_offset=30.0,  # cutoff_y = 100 - 30 = 70
      surface_line_visible=True,
      surface_line_offset=10.0,  # y = 100 - 10 = 90
      left_hand_transform=Transform(translate_y=20.0),
    )
    composed_low = character.get_image()

    # Hand (20x20) is centered (base_y=40) then translated to y=60.
    # With cutoff_y=70, only y=60..69 is visible.
    self.assertEqual(composed_low.getpixel((50, 65)), (200, 10, 10, 255))
    self.assertEqual(composed_low.getpixel((50, 75)), (0, 0, 0, 0))

    # Surface line is rendered after head and is not subject to masking.
    self.assertEqual(composed_low.getpixel((50, 90)), (10, 200, 10, 255))

    # Now move the hand above the boundary; the previously masked pixels must reappear.
    character.set_pose(left_hand_transform=Transform(translate_y=-10.0))
    composed_high = character.get_image()
    self.assertEqual(composed_high.getpixel((50, 45)), (200, 10, 10, 255))

  def test_initialization_with_definition(self):
    definition = models.PosableCharacterDef(
      width=10,
      height=20,
      head_gcs_uri="gs://test/model_head.png",
      surface_line_gcs_uri="gs://test/model_surface_line.png",
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
    self.assertEqual(character.mouth_state, MouthState.CLOSED)
    self.assertIsInstance(character._image_cache, dict)

    # Verify it works with get_image (mocking download)
    with patch("common.posable_character.cloud_storage.download_image_from_gcs"
               ) as mock_download:
      mock_download.return_value = _make_image((255, 0, 0, 255), size=(10, 20))
      character.get_image()
      mock_download.assert_any_call("gs://test/model_head.png")


if __name__ == "__main__":
  unittest.main()
