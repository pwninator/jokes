"""Tests for social_operations."""

from __future__ import annotations

import datetime
from unittest.mock import Mock

import pytest
from common import models, social_operations
from PIL import Image


def test_create_social_post_image_pinterest_carousel_uses_giraffe(
  monkeypatch: pytest.MonkeyPatch, ):
  jokes = [
    models.PunnyJoke(
      key="j1",
      setup_text="Setup 1",
      punchline_text="Punchline 1",
      setup_image_url="setup-1",
      punchline_image_url="punch-1",
    ),
    models.PunnyJoke(
      key="j2",
      setup_text="Setup 2",
      punchline_text="Punchline 2",
      setup_image_url="setup-2",
      punchline_image_url="punch-2",
    ),
  ]
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_CAROUSEL,
    jokes=jokes,
    link_url="https://example.com/jokes/tag",
  )

  giraffe_image = Image.new('RGB', (1024, 4096), color='white')
  giraffe_mock = Mock(return_value=giraffe_image)
  monkeypatch.setattr(social_operations.image_operations,
                      "create_joke_giraffe_image", giraffe_mock)
  monkeypatch.setattr(
    social_operations.image_operations,
    "create_single_joke_images_4by5",
    Mock(side_effect=AssertionError("Unexpected 4x5 carousel call")),
  )

  upload_calls: list[tuple[Image.Image, str, str]] = []

  def _fake_upload(image, file_name_base, extension, **_kwargs):
    upload_calls.append((image, file_name_base, extension))
    return "gs://bucket/social_post.png", b"image-bytes"

  monkeypatch.setattr(social_operations.cloud_storage, "upload_image_to_gcs",
                      _fake_upload)
  monkeypatch.setattr(
    social_operations.cloud_storage,
    "get_public_cdn_url",
    lambda _uri: "https://cdn.example.com/social_post.png",
  )

  image_urls, image_bytes = social_operations._create_social_post_image(
    post,
    models.SocialPlatform.PINTEREST,
  )

  assert image_urls == ["https://cdn.example.com/social_post.png"]
  assert image_bytes == [b"image-bytes"]
  giraffe_mock.assert_called_once_with(jokes=jokes)
  assert upload_calls == [(giraffe_image, "social_post", "png")]


def test_generate_social_post_media_joke_video_sets_shared_video_uris(
  monkeypatch: pytest.MonkeyPatch, ):
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_REEL_VIDEO,
    jokes=[
      models.PunnyJoke(
        key="j1",
        setup_text="Setup 1",
        punchline_text="Punchline 1",
        setup_image_url="https://cdn.example.com/setup.png",
        punchline_image_url="https://cdn.example.com/punch.png",
      )
    ],
    link_url="https://snickerdoodlejokes.com/jokes/setup-1",
  )

  monkeypatch.setattr(
    social_operations.cloud_storage,
    "extract_gcs_uri_from_image_url",
    lambda image_url: f"gs://bucket/{image_url.rsplit('/', 1)[-1]}",
  )
  monkeypatch.setattr(
    social_operations.cloud_storage,
    "download_bytes_from_gcs",
    lambda gcs_uri: (f"bytes-{gcs_uri.rsplit('/', 1)[-1]}".encode("utf-8")),
  )
  monkeypatch.setattr(
    social_operations,
    "DEFAULT_SOCIAL_REEL_TELLER_CHARACTER_DEF_ID",
    "char_teller",
  )
  monkeypatch.setattr(
    social_operations,
    "DEFAULT_SOCIAL_REEL_LISTENER_CHARACTER_DEF_ID",
    "char_listener",
  )

  def _fake_generate_joke_video(*_args, **_kwargs):
    return Mock(
      video_gcs_uri="gs://bucket/social/joke_video.mp4",
      error=None,
      error_stage=None,
    )

  monkeypatch.setattr(
    social_operations.joke_operations,
    "generate_joke_video",
    _fake_generate_joke_video,
  )

  updated_post, image_bytes_by_platform, updated = (
    social_operations.generate_social_post_media(post))

  assert updated is True
  assert updated_post.instagram_video_gcs_uri == "gs://bucket/social/joke_video.mp4"
  assert updated_post.facebook_video_gcs_uri == "gs://bucket/social/joke_video.mp4"
  assert updated_post.pinterest_video_gcs_uri == "gs://bucket/social/joke_video.mp4"
  assert image_bytes_by_platform[models.SocialPlatform.PINTEREST] == [
    b"bytes-setup.png",
    b"bytes-punch.png",
  ]
  assert image_bytes_by_platform[models.SocialPlatform.INSTAGRAM] == [
    b"bytes-setup.png",
    b"bytes-punch.png",
  ]
  assert image_bytes_by_platform[models.SocialPlatform.FACEBOOK] == [
    b"bytes-setup.png",
    b"bytes-punch.png",
  ]


def test_publish_platform_instagram_video_uses_instagram_video_uri(
  monkeypatch: pytest.MonkeyPatch, ):
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_REEL_VIDEO,
    link_url="https://snickerdoodlejokes.com/jokes/video-joke",
    instagram_caption="Caption",
    instagram_video_gcs_uri="gs://bucket/social/ig-video.mp4",
  )

  captured = {}

  def _fake_publish_instagram_post(*, video=None, images=None, caption=""):
    captured["video_gcs_uri"] = video.gcs_uri if video else None
    captured["images"] = images
    captured["caption"] = caption
    return "ig-video-id"

  monkeypatch.setattr(
    social_operations.meta_service,
    "publish_instagram_post",
    _fake_publish_instagram_post,
  )

  now = datetime.datetime(2026, 2, 24, tzinfo=datetime.timezone.utc)
  published = social_operations.publish_platform(
    post,
    platform=models.SocialPlatform.INSTAGRAM,
    post_time=now,
  )

  assert captured["video_gcs_uri"] == "gs://bucket/social/ig-video.mp4"
  assert captured["images"] is None
  assert captured["caption"] == "Caption"
  assert published.instagram_post_id == "ig-video-id"
  assert published.instagram_post_time == now


def test_publish_platform_facebook_video_uses_facebook_video_uri(
  monkeypatch: pytest.MonkeyPatch, ):
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_REEL_VIDEO,
    link_url="https://snickerdoodlejokes.com/jokes/video-joke",
    facebook_message="Message",
    facebook_video_gcs_uri="gs://bucket/social/fb-video.mp4",
  )

  captured = {}

  def _fake_publish_facebook_post(*, video=None, images=None, message=""):
    captured["video_gcs_uri"] = video.gcs_uri if video else None
    captured["images"] = images
    captured["message"] = message
    return "fb-video-id"

  monkeypatch.setattr(
    social_operations.meta_service,
    "publish_facebook_post",
    _fake_publish_facebook_post,
  )

  now = datetime.datetime(2026, 2, 24, tzinfo=datetime.timezone.utc)
  published = social_operations.publish_platform(
    post,
    platform=models.SocialPlatform.FACEBOOK,
    post_time=now,
  )

  assert captured["video_gcs_uri"] == "gs://bucket/social/fb-video.mp4"
  assert captured["images"] is None
  assert captured["message"] == "Message"
  assert published.facebook_post_id == "fb-video-id"
  assert published.facebook_post_time == now


def test_initialize_social_post_joke_video_requires_single_joke(
  monkeypatch: pytest.MonkeyPatch, ):
  jokes = [
    models.PunnyJoke(key="j1", setup_text="S1", punchline_text="P1"),
    models.PunnyJoke(key="j2", setup_text="S2", punchline_text="P2"),
  ]
  monkeypatch.setattr(social_operations.firestore, "get_punny_jokes",
                      lambda _ids: jokes)

  with pytest.raises(social_operations.SocialPostRequestError,
                     match="exactly one joke"):
    _ = social_operations.initialize_social_post(
      post_id=None,
      joke_ids=["j1", "j2"],
      post_type=models.JokeSocialPostType.JOKE_REEL_VIDEO,
    )
