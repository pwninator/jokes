"""Social post generation operations."""

from __future__ import annotations

import datetime

from common import image_operations, joke_operations, models, utils
from functions.prompts import social_post_prompts
from services import cloud_storage, firestore
from services import meta as meta_service

MAX_SOCIAL_POST_JOKES = 5
PUBLIC_JOKE_BASE_URL = "https://snickerdoodlejokes.com/jokes"
NUM_RECENT_POSTS_TO_INCLUDE = 10
DEFAULT_SOCIAL_REEL_TELLER_CHARACTER_DEF_ID = "cat_orange_tabby"
DEFAULT_SOCIAL_REEL_LISTENER_CHARACTER_DEF_ID = "dog_beagle"


class SocialPostRequestError(Exception):
  """Request validation error with an HTTP status code."""

  status: int

  def __init__(self, message: str, status: int = 400):
    super().__init__(message)
    self.status = status


def delete_social_post(*, post_id: str) -> bool:
  """Delete a social post if it has not been posted anywhere."""
  post_id = (post_id or "").strip()
  if not post_id:
    raise SocialPostRequestError("post_id is required")

  post = firestore.get_joke_social_post(post_id)
  if not post:
    raise SocialPostRequestError(f"Social post not found: {post_id}",
                                 status=404)

  posted_anywhere = any(
    post.is_platform_posted(platform) for platform in models.SocialPlatform)
  if posted_anywhere:
    raise SocialPostRequestError(
      "Cannot delete a social post that has been posted on a platform")

  deleted = firestore.delete_joke_social_post(post_id)
  if not deleted:
    raise SocialPostRequestError(f"Social post not found: {post_id}",
                                 status=404)
  return True


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
    if post_type == models.JokeSocialPostType.JOKE_REEL_VIDEO and len(
        ordered_jokes) != 1:
      raise SocialPostRequestError("JOKE_REEL_VIDEO requires exactly one joke")
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


def publish_platform(
  post: models.JokeSocialPost,
  *,
  platform: models.SocialPlatform,
  post_time: datetime.datetime | None = None,
) -> models.JokeSocialPost:
  """Publish the social post to a platform and mark it posted.

  Notes:
    - Only supports Instagram + Facebook (Meta Graph API) today.
  """
  if post.is_platform_posted(platform):
    raise SocialPostRequestError(
      f"{platform.value.title()} post already marked as posted")

  post_time = post_time or datetime.datetime.now(datetime.timezone.utc)

  match platform:
    case models.SocialPlatform.INSTAGRAM:
      caption = (post.instagram_caption or "").strip()
      if not caption:
        raise SocialPostRequestError("Instagram caption is required")

      images, video = _validate_and_build_publish_media(
        image_urls=post.instagram_image_urls,
        alt_text=post.instagram_alt_text,
        video_gcs_uri=post.instagram_video_gcs_uri,
        post_type=post.type,
      )
      platform_post_id = meta_service.publish_instagram_post(
        images=images,
        video=video,
        caption=caption,
      )
    case models.SocialPlatform.FACEBOOK:
      message = (post.facebook_message or "").strip()
      if not message:
        raise SocialPostRequestError("Facebook message is required")

      images, video = _validate_and_build_publish_media(
        image_urls=post.facebook_image_urls or post.instagram_image_urls,
        alt_text=post.instagram_alt_text,
        video_gcs_uri=post.facebook_video_gcs_uri,
        post_type=post.type,
      )
      platform_post_id = meta_service.publish_facebook_post(
        images=images,
        video=video,
        message=message,
      )
    case _:
      raise SocialPostRequestError(f"Unsupported platform: {platform.value}")

  return mark_platform_posted(
    post,
    platform=platform,
    platform_post_id=platform_post_id,
    post_time=post_time,
  )


def _validate_and_build_publish_media(
  *,
  image_urls: list[str],
  alt_text: str | None,
  video_gcs_uri: str | None,
  post_type: models.JokeSocialPostType,
) -> tuple[list[models.Image] | None, models.Video | None]:
  """Build publish-ready image objects with the same optional alt text."""
  normalized_alt_text = (alt_text or "").strip() or None
  images = [
    models.Image(url=url, alt_text=normalized_alt_text) for url in image_urls
  ] if image_urls else None
  video = models.Video(gcs_uri=video_gcs_uri) if video_gcs_uri else None

  if post_type == models.JokeSocialPostType.JOKE_REEL_VIDEO:
    if not video:
      raise SocialPostRequestError(
        "Video is required for JOKE_REEL_VIDEO posts")
    if images:
      raise SocialPostRequestError(
        "Images are not allowed for JOKE_REEL_VIDEO posts")
  else:
    if not images:
      raise SocialPostRequestError(
        "Images are required for non-JOKE_REEL_VIDEO posts")
    if video:
      raise SocialPostRequestError(
        "Video is not allowed for non-JOKE_REEL_VIDEO posts")

  return images, video


def mark_platform_posted(
  post: models.JokeSocialPost,
  *,
  platform: models.SocialPlatform,
  platform_post_id: str | None,
  post_time: datetime.datetime | None = None,
) -> models.JokeSocialPost:
  """Stamp the post id and post date for a platform."""
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
  missing = [jid for jid in joke_ids if jokes_by_id.get(jid) is None]
  if missing:
    raise SocialPostRequestError(f'Jokes not found: {missing}')
  ordered_jokes = [jokes_by_id[joke_id] for joke_id in joke_ids]
  return ordered_jokes


def _build_social_post_link_url(
  post_type: models.JokeSocialPostType,
  jokes: list[models.PunnyJoke],
) -> str:

  if post_type in (models.JokeSocialPostType.JOKE_GRID_TEASER,
                   models.JokeSocialPostType.JOKE_REEL_VIDEO):
    last_joke = jokes[-1]
    slug = last_joke.human_readable_setup_text_slug
  else:
    tag = _select_joke_grid_tag(jokes)
    slug = utils.get_text_slug(tag, human_readable=True)

  return f"{PUBLIC_JOKE_BASE_URL}/{slug}"


def _select_joke_grid_tag(jokes: list[models.PunnyJoke]) -> str:
  """Pick the best tag for a JOKE_GRID link.

  Sort tags by:
  1) number of jokes containing the tag (descending)
  2) lowest position the tag appears in any joke's tag list (ascending)
  3) tie-break deterministically (tag string)
  """
  tag_to_joke_indexes: dict[str, set[int]] = {}
  tag_to_min_position: dict[str, int] = {}

  for joke_index, joke in enumerate(jokes):
    if not joke or not joke.tags:
      continue

    seen_in_joke: set[str] = set()
    for tag_position, raw_tag in enumerate(joke.tags):
      tag = (raw_tag or "").strip()
      if not tag:
        continue

      if tag not in seen_in_joke:
        tag_to_joke_indexes.setdefault(tag, set()).add(joke_index)
        seen_in_joke.add(tag)

      prev_pos = tag_to_min_position.get(tag)
      if prev_pos is None or tag_position < prev_pos:
        tag_to_min_position[tag] = tag_position

  # Preserve previous behavior (IndexError) if no tags exist.
  if not tag_to_joke_indexes:
    return jokes[0].tags[0]

  best_tag = sorted(
    tag_to_joke_indexes.keys(),
    key=lambda t:
    (-len(tag_to_joke_indexes[t]), tag_to_min_position.get(t, 1 << 30), t),
  )[0]
  return best_tag


def generate_social_post_media(
  post: models.JokeSocialPost,
) -> tuple[models.JokeSocialPost, dict[models.SocialPlatform, list[bytes]],
           bool]:
  """Generate image assets for each unposted platform.

  For single-image posts (JOKE_GRID, JOKE_GRID_TEASER): Instagram and Facebook
  share the same square image asset. For carousel posts (JOKE_CAROUSEL): each
  platform gets the same set of images.

  Args:
    post: The social post to generate media for.

  Returns:
    A tuple containing the updated post, a dictionary of image bytes by platform for text generation,
    and a boolean indicating if the post was updated.
  """

  if post.type == models.JokeSocialPostType.JOKE_REEL_VIDEO:
    return _generate_social_post_media_video(post)
  else:
    return _generate_social_post_media_images(post)


def _generate_social_post_media_video(
  post: models.JokeSocialPost,
) -> tuple[models.JokeSocialPost, dict[models.SocialPlatform, list[bytes]],
           bool]:
  """Generate video assets for each unposted platform."""
  image_bytes_by_platform: dict[models.SocialPlatform, list[bytes]] = {}
  prompt_image_bytes = _load_video_prompt_image_bytes(post)
  for platform in models.SocialPlatform:
    if not post.is_platform_posted(platform):
      image_bytes_by_platform[platform] = prompt_image_bytes
  updated = _ensure_video_uris_for_post(post)
  return post, image_bytes_by_platform, updated


def _generate_social_post_media_images(
  post: models.JokeSocialPost,
) -> tuple[models.JokeSocialPost, dict[models.SocialPlatform, list[bytes]],
           bool]:
  """Generate image assets for each unposted platform."""
  image_bytes_by_platform: dict[models.SocialPlatform, list[bytes]] = {}
  updated = False

  # Pinterest: always its own asset
  if not post.is_platform_posted(models.SocialPlatform.PINTEREST):
    image_urls, image_bytes_list = _create_social_post_image(
      post,
      models.SocialPlatform.PINTEREST,
    )
    image_bytes_by_platform[models.SocialPlatform.PINTEREST] = image_bytes_list
    post.pinterest_image_urls = image_urls
    updated = True

  # Instagram + Facebook: shared square asset for single-image posts, or
  # shared carousel for JOKE_CAROUSEL.
  shared_platforms = (models.SocialPlatform.INSTAGRAM,
                      models.SocialPlatform.FACEBOOK)
  unposted_shared_platforms = [
    platform for platform in shared_platforms
    if not post.is_platform_posted(platform)
  ]
  if unposted_shared_platforms:
    # Check if either platform already has images we can reuse
    existing_square_urls = post.instagram_image_urls or post.facebook_image_urls
    if existing_square_urls:
      for platform in unposted_shared_platforms:
        if platform == models.SocialPlatform.INSTAGRAM:
          post.instagram_image_urls = existing_square_urls
        elif platform == models.SocialPlatform.FACEBOOK:
          post.facebook_image_urls = existing_square_urls
      updated = True
    else:
      image_urls, image_bytes_list = _create_social_post_image(
        post,
        models.SocialPlatform.INSTAGRAM,
      )
      for platform in unposted_shared_platforms:
        image_bytes_by_platform[platform] = image_bytes_list
        if platform == models.SocialPlatform.INSTAGRAM:
          post.instagram_image_urls = image_urls
        elif platform == models.SocialPlatform.FACEBOOK:
          post.facebook_image_urls = image_urls
      updated = True

  return post, image_bytes_by_platform, updated


def generate_social_post_text(
  post: models.JokeSocialPost,
  *,
  image_bytes_by_platform: dict[models.SocialPlatform, list[bytes]]
  | None = None,
) -> tuple[models.JokeSocialPost, bool]:
  """Generate text content for each unposted platform."""
  updated = False
  video_prompt_image_bytes: list[bytes] | None = None
  for platform in models.SocialPlatform:
    if post.is_platform_posted(platform):
      continue
    platform_image_bytes = None
    if image_bytes_by_platform:
      platform_image_bytes = image_bytes_by_platform.get(platform)
    if (not platform_image_bytes
        and post.type == models.JokeSocialPostType.JOKE_REEL_VIDEO):
      if video_prompt_image_bytes is None:
        video_prompt_image_bytes = _load_video_prompt_image_bytes(post)
      platform_image_bytes = video_prompt_image_bytes

    recent_posts = firestore.get_joke_social_posts(
      post_type=post.type,
      limit=NUM_RECENT_POSTS_TO_INCLUDE,
    )

    match platform:
      case models.SocialPlatform.PINTEREST:
        if not platform_image_bytes and not post.pinterest_image_urls:
          continue
        post = _generate_pinterest_post_text(
          post,
          recent_posts,
          platform_image_bytes,
        )
        updated = True
      case models.SocialPlatform.INSTAGRAM:
        if not platform_image_bytes and not post.instagram_image_urls:
          continue
        post = _generate_instagram_post_text(
          post,
          recent_posts,
          platform_image_bytes,
        )
        updated = True
      case models.SocialPlatform.FACEBOOK:
        if not platform_image_bytes and not post.facebook_image_urls:
          continue
        post = _generate_facebook_post_text(
          post,
          recent_posts,
          platform_image_bytes,
        )
        updated = True

  return post, updated


def _generate_pinterest_post_text(
  post: models.JokeSocialPost,
  recent_posts: list[models.JokeSocialPost],
  pin_image_bytes: list[bytes] | None = None,
) -> models.JokeSocialPost:
  """Generate Pinterest text fields based on the composed images."""
  if not pin_image_bytes:
    if not post.pinterest_image_urls:
      return post
    pin_image_bytes = []
    for image_url in post.pinterest_image_urls:
      gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(image_url)
      pin_image_bytes.append(cloud_storage.download_bytes_from_gcs(gcs_uri))

  title, description, alt_text, _metadata = (
    social_post_prompts.generate_pinterest_post_text(
      pin_image_bytes,
      post_type=post.type,
      recent_posts=recent_posts,
    ))
  post.pinterest_title = title
  post.pinterest_description = description
  post.pinterest_alt_text = alt_text
  return post


def _generate_instagram_post_text(
  post: models.JokeSocialPost,
  recent_posts: list[models.JokeSocialPost],
  instagram_image_bytes: list[bytes] | None = None,
) -> models.JokeSocialPost:
  """Generate Instagram text fields based on the composed images."""
  if not instagram_image_bytes:
    if not post.instagram_image_urls:
      return post
    instagram_image_bytes = []
    for image_url in post.instagram_image_urls:
      gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(image_url)
      instagram_image_bytes.append(
        cloud_storage.download_bytes_from_gcs(gcs_uri))

  caption, alt_text, _metadata = (
    social_post_prompts.generate_instagram_post_text(
      instagram_image_bytes,
      post_type=post.type,
      recent_posts=recent_posts,
    ))
  post.instagram_caption = caption
  post.instagram_alt_text = alt_text
  return post


def _generate_facebook_post_text(
  post: models.JokeSocialPost,
  recent_posts: list[models.JokeSocialPost],
  facebook_image_bytes: list[bytes] | None = None,
) -> models.JokeSocialPost:
  """Generate Facebook text fields based on the composed images."""
  if not facebook_image_bytes:
    if not post.facebook_image_urls:
      return post
    facebook_image_bytes = []
    for image_url in post.facebook_image_urls:
      gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(image_url)
      facebook_image_bytes.append(
        cloud_storage.download_bytes_from_gcs(gcs_uri))

  message, _metadata = social_post_prompts.generate_facebook_post_text(
    facebook_image_bytes,
    post_type=post.type,
    recent_posts=recent_posts,
    link_url=post.link_url or "",
  )
  post.facebook_message = message
  return post


def _create_social_post_image(
    post: models.JokeSocialPost,
    platform: models.SocialPlatform) -> tuple[list[str], list[bytes]]:
  """Create social post image assets for a platform.

  Returns:
    Tuple of (image_urls, image_bytes_list). For single-image posts, lists
    contain one element. For carousel posts, lists contain multiple elements,
    except Pinterest which uses a single stacked image.
  """
  post_images = []
  if post.type == models.JokeSocialPostType.JOKE_CAROUSEL:
    if platform == models.SocialPlatform.PINTEREST:
      post_images = [
        image_operations.create_joke_giraffe_image(jokes=post.jokes, )
      ]
    elif platform in (models.SocialPlatform.INSTAGRAM,
                      models.SocialPlatform.FACEBOOK):
      post_images = image_operations.create_single_joke_images_4by5(
        jokes=post.jokes, )
  elif post.type in (models.JokeSocialPostType.JOKE_GRID,
                     models.JokeSocialPostType.JOKE_GRID_TEASER):
    if platform == models.SocialPlatform.PINTEREST:
      post_images = [
        image_operations.create_joke_grid_image_3x2(
          jokes=post.jokes,
          block_last_panel=post.type ==
          models.JokeSocialPostType.JOKE_GRID_TEASER,
        )
      ]
    elif platform in (models.SocialPlatform.INSTAGRAM,
                      models.SocialPlatform.FACEBOOK):
      post_images = [
        image_operations.create_joke_grid_image_4by5(
          jokes=post.jokes,
          block_last_panel=post.type ==
          models.JokeSocialPostType.JOKE_GRID_TEASER,
        )
      ]
  else:
    raise SocialPostRequestError(f"Unsupported post type: {post.type}")
  if not post_images:
    raise SocialPostRequestError(
      f"Unsupported platform: {platform} for post type: {post.type}")

  image_urls: list[str] = []
  image_bytes_list: list[bytes] = []
  for img in post_images:
    uploaded_gcs_uri, img_bytes = cloud_storage.upload_image_to_gcs(
      img,
      'social_post',
      'png',
    )
    image_urls.append(cloud_storage.get_public_cdn_url(uploaded_gcs_uri))
    image_bytes_list.append(img_bytes)
  return image_urls, image_bytes_list


def _load_video_prompt_image_bytes(post: models.JokeSocialPost) -> list[bytes]:
  """Load setup + punchline image bytes for a single-joke video post."""
  if len(post.jokes) != 1:
    raise SocialPostRequestError("JOKE_REEL_VIDEO requires exactly one joke")
  joke = post.jokes[0]
  if not joke.setup_image_url or not joke.punchline_image_url:
    raise SocialPostRequestError(
      "JOKE_REEL_VIDEO text generation requires setup and punchline images")
  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.setup_image_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.punchline_image_url)
  return [
    cloud_storage.download_bytes_from_gcs(setup_gcs_uri),
    cloud_storage.download_bytes_from_gcs(punchline_gcs_uri),
  ]


def _ensure_video_uris_for_post(post: models.JokeSocialPost) -> bool:
  """Ensure all platform video URI fields are set to the same value."""
  shared_video_gcs_uri = (post.instagram_video_gcs_uri
                          or post.facebook_video_gcs_uri
                          or post.pinterest_video_gcs_uri or "").strip()
  if not shared_video_gcs_uri:
    generated_video = _generate_social_post_video(post)
    shared_video_gcs_uri = (generated_video.gcs_uri or "").strip()
    if not shared_video_gcs_uri:
      raise SocialPostRequestError("Video generation did not return a GCS URI")

  updated = False
  if post.instagram_video_gcs_uri != shared_video_gcs_uri:
    post.instagram_video_gcs_uri = shared_video_gcs_uri
    updated = True
  if post.facebook_video_gcs_uri != shared_video_gcs_uri:
    post.facebook_video_gcs_uri = shared_video_gcs_uri
    updated = True
  if post.pinterest_video_gcs_uri != shared_video_gcs_uri:
    post.pinterest_video_gcs_uri = shared_video_gcs_uri
    updated = True
  return updated


def _generate_social_post_video(post: models.JokeSocialPost) -> models.Video:
  """Generate video media for a single-joke JOKE_REEL_VIDEO post."""
  if len(post.jokes) != 1:
    raise SocialPostRequestError("JOKE_REEL_VIDEO requires exactly one joke")
  joke = post.jokes[0]
  result = joke_operations.generate_joke_video(
    joke,
    teller_character_def_id=DEFAULT_SOCIAL_REEL_TELLER_CHARACTER_DEF_ID,
    listener_character_def_id=DEFAULT_SOCIAL_REEL_LISTENER_CHARACTER_DEF_ID,
    script_template=joke_operations.DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE,
    use_audio_cache=True,
  )
  if result.error and not result.video_gcs_uri:
    raise SocialPostRequestError(
      f"Video generation failed: {result.error} ({result.error_stage or 'unknown'})"
    )
  video_gcs_uri = (result.video_gcs_uri or "").strip()
  if not video_gcs_uri:
    raise SocialPostRequestError("Video generation did not return a GCS URI")
  return models.Video(gcs_uri=video_gcs_uri)
