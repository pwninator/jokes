"""Meta Graph API helpers for publishing social posts."""

from __future__ import annotations

import json
import time
from typing import Any, cast

import requests
from common import config, models
from firebase_functions import logger

GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
REEL_STATUS_POLL_INTERVAL_SEC = 3
REEL_STATUS_MAX_ATTEMPTS = 60


class MetaAPIError(Exception):
  """Raised when the Meta Graph API returns an error."""

  status_code: int | None
  response_data: dict[str, Any] | None

  def __init__(
    self,
    message: str,
    *,
    status_code: int | None = None,
    response_data: dict[str, Any] | None = None,
  ):
    super().__init__(message)
    self.status_code = status_code
    self.response_data = response_data


def _make_graph_request(
  method: str,
  endpoint: str,
  *,
  params: dict[str, Any] | None = None,
  access_token: str | None = None,
) -> dict[str, Any]:
  """Make a request to the Meta Graph API and return JSON payload."""
  payload = dict(params or {})
  payload.setdefault("access_token", config.get_meta_long_lived_token())
  if access_token:
    payload["access_token"] = access_token
  url = f"{GRAPH_API_BASE_URL}{endpoint}"

  logger.info(
    "Meta Graph API request",
    extra={"json_fields": {
      "method": method,
      "url": url
    }},
  )

  if method.upper() == "GET":
    response = requests.request(method, url, params=payload, timeout=30)
  else:
    response = requests.request(method, url, data=payload, timeout=30)

  try:
    data = response.json()
  except ValueError:
    data = {"error": {"message": response.text}}

  if response.status_code < 200 or response.status_code >= 300:
    logger.error(
      "Meta Graph API error",
      extra={
        "json_fields": {
          "status_code": response.status_code,
          "response": data,
        }
      },
    )
    raise MetaAPIError(
      f"Meta Graph API error {response.status_code}: {data}",
      status_code=response.status_code,
      response_data=data,
    )

  return data


def _extract_image_urls(images: list[models.Image]) -> list[str]:
  """Return non-empty image URLs or raise if any are missing."""
  if not images:
    raise ValueError("images must not be empty")

  urls: list[str] = []
  for image in images:
    url = (image.url or "").strip()
    if not url:
      raise ValueError("All images must include a public url")
    urls.append(url)
  return urls


def _validate_media_selection(
  *,
  images: list[models.Image] | None,
  video: models.Video | None,
) -> None:
  """Validate that exactly one media type is supplied."""
  if video and images:
    raise ValueError("images and video are mutually exclusive")
  if not video and not images:
    raise ValueError("Either images or video must be provided")


def _get_facebook_page_access_token(*, page_id: str) -> str:
  """Return a Page access token for the configured Meta user token.

  Facebook Pages publishing endpoints require acting as the Page (not the user)
  for some operations (notably uploading unpublished photos for multi-photo
  posts).
  """
  page_id = (page_id or "").strip()
  if not page_id:
    raise ValueError("page_id is required")

  resp = _make_graph_request(
    "GET",
    f"/{page_id}",
    params={"fields": "access_token"},
    access_token=config.get_meta_long_lived_token(),
  )
  token = (resp.get("access_token") or "").strip()
  if not token:
    raise MetaAPIError("Failed to retrieve Facebook Page access token")
  return token


def publish_instagram_post(
  images: list[models.Image] | None = None,
  video: models.Video | None = None,
  caption: str = "",
) -> str:
  """Publish images or a reel to Instagram.

  Args:
    images: Optional list of Image objects with public URLs.
    video: Optional Video object with a `gcs_uri`. Published as a Reel.
    caption: Caption text for the post.

  Returns:
    Published media ID.
  """
  _validate_media_selection(images=images, video=video)
  if video:
    return _publish_instagram_reel(video=video, caption=caption)

  assert images is not None
  urls = _extract_image_urls(images)
  ig_user_id = config.INSTAGRAM_USER_ID

  if len(urls) == 1:
    image_alt_text = (images[0].alt_text or "").strip()
    container = _make_graph_request(
      "POST",
      f"/{ig_user_id}/media",
      params={
        "image_url": urls[0],
        "caption": caption,
        **({
          "alt_text": image_alt_text
        } if image_alt_text else {}),
      },
    )
    creation_id = container.get("id")
  else:
    item_ids: list[str] = []
    for image, url in zip(images, urls):
      item_alt_text = (image.alt_text or "").strip()
      container = _make_graph_request(
        "POST",
        f"/{ig_user_id}/media",
        params={
          "image_url": url,
          "is_carousel_item": "true",
          **({
            "alt_text": item_alt_text
          } if item_alt_text else {}),
        },
      )
      item_id = container.get("id")
      if not item_id:
        raise MetaAPIError("Missing carousel item container id")
      item_ids.append(item_id)

    carousel = _make_graph_request(
      "POST",
      f"/{ig_user_id}/media",
      params={
        "media_type": "CAROUSEL",
        "caption": caption,
        "children": ",".join(item_ids),
      },
    )
    creation_id = carousel.get("id")

  if not creation_id:
    raise MetaAPIError("Missing Instagram creation id")

  publish_resp = _make_graph_request(
    "POST",
    f"/{ig_user_id}/media_publish",
    params={"creation_id": creation_id},
  )
  published_id = publish_resp.get("id")
  if not published_id:
    raise MetaAPIError("Missing Instagram published media id")
  return published_id


def _publish_instagram_reel(*, video: models.Video, caption: str) -> str:
  """Publish a single Reel to Instagram and return the media id."""
  ig_user_id = config.INSTAGRAM_USER_ID
  video_url = video.url
  if not video_url:
    raise MetaAPIError("Video URL is required")

  container = _make_graph_request(
    "POST",
    f"/{ig_user_id}/media",
    params={
      "media_type": "REELS",
      "video_url": video_url,
      **({
        "caption": caption
      } if caption else {}),
    },
  )
  creation_id = container.get("id")
  if not creation_id:
    raise MetaAPIError("Missing Instagram Reel creation id")

  _wait_for_reel_media_ready(creation_id=creation_id)

  publish_resp = _make_graph_request(
    "POST",
    f"/{ig_user_id}/media_publish",
    params={"creation_id": creation_id},
  )
  published_id = publish_resp.get("id")
  if not published_id:
    raise MetaAPIError("Missing Instagram Reel media id")
  return published_id


def _parse_instagram_reel_status(response: dict[str, Any]) -> str:
  """Extract and normalize Instagram reel status from Graph API response."""
  status: Any = response.get("status_code")
  if status is None:
    return ""
  return str(cast(object, status)).strip().upper()


def _parse_facebook_reel_status(response: dict[str, Any]) -> str:
  """Extract and normalize Facebook reel status from Graph API response."""
  status_obj = response.get("status")
  if not isinstance(status_obj, dict):
    return ""

  typed_status_obj = cast(dict[str, Any], status_obj)
  status: Any = typed_status_obj.get("video_status")
  if status is None:
    return ""
  return str(cast(object, status)).strip().upper()


def _wait_for_reel_media_ready(
  *,
  creation_id: str | None = None,
  video_id: str | None = None,
  page_access_token: str | None = None,
) -> None:
  """Wait for Instagram or Facebook reel media to reach ready status.

  Args:
    creation_id: Instagram reel container id.
    video_id: Facebook reel video id.
    page_access_token: Required when polling Facebook video status.
  """
  if bool(creation_id) == bool(video_id):
    raise ValueError("Specify exactly one of creation_id or video_id")

  if creation_id:
    platform = "instagram"
    media_id = creation_id
    status_field = "status_code"
    request_params = {"fields": "status_code"}
    request_access_token = None
    ready_statuses = {"FINISHED", "PUBLISHED"}
    terminal_statuses = {"ERROR", "EXPIRED"}
    parse_status = _parse_instagram_reel_status
  else:
    if not page_access_token:
      raise ValueError("page_access_token is required for Facebook polling")
    platform = "facebook"
    media_id = str(video_id)
    status_field = "status.video_status"
    request_params = {"fields": "status"}
    request_access_token = page_access_token
    ready_statuses = {"READY", "PUBLISHED", "FINISHED"}
    terminal_statuses = {"ERROR", "FAILED", "BLOCKED", "REJECTED", "EXPIRED"}
    parse_status = _parse_facebook_reel_status

  last_status = ""
  for attempt in range(1, REEL_STATUS_MAX_ATTEMPTS + 1):
    status_resp = _make_graph_request(
      "GET",
      f"/{media_id}",
      params=request_params,
      access_token=request_access_token,
    )
    status = parse_status(status_resp)
    last_status = status

    if status in ready_statuses:
      return
    if status in terminal_statuses:
      raise MetaAPIError(
        f"{platform} reel media {media_id} entered terminal status: {status}")

    if attempt < REEL_STATUS_MAX_ATTEMPTS:
      logger.info(
        "Reel media not ready yet",
        extra={
          "json_fields": {
            "platform": platform,
            "attempt": attempt,
            "media_id": media_id,
            "status_field": status_field,
            "status": status,
          }
        },
      )
      time.sleep(REEL_STATUS_POLL_INTERVAL_SEC)

  raise MetaAPIError(
    f"{platform} reel media {media_id} not ready after "
    f"{REEL_STATUS_MAX_ATTEMPTS} polls; last status={last_status}")


def publish_facebook_post(
  images: list[models.Image] | None = None,
  message: str = "",
  video: models.Video | None = None,
) -> str:
  """Publish images or a Reel to Facebook.

  Args:
    images: Optional list of Image objects with public URLs.
    message: Message text for the post.
    video: Optional Video object with a `gcs_uri`. Published as a Reel.

  Returns:
    Published post ID.
  """
  _validate_media_selection(images=images, video=video)
  if video:
    return _publish_facebook_reel(video=video, message=message)

  assert images is not None
  urls = _extract_image_urls(images)
  page_id = config.FACEBOOK_PAGE_ID
  page_access_token = _get_facebook_page_access_token(page_id=page_id)

  if len(urls) == 1:
    image_alt_text = (images[0].alt_text or "").strip()
    params: dict[str, Any] = {
      "url": urls[0],
      "message": message,
      "published": "true",
    }
    if image_alt_text:
      params["alt_text_custom"] = image_alt_text
    resp = _make_graph_request(
      "POST",
      f"/{page_id}/photos",
      params=params,
      access_token=page_access_token,
    )
    post_id = resp.get("post_id") or resp.get("id")
  else:
    photo_ids: list[str] = []
    for image, url in zip(images, urls):
      params = {
        "url": url,
        "published": "false",
        "temporary": "false",
      }
      image_alt_text = (image.alt_text or "").strip()
      if image_alt_text:
        params["alt_text_custom"] = image_alt_text
      upload = _make_graph_request(
        "POST",
        f"/{page_id}/photos",
        params=params,
        access_token=page_access_token,
      )
      photo_id = upload.get("id")
      if not photo_id:
        raise MetaAPIError("Missing Facebook photo id")
      photo_ids.append(photo_id)

    attached_media = [{"media_fbid": photo_id} for photo_id in photo_ids]
    resp = _make_graph_request(
      "POST",
      f"/{page_id}/feed",
      params={
        "message": message,
        "attached_media": json.dumps(attached_media),
      },
      access_token=page_access_token,
    )
    post_id = resp.get("id")

  if not post_id:
    raise MetaAPIError("Missing Facebook post id")
  return post_id


def _upload_facebook_reel_hosted_video(
  *,
  upload_url: str,
  video_url: str,
  page_access_token: str,
) -> None:
  """Upload hosted video URL to a Facebook Reel upload session."""
  response = requests.request(
    "POST",
    upload_url,
    headers={
      "Authorization": f"OAuth {page_access_token}",
      "file_url": video_url,
    },
    timeout=30,
  )

  try:
    data = response.json()
  except ValueError:
    data = {"error": {"message": response.text}}

  if response.status_code < 200 or response.status_code >= 300:
    raise MetaAPIError(
      f"Facebook Reel upload error {response.status_code}: {data}")

  if data.get("success") is False:
    raise MetaAPIError(f"Facebook Reel upload failed: {data}")


def _publish_facebook_reel(*, video: models.Video, message: str) -> str:
  """Publish a single Reel to Facebook and return the video id."""
  page_id = config.FACEBOOK_PAGE_ID
  page_access_token = _get_facebook_page_access_token(page_id=page_id)
  video_url = video.url
  if not video_url:
    raise MetaAPIError("Video URL is required")

  start_resp = _make_graph_request(
    "POST",
    f"/{page_id}/video_reels",
    params={"upload_phase": "start"},
    access_token=page_access_token,
  )
  video_id = (start_resp.get("video_id") or "").strip()
  upload_url = (start_resp.get("upload_url") or "").strip()
  if not video_id:
    raise MetaAPIError("Missing Facebook Reel video_id")
  if not upload_url:
    raise MetaAPIError("Missing Facebook Reel upload_url")

  _upload_facebook_reel_hosted_video(
    upload_url=upload_url,
    video_url=video_url,
    page_access_token=page_access_token,
  )

  finish_params: dict[str, Any] = {
    "video_id": video_id,
    "upload_phase": "finish",
    "video_state": "PUBLISHED",
  }
  if message:
    finish_params["description"] = message
  finish_resp = _make_graph_request(
    "POST",
    f"/{page_id}/video_reels",
    params=finish_params,
    access_token=page_access_token,
  )
  if finish_resp.get("success") is False:
    raise MetaAPIError(f"Facebook Reel publish failed: {finish_resp}")

  _wait_for_reel_media_ready(
    video_id=video_id,
    page_access_token=page_access_token,
  )
  return video_id
