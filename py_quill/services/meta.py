"""Meta Graph API helpers for publishing social posts."""

from __future__ import annotations

import json
from typing import Any

import requests
from common import config, models
from firebase_functions import logger

GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class MetaAPIError(Exception):
  """Raised when the Meta Graph API returns an error."""


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
    raise MetaAPIError(f"Meta Graph API error {response.status_code}: {data}")

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
  images: list[models.Image],
  caption: str,
  alt_text: str | None = None,
) -> str:
  """Publish a single-image or carousel post to Instagram.

  Args:
    images: List of Image objects with public URLs.
    caption: Caption text for the post.
    alt_text: Optional alt text for the first/only image.

  Returns:
    Published media ID.
  """
  urls = _extract_image_urls(images)
  ig_user_id = config.INSTAGRAM_USER_ID
  alt_text = (alt_text or "").strip() or None

  if len(urls) == 1:
    container = _make_graph_request(
      "POST",
      f"/{ig_user_id}/media",
      params={
        "image_url": urls[0],
        "caption": caption,
        **({
          "alt_text": alt_text
        } if alt_text else {}),
      },
    )
    creation_id = container.get("id")
  else:
    item_ids: list[str] = []
    for index, url in enumerate(urls):
      item_alt_text = alt_text if (alt_text and index == 0) else None
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


def publish_facebook_post(
  images: list[models.Image],
  message: str,
  alt_text: str | None = None,
) -> str:
  """Publish a single-image or multi-photo post to Facebook.

  Args:
    images: List of Image objects with public URLs.
    message: Message text for the post.
    alt_text: Optional alt text for the first/only image.

  Returns:
    Published post ID.
  """
  urls = _extract_image_urls(images)
  page_id = config.FACEBOOK_PAGE_ID
  alt_text = (alt_text or "").strip() or None
  page_access_token = _get_facebook_page_access_token(page_id=page_id)

  if len(urls) == 1:
    # Future improvement: support per-image alt text lists for multi-photo posts.
    params: dict[str, Any] = {
      "url": urls[0],
      "message": message,
      "published": "true",
    }
    if alt_text:
      params["alt_text_custom"] = alt_text
    resp = _make_graph_request(
      "POST",
      f"/{page_id}/photos",
      params=params,
      access_token=page_access_token,
    )
    post_id = resp.get("post_id") or resp.get("id")
  else:
    photo_ids: list[str] = []
    # Future improvement: support per-image alt text lists for multi-photo posts.
    for index, url in enumerate(urls):
      params = {
        "url": url,
        "published": "false",
        "temporary": "false",
      }
      if alt_text and index == 0:
        params["alt_text_custom"] = alt_text
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
