"""Posable character subclasses."""

from __future__ import annotations

from common import models
from common.posable_character import PosableCharacter

_CAT_ASSET_DIR = "gs://images.quillsstorybook.com/_joke_assets/characters/cat"

_CAT_DEF = models.PosableCharacterDef(
  key="cat",
  name="Cat",
  width=500,
  height=350,
  head_gcs_uri=f"{_CAT_ASSET_DIR}/cat_head.png",
  surface_line_gcs_uri=f"{_CAT_ASSET_DIR}/cat_surface_line.png",
  left_hand_gcs_uri=f"{_CAT_ASSET_DIR}/cat_hand_left.png",
  right_hand_gcs_uri=f"{_CAT_ASSET_DIR}/cat_hand_right.png",
  mouth_open_gcs_uri=f"{_CAT_ASSET_DIR}/cat_mouth_open.png",
  mouth_closed_gcs_uri=f"{_CAT_ASSET_DIR}/cat_mouth_closed.png",
  mouth_o_gcs_uri=f"{_CAT_ASSET_DIR}/cat_mouth_o.png",
  left_eye_open_gcs_uri=f"{_CAT_ASSET_DIR}/cat_eye_left_open.png",
  left_eye_closed_gcs_uri=f"{_CAT_ASSET_DIR}/cat_eye_left_closed.png",
  right_eye_open_gcs_uri=f"{_CAT_ASSET_DIR}/cat_eye_right_open.png",
  right_eye_closed_gcs_uri=f"{_CAT_ASSET_DIR}/cat_right_closed.png",
)


class PosableCat(PosableCharacter):
  """Cat character with posable sprite components."""

  def __init__(self):
    super().__init__(definition=_CAT_DEF)
