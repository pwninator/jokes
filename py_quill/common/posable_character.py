"""Base class for posable sprite-based characters."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum

from PIL import Image
from common import utils
from common.models import _parse_int_field
from services import cloud_storage


class MouthState(Enum):
  """State of the mouth for a posable character."""

  CLOSED = "CLOSED"
  OPEN = "OPEN"
  O = "O"


@dataclass(frozen=True)
class Transform:
  """Translation and scaling transform for a sprite component."""

  translate_x: float = 0.0
  translate_y: float = 0.0
  scale_x: float = 1.0
  scale_y: float = 1.0

  @staticmethod
  def from_tuple(
    values: tuple[float, float] | tuple[float, float, float, float]
  ) -> "Transform":
    """Create a Transform from (tx, ty) or (tx, ty, sx, sy)."""
    if len(values) == 2:
      translate_x, translate_y = values
      return Transform(translate_x=translate_x, translate_y=translate_y)
    if len(values) == 4:
      translate_x, translate_y, scale_x, scale_y = values
      return Transform(
        translate_x=translate_x,
        translate_y=translate_y,
        scale_x=scale_x,
        scale_y=scale_y,
      )
    raise ValueError("Transform tuple must have 2 or 4 values")


@dataclass(kw_only=True)
class PosableCharacter:
  """Base class for sprite-based characters with posable components."""

  key: str | None = None
  name: str | None = None

  width: int = 0
  height: int = 0

  head_gcs_uri: str = ""
  left_hand_gcs_uri: str = ""
  right_hand_gcs_uri: str = ""
  mouth_open_gcs_uri: str = ""
  mouth_closed_gcs_uri: str = ""
  mouth_o_gcs_uri: str = ""
  left_eye_open_gcs_uri: str = ""
  left_eye_closed_gcs_uri: str = ""
  right_eye_open_gcs_uri: str = ""
  right_eye_closed_gcs_uri: str = ""

  # Transient state (not stored in Firestore)
  left_eye_open: bool = field(default=True, init=False)
  right_eye_open: bool = field(default=True, init=False)
  mouth_state: MouthState = field(default=MouthState.OPEN, init=False)
  left_hand_visible: bool = field(default=True, init=False)
  right_hand_visible: bool = field(default=True, init=False)
  left_hand_transform: Transform = field(default_factory=Transform, init=False)
  right_hand_transform: Transform = field(default_factory=Transform,
                                          init=False)
  head_transform: Transform = field(default_factory=Transform, init=False)
  _image_cache: dict[tuple[object, ...], Image.Image] = field(
    default_factory=dict, init=False)
  _component_cache: dict[str, Image.Image] = field(
    default_factory=dict, init=False)

  def __post_init__(self):
    """Initialize transient state fields if they weren't set."""
    # Support legacy subclasses that define config as class attributes
    # If the instance value is default (0/empty), check if the class has a value.
    for field_name in [
      'width',
      'height',
      'head_gcs_uri',
      'left_hand_gcs_uri',
      'right_hand_gcs_uri',
      'mouth_open_gcs_uri',
      'mouth_closed_gcs_uri',
      'mouth_o_gcs_uri',
      'left_eye_open_gcs_uri',
      'left_eye_closed_gcs_uri',
      'right_eye_open_gcs_uri',
      'right_eye_closed_gcs_uri',
    ]:
      val = getattr(self, field_name)
      if not val:  # 0 or empty string
        class_val = getattr(type(self), field_name, None)
        # Only overwrite if the class value is "truthy" (actually set)
        # This handles cases where subclasses don't define it but inherit defaults
        if class_val:
          setattr(self, field_name, class_val)

    # Ensure transient fields are initialized even if subclasses override __init__
    if not hasattr(self, 'left_eye_open'):
      self.left_eye_open = True
    if not hasattr(self, 'right_eye_open'):
      self.right_eye_open = True
    if not hasattr(self, 'mouth_state'):
      self.mouth_state = MouthState.OPEN
    if not hasattr(self, 'left_hand_visible'):
      self.left_hand_visible = True
    if not hasattr(self, 'right_hand_visible'):
      self.right_hand_visible = True
    if not hasattr(self, 'left_hand_transform'):
      self.left_hand_transform = Transform()
    if not hasattr(self, 'right_hand_transform'):
      self.right_hand_transform = Transform()
    if not hasattr(self, 'head_transform'):
      self.head_transform = Transform()
    if not hasattr(self, '_image_cache'):
      self._image_cache = {}
    if not hasattr(self, '_component_cache'):
      self._component_cache = {}

  def to_dict(self, include_key: bool = False) -> dict:
    """Convert to dictionary for Firestore storage."""
    data = dataclasses.asdict(self)
    # Remove transient fields
    transient_fields = {
      'left_eye_open', 'right_eye_open', 'mouth_state', 'left_hand_visible',
      'right_hand_visible', 'left_hand_transform', 'right_hand_transform',
      'head_transform', '_image_cache', '_component_cache'
    }
    for field_name in transient_fields:
      data.pop(field_name, None)

    if not include_key:
      data.pop('key', None)
    return data

  @classmethod
  def from_firestore_dict(cls, data: dict, key: str) -> 'PosableCharacter':
    """Create a PosableCharacter from a Firestore dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)

    data['key'] = key

    _parse_int_field(data, 'width', 0)
    _parse_int_field(data, 'height', 0)

    # Filter to dataclass fields
    allowed = {f.name for f in dataclasses.fields(cls) if f.init}
    filtered = {k: v for k, v in data.items() if k in allowed}

    return cls(**filtered)

  def set_pose(
    self,
    *,
    left_eye_open: bool | None = None,
    right_eye_open: bool | None = None,
    mouth_state: MouthState | None = None,
    left_hand_visible: bool | None = None,
    right_hand_visible: bool | None = None,
    left_hand_transform: Transform | tuple[float, float]
    | tuple[float, float, float, float] | None = None,
    right_hand_transform: Transform | tuple[float, float]
    | tuple[float, float, float, float] | None = None,
    head_transform: Transform | tuple[float, float]
    | tuple[float, float, float, float] | None = None,
  ) -> None:
    """Set the pose state; only provided params are updated."""
    if left_eye_open is not None:
      self.left_eye_open = left_eye_open
    if right_eye_open is not None:
      self.right_eye_open = right_eye_open
    if mouth_state is not None:
      self.mouth_state = mouth_state
    if left_hand_visible is not None:
      self.left_hand_visible = left_hand_visible
    if right_hand_visible is not None:
      self.right_hand_visible = right_hand_visible
    if left_hand_transform is not None:
      self.left_hand_transform = _coerce_transform(left_hand_transform)
    if right_hand_transform is not None:
      self.right_hand_transform = _coerce_transform(right_hand_transform)
    if head_transform is not None:
      self.head_transform = _coerce_transform(head_transform)

  def get_image(self) -> Image.Image:
    """Return a PIL image of the current pose, using cache if available."""
    self._validate_assets()
    cache_key = self._get_pose_cache_key()
    cached = self._image_cache.get(cache_key)
    if cached is not None:
      return cached

    canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))

    head_image = self._load_component(self.head_gcs_uri)
    self._paste_component(canvas, head_image, self.head_transform)

    left_eye_uri = (self.left_eye_open_gcs_uri
                    if self.left_eye_open else self.left_eye_closed_gcs_uri)
    right_eye_uri = (self.right_eye_open_gcs_uri
                     if self.right_eye_open else self.right_eye_closed_gcs_uri)
    mouth_uri = _get_mouth_gcs_uri(self)

    left_eye_image = self._load_component(left_eye_uri)
    right_eye_image = self._load_component(right_eye_uri)
    mouth_image = self._load_component(mouth_uri)

    self._paste_component(canvas, left_eye_image, self.head_transform)
    self._paste_component(canvas, right_eye_image, self.head_transform)
    self._paste_component(canvas, mouth_image, self.head_transform)

    if self.left_hand_visible:
      left_hand_image = self._load_component(self.left_hand_gcs_uri)
      self._paste_component(canvas, left_hand_image, self.left_hand_transform)
    if self.right_hand_visible:
      right_hand_image = self._load_component(self.right_hand_gcs_uri)
      self._paste_component(canvas, right_hand_image,
                            self.right_hand_transform)

    self._image_cache[cache_key] = canvas
    return canvas

  def _get_pose_cache_key(self) -> tuple[object, ...]:
    return (
      self.left_eye_open,
      self.right_eye_open,
      self.mouth_state,
      self.left_hand_visible,
      self.right_hand_visible,
      self.left_hand_transform,
      self.right_hand_transform,
      self.head_transform,
    )

  def _load_component(self, gcs_uri: str) -> Image.Image:
    cached = self._component_cache.get(gcs_uri)
    if cached is not None:
      return cached
    image = cloud_storage.download_image_from_gcs(gcs_uri).convert("RGBA")
    self._component_cache[gcs_uri] = image
    return image

  def _paste_component(self, canvas: Image.Image, component: Image.Image,
                       transform: Transform) -> None:
    transformed, x, y = self._apply_transform(component, transform,
                                              canvas.size)
    canvas.paste(transformed, (x, y), transformed)

  def _apply_transform(
    self,
    component: Image.Image,
    transform: Transform,
    canvas_size: tuple[int, int],
  ) -> tuple[Image.Image, int, int]:
    target_width = max(1, int(round(component.width * transform.scale_x)))
    target_height = max(1, int(round(component.height * transform.scale_y)))
    resized = component
    if (target_width, target_height) != component.size:
      resized = component.resize(
        (target_width, target_height),
        resample=Image.Resampling.LANCZOS,
      )
    base_x = (canvas_size[0] - target_width) / 2
    base_y = (canvas_size[1] - target_height) / 2
    x = int(round(base_x + transform.translate_x))
    y = int(round(base_y + transform.translate_y))
    return resized, x, y

  def _validate_assets(self) -> None:
    required = {
      "width": self.width,
      "height": self.height,
      "head_gcs_uri": self.head_gcs_uri,
      "left_hand_gcs_uri": self.left_hand_gcs_uri,
      "right_hand_gcs_uri": self.right_hand_gcs_uri,
      "mouth_open_gcs_uri": self.mouth_open_gcs_uri,
      "mouth_closed_gcs_uri": self.mouth_closed_gcs_uri,
      "mouth_o_gcs_uri": self.mouth_o_gcs_uri,
      "left_eye_open_gcs_uri": self.left_eye_open_gcs_uri,
      "left_eye_closed_gcs_uri": self.left_eye_closed_gcs_uri,
      "right_eye_open_gcs_uri": self.right_eye_open_gcs_uri,
      "right_eye_closed_gcs_uri": self.right_eye_closed_gcs_uri,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
      raise ValueError("PosableCharacter subclass must define: " +
                       ", ".join(missing))


def _coerce_transform(
  transform: Transform | tuple[float, float]
  | tuple[float, float, float, float]
) -> Transform:
  if isinstance(transform, Transform):
    return transform
  return Transform.from_tuple(transform)


def _get_mouth_gcs_uri(character: PosableCharacter) -> str:
  if character.mouth_state == MouthState.OPEN:
    return character.mouth_open_gcs_uri
  if character.mouth_state == MouthState.O:
    return character.mouth_o_gcs_uri
  return character.mouth_closed_gcs_uri
