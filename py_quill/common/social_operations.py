"""Social post generation operations."""

from __future__ import annotations

from io import BytesIO

from common import image_operations, models
from functions.prompts import social_post_prompts
from services import cloud_storage, firestore

MAX_SOCIAL_POST_JOKES = 5


class SocialPostRequestError(Exception):
  """Request validation error with an HTTP status code."""

  def __init__(self, message: str, status: int = 400):
    super().__init__(message)
    self.status = status


def initialize_social_post(
  *,
  post_id: str | None,
  joke_ids: list[str] | None,
  post_type: models.JokeSocialPostType | None,
  pinterest_title: str | None = None,
  pinterest_description: str | None = None,
  pinterest_alt_text: str | None = None,
) -> models.JokeSocialPost:
  """Load or create a social post and apply manual overrides."""
  if post_id:
    post = firestore.get_joke_social_post(post_id)
    if not post:
      raise SocialPostRequestError(f'Social post not found: {post_id}',
                                   status=404)
  else:
    joke_id_list = _validate_joke_ids(joke_ids)
    post_type = _validate_post_type(post_type)
    ordered_jokes = _load_ordered_jokes(joke_id_list)
    post = models.JokeSocialPost(
      type=post_type,
      jokes=ordered_jokes,
    )

  if pinterest_title is not None:
    post.pinterest_title = pinterest_title
  if pinterest_description is not None:
    post.pinterest_description = pinterest_description
  if pinterest_alt_text is not None:
    post.pinterest_alt_text = pinterest_alt_text

  return post


def _validate_post_type(
  post_type: models.JokeSocialPostType | None, ) -> models.JokeSocialPostType:
  if not post_type:
    raise SocialPostRequestError('type is required')
  return post_type


def _validate_joke_ids(joke_ids: list[str] | None) -> list[str]:
  if not joke_ids:
    raise SocialPostRequestError('joke_ids must be a non-empty list')
  if len(joke_ids) > MAX_SOCIAL_POST_JOKES:
    raise SocialPostRequestError('joke_ids must have at most 5 items')
  return joke_ids


def _load_ordered_jokes(joke_ids: list[str]) -> list[models.PunnyJoke]:
  jokes = firestore.get_punny_jokes(joke_ids)
  jokes_by_id = {joke.key: joke for joke in jokes if joke.key}
  ordered_jokes = [jokes_by_id.get(joke_id) for joke_id in joke_ids]
  if any(joke is None for joke in ordered_jokes):
    missing = [
      jid for jid, joke in zip(joke_ids, ordered_jokes) if joke is None
    ]
    raise SocialPostRequestError(f'Jokes not found: {missing}')
  return ordered_jokes


def generate_pinterest_post_text(
  post: models.JokeSocialPost,
  pin_image_bytes: bytes | None = None,
) -> models.JokeSocialPost:
  """Generate Pinterest text fields based on the composed image."""
  if not pin_image_bytes:
    gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
      post.pinterest_image_url)
    pin_image_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)

  title, description, alt_text, _metadata = (
    social_post_prompts.generate_pinterest_post_text(
      pin_image_bytes,
      post_type=post.type,
    ))
  post.pinterest_title = title
  post.pinterest_description = description
  post.pinterest_alt_text = alt_text
  return post


def create_pinterest_pin_assets(
    post: models.JokeSocialPost) -> tuple[models.JokeSocialPost, bytes]:
  """Create Pinterest pin assets for a social post."""
  pin_image = image_operations.create_pinterest_pin_image(
    jokes=post.jokes,
    block_last_panel=post.type == models.JokeSocialPostType.JOKE_GRID_TEASER,
  )

  buffer = BytesIO()
  pin_image.save(buffer, format='PNG')
  image_bytes = buffer.getvalue()

  gcs_uri = cloud_storage.get_image_gcs_uri('social_pinterest', 'png')
  cloud_storage.upload_bytes_to_gcs(
    image_bytes,
    gcs_uri,
    'image/png',
  )
  pin_url = cloud_storage.get_public_cdn_url(gcs_uri)
  post.pinterest_image_url = pin_url
  return post, image_bytes
