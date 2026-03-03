"""Operations for jokes."""

from __future__ import annotations

import datetime
import random
from io import BytesIO
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from common import image_generation, models
from firebase_functions import logger
from functions.prompts import joke_operation_prompts
from google.cloud.firestore_v1.field_path import FieldPath
from google.cloud.firestore_v1.vector import Vector
from PIL import Image
from services import cloud_storage, firestore, image_client, image_editor

_IMAGE_UPSCALE_FACTOR = "x2"
_HIGH_QUALITY_UPSCALE_FACTOR = "x2"

_MIME_TYPE_CONFIG: dict[str, tuple[str, str]] = {
  "image/png": ("PNG", "png"),
  "image/jpeg": ("JPEG", "jpg"),
}
_BATCHES_COLLECTION = "joke_schedule_batches"
_DAILY_SCHEDULE_ID = "daily_jokes"
_LA_TIMEZONE = ZoneInfo("America/Los_Angeles")
_ADMIN_MUTABLE_STATES = {
  models.JokeState.UNREVIEWED,
  models.JokeState.APPROVED,
  models.JokeState.REJECTED,
}
_SELECTABLE_TARGET_STATES = {
  models.JokeState.UNREVIEWED,
  models.JokeState.APPROVED,
  models.JokeState.REJECTED,
  models.JokeState.PUBLISHED,
  models.JokeState.DAILY,
}


class JokeOperationsError(Exception):
  """Base exception for joke operation failures."""


class JokeNotFoundError(JokeOperationsError):
  """Exception raised when a requested joke cannot be found."""


class JokePopulationError(JokeOperationsError):
  """Exception raised for errors in joke population."""


SafetyCheckError = joke_operation_prompts.SafetyCheckError


def initialize_joke(
  *,
  joke_id: str | None,
  user_id: str | None,
  admin_owned: bool,
  setup_text: str | None = None,
  punchline_text: str | None = None,
  seasonal: str | None = None,
  tags: list[str] | str | None = None,
  setup_scene_idea: str | None = None,
  punchline_scene_idea: str | None = None,
  setup_image_description: str | None = None,
  punchline_image_description: str | None = None,
  setup_image_url: str | None = None,
  punchline_image_url: str | None = None,
) -> models.PunnyJoke:
  """Load or create a joke and apply the provided overrides."""
  joke: models.PunnyJoke | None = None
  if joke_id:
    joke = firestore.get_punny_joke(joke_id)
    if not joke:
      raise JokeNotFoundError(f'Joke not found: {joke_id}')
  else:
    setup_text = setup_text.strip() if setup_text else None
    punchline_text = (punchline_text.strip() if punchline_text else None)
    if not setup_text:
      raise ValueError('Setup text is required')
    if not punchline_text:
      raise ValueError('Punchline text is required')
    if not user_id:
      raise ValueError('user_id is required when creating a joke')
    owner_user_id = "ADMIN" if admin_owned else user_id
    joke = models.PunnyJoke(
      setup_text=setup_text,
      punchline_text=punchline_text,
      owner_user_id=owner_user_id,
      state=models.JokeState.DRAFT,
      random_id=random.randint(0, 2**31 - 1),
    )

  if setup_text is not None:
    joke.setup_text = setup_text
  if punchline_text is not None:
    joke.punchline_text = punchline_text
  if seasonal is not None:
    joke.seasonal = seasonal
  if tags is not None:
    if isinstance(tags, str):
      joke.tags = [t.strip() for t in tags.split(',') if t.strip()]
    else:
      joke.tags = [t.strip() for t in tags if t.strip()]
  if setup_scene_idea is not None:
    joke.setup_scene_idea = setup_scene_idea
  if punchline_scene_idea is not None:
    joke.punchline_scene_idea = punchline_scene_idea
  if setup_image_description is not None:
    joke.setup_image_description = setup_image_description
  if punchline_image_description is not None:
    joke.punchline_image_description = punchline_image_description
  if setup_image_url is not None:
    if setup_image_url != joke.setup_image_url:
      joke.setup_image_url_upscaled = None
    joke.setup_image_url = setup_image_url
    if setup_image_url and setup_image_url not in joke.all_setup_image_urls:
      joke.all_setup_image_urls.append(setup_image_url)
  if punchline_image_url is not None:
    if punchline_image_url != joke.punchline_image_url:
      joke.punchline_image_url_upscaled = None
    joke.punchline_image_url = punchline_image_url
    if (punchline_image_url
        and punchline_image_url not in joke.all_punchline_image_urls):
      joke.all_punchline_image_urls.append(punchline_image_url)

  return joke


def regenerate_scene_ideas(joke: models.PunnyJoke) -> models.PunnyJoke:
  """Generate fresh scene ideas from the joke's text."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError('Setup and punchline text are required to build scenes')

  (
    setup_scene_idea,
    punchline_scene_idea,
    idea_generation_metadata,
  ) = joke_operation_prompts.generate_joke_scene_ideas(
    setup_text=joke.setup_text,
    punchline_text=joke.punchline_text,
  )

  joke.setup_scene_idea = setup_scene_idea
  joke.punchline_scene_idea = punchline_scene_idea
  joke.generation_metadata.add_generation(idea_generation_metadata)
  return joke


def modify_image_scene_ideas(
  joke: models.PunnyJoke,
  setup_suggestion: str | None,
  punchline_suggestion: str | None,
) -> models.PunnyJoke:
  """Update a joke's image scene ideas using the provided suggestions."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError('Joke is missing text required to edit scene ideas')
  if not joke.setup_scene_idea or not joke.punchline_scene_idea:
    raise ValueError('Joke must have existing scene ideas to edit')

  setup_instruction = setup_suggestion.strip() if setup_suggestion else ''
  punchline_instruction = (punchline_suggestion.strip()
                           if punchline_suggestion else '')

  if not (setup_instruction or punchline_instruction):
    raise ValueError('At least one suggestion is required to modify scenes')

  (
    updated_setup_scene,
    updated_punchline_scene,
    metadata,
  ) = joke_operation_prompts.modify_scene_ideas_with_suggestions(
    setup_text=joke.setup_text,
    punchline_text=joke.punchline_text,
    current_setup_scene_idea=joke.setup_scene_idea,
    current_punchline_scene_idea=joke.punchline_scene_idea,
    setup_suggestion=setup_instruction,
    punchline_suggestion=punchline_instruction,
  )

  joke.setup_scene_idea = updated_setup_scene
  joke.punchline_scene_idea = updated_punchline_scene
  joke.generation_metadata.add_generation(metadata)

  return joke


def generate_image_descriptions(joke: models.PunnyJoke) -> models.PunnyJoke:
  """Ensure the joke has detailed image descriptions derived from scene ideas."""
  if not joke.setup_text or not joke.punchline_text:
    raise JokePopulationError('Joke is missing setup or punchline text')
  if not joke.setup_scene_idea or not joke.punchline_scene_idea:
    raise JokePopulationError('Joke is missing scene ideas')

  setup_description, punchline_description, metadata = (
    joke_operation_prompts.generate_detailed_image_descriptions(
      setup_text=joke.setup_text,
      punchline_text=joke.punchline_text,
      setup_scene_idea=joke.setup_scene_idea,
      punchline_scene_idea=joke.punchline_scene_idea,
    ))

  joke.setup_image_description = setup_description
  joke.punchline_image_description = punchline_description
  joke.generation_metadata.add_generation(metadata)
  return joke


def generate_joke_images(joke: models.PunnyJoke,
                         image_quality: str) -> models.PunnyJoke:
  """Populate a joke with new images using the image generation service."""
  if not joke.setup_text:
    raise JokePopulationError('Joke is missing setup text')
  if not joke.punchline_text:
    raise JokePopulationError('Joke is missing punchline text')
  if not joke.setup_image_description or not joke.punchline_image_description:
    joke = generate_image_descriptions(joke)
  if not joke.setup_image_description or not joke.punchline_image_description:
    raise JokePopulationError('Joke image description generation failed')

  setup_image, punchline_image = image_generation.generate_pun_images(
    setup_text=joke.setup_text,
    setup_image_description=joke.setup_image_description,
    punchline_text=joke.punchline_text,
    punchline_image_description=joke.punchline_image_description,
    image_quality=image_quality,
  )

  joke.set_setup_image(setup_image)
  joke.set_punchline_image(punchline_image)

  joke.setup_image_url_upscaled = None
  joke.punchline_image_url_upscaled = None

  if joke.state == models.JokeState.DRAFT:
    joke.state = models.JokeState.UNREVIEWED

  return joke


def upscale_joke(
  joke_id: str,
  mime_type: Literal["image/png", "image/jpeg"] = "image/png",
  *,
  compression_quality: int | None = None,
  overwrite: bool = False,
  high_quality: bool = False,
) -> models.PunnyJoke:
  """Upscales a joke's images.

  If overwrite is False, this function is idempotent. If the joke already
  has upscaled URLs, it will return immediately.

  Args:
    joke_id: The ID of the joke to upscale.
    mime_type: The MIME type of the image.
    compression_quality: The compression quality of the image.
    overwrite: Whether to force re-upscaling even if URLs already exist.
    high_quality: Whether to use high-quality upscaling and replace base images.
  """
  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')

  setup_needs_upscale = bool(joke.setup_image_url and
                             (overwrite or not joke.setup_image_url_upscaled))
  punchline_needs_upscale = bool(
    joke.punchline_image_url
    and (overwrite or not joke.punchline_image_url_upscaled))

  if not (setup_needs_upscale or punchline_needs_upscale):
    return joke

  model = (image_client.ImageModel.IMAGEN_4_UPSCALE
           if high_quality else image_client.ImageModel.IMAGEN_1)
  upscale_factor = (_HIGH_QUALITY_UPSCALE_FACTOR
                    if high_quality else _IMAGE_UPSCALE_FACTOR)
  client = image_client.get_client(
    label="upscale_joke_high" if high_quality else "upscale_joke_standard",
    model=model,
    file_name_base="upscaled_joke_image",
  )
  update_data: dict[str, object] = {}

  if setup_needs_upscale:
    update_data.update(
      _process_upscale_for_image(
        joke=joke,
        image_role="setup",
        client=client,
        mime_type=mime_type,
        compression_quality=compression_quality,
        upscale_factor=upscale_factor,
        replace_original=high_quality,
      ))

  if punchline_needs_upscale:
    update_data.update(
      _process_upscale_for_image(
        joke=joke,
        image_role="punchline",
        client=client,
        mime_type=mime_type,
        compression_quality=compression_quality,
        upscale_factor=upscale_factor,
        replace_original=high_quality,
      ))

  update_data["generation_metadata"] = joke.generation_metadata.as_dict
  _ = firestore.update_punny_joke(joke_id, update_data)

  return joke


def _process_upscale_for_image(
  *,
  joke: models.PunnyJoke,
  image_role: Literal["setup", "punchline"],
  client: image_client.ImageClient[object],
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscale_factor: Literal["x2", "x4"],
  replace_original: bool,
) -> dict[str, object]:
  """Upscale a single image (setup or punchline) and return updated fields."""
  match image_role:
    case "setup":
      source_url = joke.setup_image_url
      upscaled_attr = "setup_image_url_upscaled"
      all_urls_attr = "all_setup_image_urls"
    case "punchline":
      source_url = joke.punchline_image_url
      upscaled_attr = "punchline_image_url_upscaled"
      all_urls_attr = "all_punchline_image_urls"

  if not source_url:
    return {}

  gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(source_url)
  upscaled_image = client.upscale_image(
    upscale_factor=upscale_factor,
    mime_type=mime_type,
    compression_quality=compression_quality,
    gcs_uri=gcs_uri,
  )

  if image_role == "setup":
    joke.setup_image_url_upscaled = upscaled_image.url_upscaled
  else:
    joke.punchline_image_url_upscaled = upscaled_image.url_upscaled
  joke.generation_metadata.add_generation(upscaled_image.generation_metadata)

  update_data: dict[str, object] = {upscaled_attr: upscaled_image.url_upscaled}

  if replace_original and upscaled_image.gcs_uri_upscaled:
    original_dimensions = _get_image_dimensions(gcs_uri)
    downscaled_gcs_uri, downscaled_url = _create_downscaled_image(
      joke=joke,
      image_role=image_role,
      editor=image_editor.ImageEditor(),
      target_dimensions=original_dimensions,
      mime_type=mime_type,
      compression_quality=compression_quality,
      upscaled_image_gcs_uri=upscaled_image.gcs_uri_upscaled,
    )
    replacement_image = models.Image(
      url=downscaled_url,
      gcs_uri=downscaled_gcs_uri,
      url_upscaled=upscaled_image.url_upscaled,
      gcs_uri_upscaled=upscaled_image.gcs_uri_upscaled,
      generation_metadata=models.GenerationMetadata(),  # Already added above
    )
    match image_role:
      case "setup":
        joke.set_setup_image(replacement_image, update_text=False)
        update_data["setup_image_url"] = joke.setup_image_url
      case "punchline":
        joke.set_punchline_image(replacement_image, update_text=False)
        update_data["punchline_image_url"] = joke.punchline_image_url

    update_data[all_urls_attr] = getattr(joke, all_urls_attr)

  return update_data


def _get_image_dimensions(gcs_uri: str) -> tuple[int, int]:
  """Load image dimensions from GCS."""
  with Image.open(BytesIO(
      cloud_storage.download_bytes_from_gcs(gcs_uri))) as img:
    return img.width, img.height


def _create_downscaled_image(
  *,
  joke: models.PunnyJoke,
  image_role: str,
  editor: image_editor.ImageEditor,
  target_dimensions: tuple[int, int],
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscaled_image_gcs_uri: str,
) -> tuple[str, str]:
  """Create a downscaled image that matches the original dimensions."""
  upscaled_image = cloud_storage.download_image_from_gcs(
    upscaled_image_gcs_uri)
  target_width, target_height = target_dimensions

  if upscaled_image.width == 0 or upscaled_image.height == 0:
    raise ValueError("Upscaled image has invalid dimensions")

  scale_factor = min(
    target_width / upscaled_image.width,
    target_height / upscaled_image.height,
  )
  scaled_image = editor.scale_image(upscaled_image, scale_factor)
  if (scaled_image.width, scaled_image.height) != target_dimensions:
    scaled_image = scaled_image.resize(
      size=target_dimensions,
      resample=Image.Resampling.LANCZOS,
    )

  image_bytes = _image_to_bytes(
    scaled_image,
    mime_type=mime_type,
    compression_quality=compression_quality,
  )

  _, extension = _MIME_TYPE_CONFIG[mime_type]
  file_base = f"{joke.key or 'joke'}_{image_role}_hq"
  downscaled_gcs_uri = cloud_storage.get_image_gcs_uri(file_base, extension)
  _ = cloud_storage.upload_bytes_to_gcs(
    content_bytes=image_bytes,
    gcs_uri=downscaled_gcs_uri,
    content_type=mime_type,
  )
  downscaled_url = cloud_storage.get_final_image_url(downscaled_gcs_uri,
                                                     width=target_width)
  return downscaled_gcs_uri, downscaled_url


def _image_to_bytes(
  image: Image.Image,
  *,
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
) -> bytes:
  """Serialize an image to bytes according to the provided MIME type."""
  format_name, _ = _MIME_TYPE_CONFIG[mime_type]
  save_kwargs: dict[str, int | bool] = {}

  if mime_type == "image/jpeg":
    if image.mode not in ("RGB", "L"):
      image = image.convert("RGB")
    save_kwargs["quality"] = compression_quality or 95
    save_kwargs["optimize"] = True
  elif mime_type == "image/png" and image.mode == "CMYK":
    image = image.convert("RGBA")

  buffer = BytesIO()
  image.save(buffer, format=format_name, **save_kwargs)
  return buffer.getvalue()


def _parse_target_state(
  target_state: models.JokeState | str, ) -> models.JokeState:
  if isinstance(target_state, models.JokeState):
    return target_state
  try:
    return models.JokeState(str(target_state))
  except ValueError as exc:
    raise ValueError(f"Unsupported new_state: {target_state}") from exc


def _transition_loaded_joke_to_state(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  target_state: models.JokeState,
  now_utc: datetime.datetime,
) -> models.PunnyJoke:
  current_state = joke.state
  if current_state == target_state:
    if current_state == models.JokeState.DAILY and not _is_future_daily(
        joke, now_utc=now_utc):
      raise ValueError('Past and current daily jokes cannot be changed')
    return joke

  reachable_states = _get_reachable_target_states(joke, now_utc=now_utc)
  if target_state not in reachable_states:
    raise ValueError(
      f'Cannot transition joke "{joke_id}" from {current_state.value} '
      f'to {target_state.value}')

  if target_state in _ADMIN_MUTABLE_STATES:
    joke = _normalize_to_admin_state(joke_id=joke_id,
                                     joke=joke,
                                     now_utc=now_utc)
    return _set_admin_rating_and_state(
      joke_id=joke_id,
      joke=joke,
      rating=_admin_rating_for_state(target_state),
    )

  if target_state == models.JokeState.PUBLISHED:
    joke = _normalize_to_admin_state(joke_id=joke_id,
                                     joke=joke,
                                     now_utc=now_utc)
    if joke.state != models.JokeState.APPROVED:
      joke = _set_admin_rating_and_state(
        joke_id=joke_id,
        joke=joke,
        rating=models.JokeAdminRating.APPROVED,
      )
    return _publish_joke_immediately(joke_id=joke_id,
                                     joke=joke,
                                     now_utc=now_utc)

  if target_state == models.JokeState.DAILY:
    if joke.state == models.JokeState.PUBLISHED:
      return _schedule_joke_to_next_available_daily(
        joke_id=joke_id,
        joke=joke,
        now_utc=now_utc,
      )
    joke = _normalize_to_admin_state(joke_id=joke_id,
                                     joke=joke,
                                     now_utc=now_utc)
    if joke.state != models.JokeState.APPROVED:
      joke = _set_admin_rating_and_state(
        joke_id=joke_id,
        joke=joke,
        rating=models.JokeAdminRating.APPROVED,
      )
    if joke.state != models.JokeState.PUBLISHED:
      joke = _publish_joke_immediately(
        joke_id=joke_id,
        joke=joke,
        now_utc=now_utc,
      )
    return _schedule_joke_to_next_available_daily(
      joke_id=joke_id,
      joke=joke,
      now_utc=now_utc,
    )

  raise ValueError(f'Unsupported target state: {target_state.value}')


def _get_reachable_target_states(
  joke: models.PunnyJoke,
  *,
  now_utc: datetime.datetime,
) -> set[models.JokeState]:
  state = joke.state
  if state in _ADMIN_MUTABLE_STATES:
    return set(_SELECTABLE_TARGET_STATES) - {state}
  if state == models.JokeState.PUBLISHED:
    return {
      models.JokeState.UNREVIEWED,
      models.JokeState.APPROVED,
      models.JokeState.REJECTED,
      models.JokeState.DAILY,
    }
  if state == models.JokeState.DAILY:
    if not _is_future_daily(joke, now_utc=now_utc):
      return set()
    return {
      models.JokeState.UNREVIEWED,
      models.JokeState.APPROVED,
      models.JokeState.REJECTED,
      models.JokeState.PUBLISHED,
    }
  return set()


def _normalize_to_admin_state(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  now_utc: datetime.datetime,
) -> models.PunnyJoke:
  if joke.state in _ADMIN_MUTABLE_STATES:
    return joke
  if joke.state == models.JokeState.PUBLISHED:
    return _reset_joke_to_approved(
      joke_id=joke_id,
      joke=joke,
      expected_state=models.JokeState.PUBLISHED,
    )
  if joke.state == models.JokeState.DAILY:
    return _remove_joke_from_daily_schedule(
      joke_id=joke_id,
      joke=joke,
      now_utc=now_utc,
    )
  raise ValueError(
    f'Cannot transition joke "{joke_id}" from {joke.state.value}')


def _admin_rating_for_state(
  state: models.JokeState, ) -> models.JokeAdminRating:
  if state == models.JokeState.APPROVED:
    return models.JokeAdminRating.APPROVED
  if state == models.JokeState.REJECTED:
    return models.JokeAdminRating.REJECTED
  if state == models.JokeState.UNREVIEWED:
    return models.JokeAdminRating.UNREVIEWED
  raise ValueError(f'Unsupported admin rating state: {state.value}')


def _set_admin_rating_and_state(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  rating: models.JokeAdminRating,
) -> models.PunnyJoke:
  if joke.state not in _ADMIN_MUTABLE_STATES:
    raise ValueError(
      f'Admin rating cannot be changed when state is {joke.state.value}')

  mapped_state = models.JokeState(rating.value)
  _ = firestore.db().collection('jokes').document(joke_id).update({
    'admin_rating':
    rating.value,
    'state':
    mapped_state.value,
  })
  joke.admin_rating = rating
  joke.state = mapped_state
  return joke


def _publish_joke_immediately(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  now_utc: datetime.datetime,
) -> models.PunnyJoke:
  la_now = _normalize_utc(now_utc).astimezone(_LA_TIMEZONE)
  public_timestamp = datetime.datetime(
    la_now.year,
    la_now.month,
    la_now.day,
    tzinfo=_LA_TIMEZONE,
  )
  _ = firestore.db().collection('jokes').document(joke_id).update({
    'state':
    models.JokeState.PUBLISHED.value,
    'public_timestamp':
    public_timestamp,
    'is_public':
    True,
  })
  joke.state = models.JokeState.PUBLISHED
  joke.public_timestamp = public_timestamp
  joke.is_public = True
  return joke


def _reset_joke_to_approved(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  expected_state: models.JokeState | None = None,
) -> models.PunnyJoke:
  if expected_state is not None and joke.state != expected_state:
    raise ValueError(
      f'Cannot reset joke "{joke_id}": current state is {joke.state.value}, '
      f'expected {expected_state.value}')
  _ = firestore.db().collection('jokes').document(joke_id).update({
    'state':
    models.JokeState.APPROVED.value,
    'public_timestamp':
    None,
    'is_public':
    False,
  })
  joke.state = models.JokeState.APPROVED
  joke.public_timestamp = None
  joke.is_public = False
  return joke


def _remove_joke_from_daily_schedule(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  now_utc: datetime.datetime,
) -> models.PunnyJoke:
  _assert_future_daily_mutable(joke, now_utc=now_utc)

  client = firestore.db()
  batches = _load_daily_schedule_batches(client)
  la_today = _normalize_utc(now_utc).astimezone(_LA_TIMEZONE).date()
  batches_to_write: dict[str, dict[str, dict[str, object]]] = {}

  for batch_id, batch in batches.items():
    parsed_batch = _parse_daily_batch_id(batch_id)
    if parsed_batch is None:
      continue
    year, month = parsed_batch
    next_batch = dict(batch)
    removed_any = False
    for day_key, day_data in list(batch.items()):
      if str(day_data.get('joke_id') or '').strip() != joke_id:
        continue
      scheduled_date = datetime.date(year, month, int(day_key))
      if scheduled_date <= la_today:
        raise ValueError('Past and current daily jokes cannot be changed')
      del next_batch[day_key]
      removed_any = True
    if removed_any:
      batches_to_write[batch_id] = next_batch

  write_batch = client.batch()
  for batch_id, batch_data in batches_to_write.items():
    write_batch.set(
      client.collection(_BATCHES_COLLECTION).document(batch_id),
      {'jokes': batch_data},
    )
  write_batch.update(
    client.collection('jokes').document(joke_id),
    {
      'state': models.JokeState.APPROVED.value,
      'public_timestamp': None,
      'is_public': False,
    },
  )
  write_batch.commit()  # pyright: ignore[reportUnusedCallResult]

  joke.state = models.JokeState.APPROVED
  joke.public_timestamp = None
  joke.is_public = False
  return joke


def _schedule_joke_to_next_available_daily(
  *,
  joke_id: str,
  joke: models.PunnyJoke,
  now_utc: datetime.datetime,
) -> models.PunnyJoke:
  if joke.state not in (models.JokeState.PUBLISHED, models.JokeState.DAILY):
    raise ValueError(
      f'Joke "{joke_id}" must be in PUBLISHED or DAILY state to schedule')

  client = firestore.db()
  batches = _load_daily_schedule_batches(client)
  target_date = _find_next_available_daily_date(batches, now_utc=now_utc)
  batch_id = _daily_batch_id(target_date.year, target_date.month)
  target_batch = dict(batches.get(batch_id) or {})
  day_key = f'{target_date.day:02d}'
  if target_batch.get(day_key):
    raise ValueError(
      f'Schedule "{_DAILY_SCHEDULE_ID}" already has a joke scheduled for '
      f'{target_date.isoformat()}')

  target_batch[day_key] = _serialize_daily_batch_joke(joke)
  public_timestamp = datetime.datetime(
    target_date.year,
    target_date.month,
    target_date.day,
    tzinfo=_LA_TIMEZONE,
  )

  write_batch = client.batch()
  write_batch.set(
    client.collection(_BATCHES_COLLECTION).document(batch_id),
    {'jokes': target_batch},
  )
  write_batch.update(
    client.collection('jokes').document(joke_id),
    {
      'state': models.JokeState.DAILY.value,
      'public_timestamp': public_timestamp,
      'is_public': False,
    },
  )
  write_batch.commit()  # pyright: ignore[reportUnusedCallResult]

  joke.state = models.JokeState.DAILY
  joke.public_timestamp = public_timestamp
  joke.is_public = False
  return joke


def _load_daily_schedule_batches(
    client: Any) -> dict[str, dict[str, dict[str, object]]]:
  batches: dict[str, dict[str, dict[str, object]]] = {}
  query: Any = (client.collection(_BATCHES_COLLECTION).order_by(
    FieldPath.document_id()).start_at([f'{_DAILY_SCHEDULE_ID}_']).end_at(
      [f'{_DAILY_SCHEDULE_ID}_\uf8ff']))
  for snapshot in query.stream():
    if not snapshot.exists:
      continue
    data_raw: object = snapshot.to_dict() or {}
    if not isinstance(data_raw, dict):
      continue
    data = cast(dict[str, object], data_raw)
    jokes_raw: object = data.get('jokes')
    if not isinstance(jokes_raw, dict):
      batches[snapshot.id] = {}
      continue
    jokes_map = cast(dict[object, object], jokes_raw)
    parsed_batch: dict[str, dict[str, object]] = {}
    for day_key, day_value in jokes_map.items():
      if not isinstance(day_value, dict):
        continue
      parsed_batch[str(day_key)] = cast(dict[str, object], day_value)
    batches[snapshot.id] = parsed_batch
  return batches


def _find_next_available_daily_date(
  batches: dict[str, dict[str, dict[str, object]]],
  *,
  now_utc: datetime.datetime,
) -> datetime.date:
  target_date = _normalize_utc(now_utc).astimezone(_LA_TIMEZONE).date()
  while True:
    batch = batches.get(_daily_batch_id(target_date.year, target_date.month),
                        {})
    if f'{target_date.day:02d}' not in batch:
      return target_date
    target_date += datetime.timedelta(days=1)


def _serialize_daily_batch_joke(joke: models.PunnyJoke) -> dict[str, object]:
  return {
    'joke_id': joke.key or '',
    'setup': joke.setup_text or '',
    'punchline': joke.punchline_text or '',
    'setup_image_url': joke.setup_image_url,
    'punchline_image_url': joke.punchline_image_url,
  }


def _daily_batch_id(year: int, month: int) -> str:
  return f'{_DAILY_SCHEDULE_ID}_{year}_{month:02d}'


def _parse_daily_batch_id(batch_id: str) -> tuple[int, int] | None:
  prefix = f'{_DAILY_SCHEDULE_ID}_'
  if not batch_id.startswith(prefix):
    return None
  suffix = batch_id.removeprefix(prefix)
  parts = suffix.split('_')
  if len(parts) != 2:
    return None
  try:
    return int(parts[0]), int(parts[1])
  except ValueError:
    return None


def _is_future_daily(
  joke: models.PunnyJoke,
  *,
  now_utc: datetime.datetime,
) -> bool:
  if joke.state != models.JokeState.DAILY:
    return False
  public_timestamp = joke.public_timestamp
  if not isinstance(public_timestamp, datetime.datetime):
    return False
  return _normalize_utc(public_timestamp) > _normalize_utc(now_utc)


def _assert_future_daily_mutable(
  joke: models.PunnyJoke,
  *,
  now_utc: datetime.datetime,
) -> None:
  if not _is_future_daily(joke, now_utc=now_utc):
    raise ValueError('Past and current daily jokes cannot be changed')


def _normalize_utc(value: datetime.datetime) -> datetime.datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=datetime.timezone.utc)
  return value.astimezone(datetime.timezone.utc)


def _current_time_utc() -> datetime.datetime:
  return datetime.datetime.now(datetime.timezone.utc)


def sync_joke_to_search_collection(
  joke: models.PunnyJoke,
  new_embedding: Vector | None,
) -> None:
  """Syncs joke data to the joke_search collection document."""
  if not joke.key:
    return

  joke_id = joke.key
  search_doc_ref = firestore.db().collection("joke_search").document(joke_id)
  search_doc = search_doc_ref.get()
  search_data = search_doc.to_dict() or {} if search_doc.exists else {}

  update_payload: dict[str, object] = {}

  # 1. Sync embedding
  if new_embedding:
    update_payload["text_embedding"] = new_embedding

  # 2. Sync state
  if search_data.get("state") != joke.state.value:
    update_payload["state"] = joke.state.value

  # 3. Sync is_public
  if search_data.get("is_public") != joke.is_public:
    update_payload["is_public"] = joke.is_public

  # 4. Sync public_timestamp
  if search_data.get("public_timestamp") != joke.public_timestamp:
    update_payload["public_timestamp"] = joke.public_timestamp

  # 5. Sync num_saved_users_fraction
  if search_data.get(
      "num_saved_users_fraction") != joke.num_saved_users_fraction:
    update_payload["num_saved_users_fraction"] = joke.num_saved_users_fraction

  # 6. Sync num_shared_users_fraction
  if search_data.get(
      "num_shared_users_fraction") != joke.num_shared_users_fraction:
    update_payload[
      "num_shared_users_fraction"] = joke.num_shared_users_fraction

  # 7. Sync popularity_score
  if search_data.get("popularity_score") != joke.popularity_score:
    update_payload["popularity_score"] = joke.popularity_score

  # 8. Sync book_id (explicitly write nulls when missing)
  if "book_id" not in search_data or search_data.get(
      "book_id") != joke.book_id:
    update_payload["book_id"] = joke.book_id

  if update_payload:
    logger.info(
      f"Syncing joke to joke_search collection: {joke_id} with payload keys {update_payload.keys()}"
    )
    _ = search_doc_ref.set(update_payload, merge=True)


def to_response_joke(joke: models.PunnyJoke) -> dict[str, object]:
  """Convert a PunnyJoke to a dictionary suitable for API responses."""
  joke_dict = joke.to_dict(include_key=True)

  # Convert datetime objects to strings (e.g. DatetimeWithNanoseconds from Firestore is not serializable)
  for key, value in joke_dict.items():
    if isinstance(value, datetime.datetime):
      joke_dict[key] = value.isoformat()

  return joke_dict


def transition_joke_to_state(
  *,
  joke_id: str,
  target_state: models.JokeState | str,
  now_utc: datetime.datetime | None = None,
) -> models.PunnyJoke:
  """Transition a joke to a reachable admin state target."""
  resolved_joke_id = joke_id.strip()
  if not resolved_joke_id:
    raise ValueError("joke_id is required")

  resolved_target_state = _parse_target_state(target_state)
  if resolved_target_state not in _SELECTABLE_TARGET_STATES:
    raise ValueError(f"Unsupported new_state: {resolved_target_state.value}")

  joke = firestore.get_punny_joke(resolved_joke_id)
  if not joke:
    raise JokeNotFoundError(f"Joke not found: {resolved_joke_id}")

  resolved_now_utc = _current_time_utc() if now_utc is None else now_utc
  return _transition_loaded_joke_to_state(
    joke_id=resolved_joke_id,
    joke=joke,
    target_state=resolved_target_state,
    now_utc=resolved_now_utc,
  )


def generate_joke_metadata(joke: models.PunnyJoke) -> models.PunnyJoke:
  """Generate seasonal info and tags for a joke."""
  if not joke.setup_text or not joke.punchline_text:
    # Skip metadata generation if text is incomplete (e.g. drafts)
    return joke

  seasonal, tags, metadata = joke_operation_prompts.generate_joke_metadata(
    setup_text=joke.setup_text,
    punchline_text=joke.punchline_text,
  )

  joke.seasonal = seasonal
  joke.tags = tags
  joke.generation_metadata.add_generation(metadata)
  return joke
