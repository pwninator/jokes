"""Base class for posable sprite-based characters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from common import models
from PIL import Image
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


@dataclass(frozen=True)
class PoseState:
  """Complete pose state for a posable character."""

  left_eye_open: bool = True
  right_eye_open: bool = True
  mouth_state: MouthState = MouthState.OPEN
  left_hand_visible: bool = True
  right_hand_visible: bool = True
  left_hand_transform: Transform = Transform()
  right_hand_transform: Transform = Transform()
  head_transform: Transform = Transform()
  surface_line_offset: float = 50.0
  mask_boundary_offset: float = 50.0
  surface_line_visible: bool = True
  head_masking_enabled: bool = True
  left_hand_masking_enabled: bool = False
  right_hand_masking_enabled: bool = False

  def with_updates(
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
    surface_line_offset: float | None = None,
    mask_boundary_offset: float | None = None,
    surface_line_visible: bool | None = None,
    head_masking_enabled: bool | None = None,
    left_hand_masking_enabled: bool | None = None,
    right_hand_masking_enabled: bool | None = None,
  ) -> PoseState:
    """Return a new PoseState with selected fields updated."""
    return PoseState(
      left_eye_open=(self.left_eye_open
                     if left_eye_open is None else bool(left_eye_open)),
      right_eye_open=(self.right_eye_open
                      if right_eye_open is None else bool(right_eye_open)),
      mouth_state=(self.mouth_state if mouth_state is None else mouth_state),
      left_hand_visible=(self.left_hand_visible if left_hand_visible is None
                         else bool(left_hand_visible)),
      right_hand_visible=(self.right_hand_visible if right_hand_visible is None
                          else bool(right_hand_visible)),
      left_hand_transform=(self.left_hand_transform
                           if left_hand_transform is None else
                           _coerce_transform(left_hand_transform)),
      right_hand_transform=(self.right_hand_transform
                            if right_hand_transform is None else
                            _coerce_transform(right_hand_transform)),
      head_transform=(self.head_transform if head_transform is None else
                      _coerce_transform(head_transform)),
      surface_line_offset=(self.surface_line_offset if surface_line_offset
                           is None else float(surface_line_offset)),
      mask_boundary_offset=(self.mask_boundary_offset if mask_boundary_offset
                            is None else float(mask_boundary_offset)),
      surface_line_visible=(self.surface_line_visible if surface_line_visible
                            is None else bool(surface_line_visible)),
      head_masking_enabled=(self.head_masking_enabled if head_masking_enabled
                            is None else bool(head_masking_enabled)),
      left_hand_masking_enabled=(self.left_hand_masking_enabled
                                 if left_hand_masking_enabled is None else
                                 bool(left_hand_masking_enabled)),
      right_hand_masking_enabled=(self.right_hand_masking_enabled
                                  if right_hand_masking_enabled is None else
                                  bool(right_hand_masking_enabled)),
    )


class PosableCharacter:
  """Runtime character renderer with cached sprites for a pose state."""

  def __init__(
    self,
    definition: models.PosableCharacterDef,
    *,
    pose_state: PoseState | None = None,
  ):
    self.definition = definition
    self._pose_state = pose_state or PoseState()
    self._image_cache: dict[tuple[object, ...], Image.Image] = {}
    self._component_cache: dict[str, Image.Image] = {}

  @classmethod
  def from_def(
    cls,
    definition: models.PosableCharacterDef,
  ) -> PosableCharacter:
    """Create a PosableCharacter instance from a definition."""
    return cls(definition=definition)

  @property
  def pose_state(self) -> PoseState:
    """Current full pose state."""
    return self._pose_state

  @pose_state.setter
  def pose_state(self, value: PoseState) -> None:
    if not isinstance(value, PoseState):
      raise TypeError("pose_state must be a PoseState")
    self._pose_state = value

  @property
  def left_eye_open(self) -> bool:
    return self._pose_state.left_eye_open

  @left_eye_open.setter
  def left_eye_open(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(left_eye_open=bool(value))

  @property
  def right_eye_open(self) -> bool:
    return self._pose_state.right_eye_open

  @right_eye_open.setter
  def right_eye_open(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      right_eye_open=bool(value))

  @property
  def mouth_state(self) -> MouthState:
    return self._pose_state.mouth_state

  @mouth_state.setter
  def mouth_state(self, value: MouthState) -> None:
    self._pose_state = self._pose_state.with_updates(mouth_state=value)

  @property
  def left_hand_visible(self) -> bool:
    return self._pose_state.left_hand_visible

  @left_hand_visible.setter
  def left_hand_visible(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      left_hand_visible=bool(value))

  @property
  def right_hand_visible(self) -> bool:
    return self._pose_state.right_hand_visible

  @right_hand_visible.setter
  def right_hand_visible(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      right_hand_visible=bool(value))

  @property
  def left_hand_transform(self) -> Transform:
    return self._pose_state.left_hand_transform

  @left_hand_transform.setter
  def left_hand_transform(
    self,
    value: Transform | tuple[float, float]
    | tuple[float, float, float, float],
  ) -> None:
    self._pose_state = self._pose_state.with_updates(left_hand_transform=value)

  @property
  def right_hand_transform(self) -> Transform:
    return self._pose_state.right_hand_transform

  @right_hand_transform.setter
  def right_hand_transform(
    self,
    value: Transform | tuple[float, float]
    | tuple[float, float, float, float],
  ) -> None:
    self._pose_state = self._pose_state.with_updates(
      right_hand_transform=value)

  @property
  def head_transform(self) -> Transform:
    return self._pose_state.head_transform

  @head_transform.setter
  def head_transform(
    self,
    value: Transform | tuple[float, float]
    | tuple[float, float, float, float],
  ) -> None:
    self._pose_state = self._pose_state.with_updates(head_transform=value)

  @property
  def surface_line_offset(self) -> float:
    return self._pose_state.surface_line_offset

  @surface_line_offset.setter
  def surface_line_offset(self, value: float) -> None:
    self._pose_state = self._pose_state.with_updates(surface_line_offset=value)

  @property
  def mask_boundary_offset(self) -> float:
    return self._pose_state.mask_boundary_offset

  @mask_boundary_offset.setter
  def mask_boundary_offset(self, value: float) -> None:
    self._pose_state = self._pose_state.with_updates(
      mask_boundary_offset=value)

  @property
  def surface_line_visible(self) -> bool:
    return self._pose_state.surface_line_visible

  @surface_line_visible.setter
  def surface_line_visible(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      surface_line_visible=bool(value))

  @property
  def head_masking_enabled(self) -> bool:
    return self._pose_state.head_masking_enabled

  @head_masking_enabled.setter
  def head_masking_enabled(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      head_masking_enabled=bool(value))

  @property
  def left_hand_masking_enabled(self) -> bool:
    return self._pose_state.left_hand_masking_enabled

  @left_hand_masking_enabled.setter
  def left_hand_masking_enabled(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      left_hand_masking_enabled=bool(value))

  @property
  def right_hand_masking_enabled(self) -> bool:
    return self._pose_state.right_hand_masking_enabled

  @right_hand_masking_enabled.setter
  def right_hand_masking_enabled(self, value: bool) -> None:
    self._pose_state = self._pose_state.with_updates(
      right_hand_masking_enabled=bool(value))

  def apply_pose_state(self, pose_state: PoseState) -> None:
    """Set the full pose state at once."""
    self.pose_state = pose_state

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
    surface_line_offset: float | None = None,
    mask_boundary_offset: float | None = None,
    surface_line_visible: bool | None = None,
    head_masking_enabled: bool | None = None,
    left_hand_masking_enabled: bool | None = None,
    right_hand_masking_enabled: bool | None = None,
  ) -> None:
    """Set the pose state; only provided params are updated."""
    self._pose_state = self._pose_state.with_updates(
      left_eye_open=left_eye_open,
      right_eye_open=right_eye_open,
      mouth_state=mouth_state,
      left_hand_visible=left_hand_visible,
      right_hand_visible=right_hand_visible,
      left_hand_transform=left_hand_transform,
      right_hand_transform=right_hand_transform,
      head_transform=head_transform,
      surface_line_offset=surface_line_offset,
      mask_boundary_offset=mask_boundary_offset,
      surface_line_visible=surface_line_visible,
      head_masking_enabled=head_masking_enabled,
      left_hand_masking_enabled=left_hand_masking_enabled,
      right_hand_masking_enabled=right_hand_masking_enabled,
    )

  def get_image(self) -> Image.Image:
    """Return a PIL image of the current pose, using cache if available."""
    self._validate_assets()
    pose = self._pose_state
    cache_key = self._get_pose_cache_key()
    cached = self._image_cache.get(cache_key)
    if cached is not None:
      return cached

    def_ = self.definition
    canvas = Image.new("RGBA", (def_.width, def_.height), (0, 0, 0, 0))

    head_mask_boundary = (pose.mask_boundary_offset
                          if pose.head_masking_enabled else None)
    head_image = self._load_component(def_.head_gcs_uri)
    self._paste_component(
      canvas,
      head_image,
      pose.head_transform,
      mask_boundary_offset=head_mask_boundary,
    )

    left_eye_uri = (def_.left_eye_open_gcs_uri
                    if pose.left_eye_open else def_.left_eye_closed_gcs_uri)
    right_eye_uri = (def_.right_eye_open_gcs_uri
                     if pose.right_eye_open else def_.right_eye_closed_gcs_uri)
    mouth_uri = _get_mouth_gcs_uri(definition=def_, pose_state=pose)

    left_eye_image = self._load_component(left_eye_uri)
    right_eye_image = self._load_component(right_eye_uri)
    mouth_image = self._load_component(mouth_uri)

    self._paste_component(
      canvas,
      left_eye_image,
      pose.head_transform,
      mask_boundary_offset=head_mask_boundary,
    )
    self._paste_component(
      canvas,
      right_eye_image,
      pose.head_transform,
      mask_boundary_offset=head_mask_boundary,
    )
    self._paste_component(
      canvas,
      mouth_image,
      pose.head_transform,
      mask_boundary_offset=head_mask_boundary,
    )

    if pose.surface_line_visible:
      surface_line_image = self._load_component(def_.surface_line_gcs_uri)
      self._paste_surface_line(
        canvas=canvas,
        component=surface_line_image,
        surface_line_offset=pose.surface_line_offset,
      )

    if pose.left_hand_visible:
      left_hand_image = self._load_component(def_.left_hand_gcs_uri)
      self._paste_component(
        canvas,
        left_hand_image,
        pose.left_hand_transform,
        mask_boundary_offset=(pose.mask_boundary_offset
                              if pose.left_hand_masking_enabled else None),
      )
    if pose.right_hand_visible:
      right_hand_image = self._load_component(def_.right_hand_gcs_uri)
      self._paste_component(
        canvas,
        right_hand_image,
        pose.right_hand_transform,
        mask_boundary_offset=(pose.mask_boundary_offset
                              if pose.right_hand_masking_enabled else None),
      )

    self._image_cache[cache_key] = canvas
    return canvas

  def _get_pose_cache_key(self) -> tuple[object, ...]:
    return (self._pose_state, )

  def _load_component(self, gcs_uri: str) -> Image.Image:
    cached = self._component_cache.get(gcs_uri)
    if cached is not None:
      return cached
    image = cloud_storage.download_image_from_gcs(gcs_uri).convert("RGBA")
    self._component_cache[gcs_uri] = image
    return image

  def _paste_component(
    self,
    canvas: Image.Image,
    component: Image.Image,
    transform: Transform,
    *,
    mask_boundary_offset: float | None = None,
  ) -> None:
    transformed, x, y = self._apply_transform(component, transform,
                                              canvas.size)
    if mask_boundary_offset is not None:
      transformed = self._apply_mask_below_boundary(
        component=transformed,
        component_y=y,
        canvas_height=canvas.height,
        boundary_offset=mask_boundary_offset,
      )
    canvas.paste(transformed, (x, y), transformed)

  def _paste_surface_line(
    self,
    *,
    canvas: Image.Image,
    component: Image.Image,
    surface_line_offset: float,
  ) -> None:
    x = int(round((canvas.width - component.width) / 2))
    y = int(round(canvas.height - float(surface_line_offset)))
    canvas.paste(component, (x, y), component)

  def _apply_mask_below_boundary(
    self,
    *,
    component: Image.Image,
    component_y: int,
    canvas_height: int,
    boundary_offset: float,
  ) -> Image.Image:
    cutoff_y = int(round(canvas_height - float(boundary_offset)))
    visible_height = cutoff_y - int(component_y)
    if visible_height >= component.height:
      return component
    if visible_height <= 0:
      return Image.new("RGBA", component.size, (0, 0, 0, 0))

    clipped = component.copy()
    clipped.paste((0, 0, 0, 0),
                  (0, visible_height, clipped.width, clipped.height))
    return clipped

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
    d = self.definition
    required = {
      "width": d.width,
      "height": d.height,
      "head_gcs_uri": d.head_gcs_uri,
      "surface_line_gcs_uri": d.surface_line_gcs_uri,
      "left_hand_gcs_uri": d.left_hand_gcs_uri,
      "right_hand_gcs_uri": d.right_hand_gcs_uri,
      "mouth_open_gcs_uri": d.mouth_open_gcs_uri,
      "mouth_closed_gcs_uri": d.mouth_closed_gcs_uri,
      "mouth_o_gcs_uri": d.mouth_o_gcs_uri,
      "left_eye_open_gcs_uri": d.left_eye_open_gcs_uri,
      "left_eye_closed_gcs_uri": d.left_eye_closed_gcs_uri,
      "right_eye_open_gcs_uri": d.right_eye_open_gcs_uri,
      "right_eye_closed_gcs_uri": d.right_eye_closed_gcs_uri,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
      raise ValueError("PosableCharacter definition must have: " +
                       ", ".join(missing))


def _coerce_transform(
  transform: Transform | tuple[float, float]
  | tuple[float, float, float, float]
) -> Transform:
  if isinstance(transform, Transform):
    return transform
  return Transform.from_tuple(transform)


def _get_mouth_gcs_uri(
  *,
  definition: models.PosableCharacterDef,
  pose_state: PoseState,
) -> str:
  if pose_state.mouth_state == MouthState.OPEN:
    return definition.mouth_open_gcs_uri
  if pose_state.mouth_state == MouthState.O:
    return definition.mouth_o_gcs_uri
  return definition.mouth_closed_gcs_uri
