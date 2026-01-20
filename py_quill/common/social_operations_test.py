"""Tests for social_operations."""

from __future__ import annotations

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
