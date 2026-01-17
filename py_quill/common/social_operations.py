"""Social post generation operations."""

from __future__ import annotations

import datetime

from common import image_operations, models
from functions.prompts import social_post_prompts
from services import cloud_storage, firestore

MAX_SOCIAL_POST_JOKES = 5
PUBLIC_JOKE_BASE_URL = "https://snickerdoodlejokes.com/jokes"


class SocialPostRequestError(Exception):
  """Request validation error with an HTTP status code."""

  def __init__(self, message: str, status: int = 400):
    super().__init__(message)
    self.status = status


def apply_platform_text_updates(
  post: models.JokeSocialPost,
  *,
  pinterest_title: str | None = None,
  pinterest_description: str | None = None,
  pinterest_alt_text: str | None = None,
  instagram_caption: str | None = None,
  instagram_alt_text: str | None = None,
  facebook_message: str | None = None,
) -> bool:
  """Apply manual text updates to the social post."""
  updated = False
  if any((pinterest_title, pinterest_description, pinterest_alt_text)):
    if not post.is_platform_posted(models.SocialPlatform.PINTEREST):
      if pinterest_title:
        post.pinterest_title = pinterest_title
        updated = True
      if pinterest_description:
        post.pinterest_description = pinterest_description
        updated = True
      if pinterest_alt_text:
        post.pinterest_alt_text = pinterest_alt_text
        updated = True

  if any((instagram_caption, instagram_alt_text)):
    if not post.is_platform_posted(models.SocialPlatform.INSTAGRAM):
      if instagram_caption:
        post.instagram_caption = instagram_caption
        updated = True
      if instagram_alt_text:
        post.instagram_alt_text = instagram_alt_text
        updated = True

  if facebook_message:
    if not post.is_platform_posted(models.SocialPlatform.FACEBOOK):
      post.facebook_message = facebook_message
      updated = True

  return updated


def mark_platform_posted(
  post: models.JokeSocialPost,
  *,
  platform: models.SocialPlatform,
  platform_post_id: str | None,
  post_time: datetime.datetime | None = None,
) -> models.JokeSocialPost:
  """Stamp the post id and post date for a platform."""
  if not isinstance(platform, models.SocialPlatform):
    raise SocialPostRequestError("platform must be a SocialPlatform")
  if post.is_platform_posted(platform):
    raise SocialPostRequestError(
      f"{platform.value.title()} post already marked as posted")
  if not isinstance(platform_post_id, str) or not platform_post_id.strip():
    raise SocialPostRequestError("platform_post_id is required")

  now = post_time or datetime.datetime.now(datetime.timezone.utc)
  prefix = platform.value
  setattr(post, f"{prefix}_post_id", platform_post_id.strip())
  setattr(post, f"{prefix}_post_time", now)
  return post


def initialize_social_post(
  *,
  post_id: str | None,
  joke_ids: list[str] | None,
  post_type: models.JokeSocialPostType | None,
  pinterest_title: str | None = None,
  pinterest_description: str | None = None,
  pinterest_alt_text: str | None = None,
  instagram_caption: str | None = None,
  instagram_alt_text: str | None = None,
  facebook_message: str | None = None,
) -> tuple[models.JokeSocialPost, bool]:
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
    link_url = _build_social_post_link_url(post_type, ordered_jokes)
    post = models.JokeSocialPost(
      type=post_type,
      jokes=ordered_jokes,
      link_url=link_url,
    )

  updated = apply_platform_text_updates(
    post,
    pinterest_title=pinterest_title,
    pinterest_description=pinterest_description,
    pinterest_alt_text=pinterest_alt_text,
    instagram_caption=instagram_caption,
    instagram_alt_text=instagram_alt_text,
    facebook_message=facebook_message,
  )

  return post, updated


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


def _build_social_post_link_url(
  post_type: models.JokeSocialPostType,
  jokes: list[models.PunnyJoke],
) -> str:
  if post_type in (
      models.JokeSocialPostType.JOKE_GRID,
      models.JokeSocialPostType.JOKE_GRID_TEASER,
  ):
    last_joke = jokes[-1]
    slug = last_joke.human_readable_setup_text_slug
    return f"{PUBLIC_JOKE_BASE_URL}/{slug}"
  raise SocialPostRequestError(f'Unsupported post type: {post_type}')


def generate_social_post_images(
  post: models.JokeSocialPost,
) -> tuple[models.JokeSocialPost, dict[models.SocialPlatform, bytes], bool]:
  """Generate image assets for each unposted platform."""
  image_bytes_by_platform: dict[models.SocialPlatform, bytes] = {}
  updated = False
  for platform in models.SocialPlatform:
    if post.is_platform_posted(platform):
      continue

    image_url, image_bytes = _create_social_post_image(post, platform)
    image_bytes_by_platform[platform] = image_bytes
    updated = True

    if platform == models.SocialPlatform.PINTEREST:
      post.pinterest_image_url = image_url
    elif platform == models.SocialPlatform.INSTAGRAM:
      post.instagram_image_url = image_url
    elif platform == models.SocialPlatform.FACEBOOK:
      post.facebook_image_url = image_url
    else:
      raise SocialPostRequestError(f"Unsupported platform: {platform}")

  return post, image_bytes_by_platform, updated


def generate_social_post_text(
  post: models.JokeSocialPost,
  *,
  image_bytes_by_platform: dict[models.SocialPlatform, bytes] | None = None,
) -> tuple[models.JokeSocialPost, bool]:
  """Generate text content for each unposted platform."""
  updated = False
  for platform in models.SocialPlatform:
    if post.is_platform_posted(platform):
      continue
    if platform == models.SocialPlatform.PINTEREST:
      pin_image_bytes = None
      if image_bytes_by_platform:
        pin_image_bytes = image_bytes_by_platform.get(
          models.SocialPlatform.PINTEREST)
      post = _generate_pinterest_post_text(post, pin_image_bytes)
      updated = True
  return post, updated


def _generate_pinterest_post_text(
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


def _create_social_post_image(
    post: models.JokeSocialPost,
    platform: models.SocialPlatform) -> tuple[str, bytes]:
  """Create Pinterest pin assets for a social post."""
  if platform == models.SocialPlatform.PINTEREST:
    post_image = image_operations.create_joke_grid_image_3x2(
      jokes=post.jokes,
      block_last_panel=post.type == models.JokeSocialPostType.JOKE_GRID_TEASER,
    )
  elif platform == models.SocialPlatform.INSTAGRAM or platform == models.SocialPlatform.FACEBOOK:
    post_image = image_operations.create_joke_grid_image_square(
      jokes=post.jokes,
      block_last_panel=post.type == models.JokeSocialPostType.JOKE_GRID_TEASER,
    )
  else:
    raise SocialPostRequestError(f"Unsupported platform: {platform}")

  uploaded_gcs_uri, image_bytes = cloud_storage.upload_image_to_gcs(
    post_image,
    'social_post',
    'png',
  )
  image_url = cloud_storage.get_public_cdn_url(uploaded_gcs_uri)
  return image_url, image_bytes
