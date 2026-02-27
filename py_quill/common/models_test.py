"""Tests for the models module."""
import datetime

import pytest

from common import models


def test_punnyjoke_default_state_unknown():
  """Test that the default state is UNKNOWN."""
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  assert joke.state == models.JokeState.UNKNOWN


def test_punnyjoke_from_firestore_maps_state_string_to_enum():
  """Test that the from_firestore_dict method maps the state string to the JokeState enum."""
  data = {
    "setup_text": "s",
    "punchline_text": "p",
    "state": "DRAFT",
    "setup_scene_idea": "Setup concept",
    "punchline_scene_idea": "Punchline concept",
  }
  joke = models.PunnyJoke.from_firestore_dict(data, key="abc")
  assert joke.state == models.JokeState.DRAFT
  assert joke.setup_scene_idea == "Setup concept"
  assert joke.punchline_scene_idea == "Punchline concept"


def test_punnyjoke_from_firestore_missing_state_defaults_unknown():
  """Test that the from_firestore_dict method defaults to UNKNOWN state if the state is missing."""
  data = {
    "setup_text": "s",
    "punchline_text": "p",
  }
  joke = models.PunnyJoke.from_firestore_dict(data, key="abc")
  assert joke.state == models.JokeState.UNKNOWN


def test_punnyjoke_to_dict_serializes_state_and_metadata_and_key_optional():
  """Test that to_dict serializes state, metadata, and handles key inclusion."""
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  joke.state = models.JokeState.DRAFT
  joke.key = "abc123"
  joke.setup_scene_idea = "Setup idea"
  joke.punchline_scene_idea = "Punchline idea"

  md = models.GenerationMetadata()
  md.add_generation(
    models.SingleGenerationMetadata(label="x", model_name="m", cost=1.0))
  joke.generation_metadata = md

  d1 = joke.to_dict(include_key=False)
  assert d1["state"] == "DRAFT"
  assert "key" not in d1
  assert d1["setup_scene_idea"] == "Setup idea"
  assert d1["punchline_scene_idea"] == "Punchline idea"
  assert isinstance(d1["generation_metadata"], dict)
  assert "generations" in d1["generation_metadata"]

  d2 = joke.to_dict(include_key=True)
  assert d2["key"] == "abc123"


def test_punnyjoke_public_timestamp_in_to_dict():
  """`public_timestamp` should be passed through as datetime in to_dict."""
  ts = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
  joke = models.PunnyJoke(setup_text="s",
                          punchline_text="p",
                          public_timestamp=ts)

  d = joke.to_dict()
  assert "public_timestamp" in d
  assert isinstance(d["public_timestamp"], datetime.datetime)
  assert d["public_timestamp"] == ts


def test_punnyjoke_from_firestore_dict_public_timestamp_passthrough():
  """from_firestore_dict should accept datetime for public_timestamp."""
  ts = datetime.datetime(2024, 2, 3, 4, 5, 6, tzinfo=datetime.timezone.utc)
  src = {
    "setup_text": "s",
    "punchline_text": "p",
    "public_timestamp": ts,
  }
  joke = models.PunnyJoke.from_firestore_dict(src, key="k1")
  assert joke.public_timestamp == ts


def test_set_setup_image_updates_text_by_default():
  """Test that set_setup_image updates text fields by default."""
  joke = models.PunnyJoke(setup_text="s", punchline_text="p")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="orig",
                       final_prompt="final")
  joke.set_setup_image(image)
  assert joke.setup_image_url == "http://example.com/img.png"
  assert joke.setup_image_description == "orig"
  assert joke.setup_image_prompt == "final"


def test_set_setup_image_skips_text_update_when_false():
  """Test that set_setup_image skips updating text fields when update_text is False."""
  joke = models.PunnyJoke(setup_text="s",
                          punchline_text="p",
                          setup_image_description="before",
                          setup_image_prompt="before")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="after",
                       final_prompt="after")
  joke.set_setup_image(image, update_text=False)
  assert joke.setup_image_url == "http://example.com/img.png"
  assert joke.setup_image_description == "before"
  assert joke.setup_image_prompt == "before"


def test_set_punchline_image_updates_text_by_default():
  """Test that set_punchline_image updates text fields by default."""
  joke = models.PunnyJoke(setup_text="s", punchline_text="p")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="orig",
                       final_prompt="final")
  joke.set_punchline_image(image)
  assert joke.punchline_image_url == "http://example.com/img.png"
  assert joke.punchline_image_description == "orig"
  assert joke.punchline_image_prompt == "final"


def test_set_punchline_image_skips_text_update_when_false():
  """Test that set_punchline_image skips updating text fields when update_text is False."""
  joke = models.PunnyJoke(setup_text="s",
                          punchline_text="p",
                          punchline_image_description="before",
                          punchline_image_prompt="before")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="after",
                       final_prompt="after")
  joke.set_punchline_image(image, update_text=False)
  assert joke.punchline_image_url == "http://example.com/img.png"
  assert joke.punchline_image_description == "before"
  assert joke.punchline_image_prompt == "before"


def test_image_as_dict_includes_alt_text():
  image = models.Image(
    url="http://example.com/img.png",
    alt_text="An image alt text",
  )

  payload = image.as_dict

  assert payload["alt_text"] == "An image alt text"


def test_image_from_dict_reads_alt_text():
  image = models.Image.from_dict({
    "url": "http://example.com/img.png",
    "alt_text": "An image alt text",
  })

  assert image.url == "http://example.com/img.png"
  assert image.alt_text == "An image alt text"


def test_video_as_dict_includes_gcs_uri():
  video = models.Video(gcs_uri="gs://bucket/video.mp4")

  payload = video.as_dict

  assert payload["gcs_uri"] == "gs://bucket/video.mp4"


def test_video_from_dict_reads_gcs_uri():
  video = models.Video.from_dict({"gcs_uri": "gs://bucket/video.mp4"})

  assert video.gcs_uri == "gs://bucket/video.mp4"


def test_video_url_maps_gcs_uri_to_public_cdn_url(monkeypatch):
  monkeypatch.setattr(
    "services.cloud_storage.get_public_cdn_url",
    lambda gcs_uri:
    f"https://cdn.example.com/{gcs_uri.removeprefix('gs://bucket/')}",
  )
  video = models.Video(gcs_uri="gs://bucket/video.mp4")

  assert video.url == "https://cdn.example.com/video.mp4"


def test_video_url_none_without_gcs_uri():
  video = models.Video(gcs_uri=None)

  assert video.url is None


def test_get_minimal_joke_data_returns_correct_fields():
  """Test that get_minimal_joke_data returns a dictionary with the correct fields."""
  joke = models.PunnyJoke(
    key="joke123",
    setup_text="Why did the scarecrow win an award?",
    punchline_text="Because he was outstanding in his field.",
    setup_image_url="http://example.com/setup.png",
    punchline_image_url="http://example.com/punchline.png",
    pun_theme="awards",
    num_viewed_users=100,
  )
  minimal_data = joke.get_minimal_joke_data()
  expected_keys = {
    "key",
    "setup_text",
    "punchline_text",
    "setup_image_url",
    "punchline_image_url",
  }
  assert set(minimal_data.keys()) == expected_keys
  assert minimal_data["key"] == "joke123"
  assert minimal_data["setup_text"] == "Why did the scarecrow win an award?"
  assert minimal_data[
    "punchline_text"] == "Because he was outstanding in his field."
  assert minimal_data["setup_image_url"] == "http://example.com/setup.png"
  assert minimal_data[
    "punchline_image_url"] == "http://example.com/punchline.png"


def test_get_minimal_joke_data_with_none_values():
  """Test that get_minimal_joke_data handles None values correctly."""
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  # key, setup_image_url, and punchline_image_url are None by default
  minimal_data = joke.get_minimal_joke_data()
  expected_keys = {
    "key",
    "setup_text",
    "punchline_text",
    "setup_image_url",
    "punchline_image_url",
  }
  assert set(minimal_data.keys()) == expected_keys
  assert minimal_data["key"] is None
  assert minimal_data["setup_text"] == "setup"
  assert minimal_data["punchline_text"] == "punchline"
  assert minimal_data["setup_image_url"] is None
  assert minimal_data["punchline_image_url"] is None


def test_get_minimal_joke_data_with_partial_image_urls():
  """Test that get_minimal_joke_data handles partial image URLs."""
  joke = models.PunnyJoke(
    key="joke456",
    setup_text="Why did the chicken cross the road?",
    punchline_text="To get to the other side.",
    setup_image_url="http://example.com/setup.png",
    # punchline_image_url is None
  )
  minimal_data = joke.get_minimal_joke_data()
  assert minimal_data["key"] == "joke456"
  assert minimal_data["setup_text"] == "Why did the chicken cross the road?"
  assert minimal_data["punchline_text"] == "To get to the other side."
  assert minimal_data["setup_image_url"] == "http://example.com/setup.png"
  assert minimal_data["punchline_image_url"] is None


def test_joke_social_post_to_dict_serializes_type_and_keeps_dates():
  """JokeSocialPost should serialize enums and pass through post dates."""
  ts = datetime.datetime(2024, 3, 4, 5, 6, 7, tzinfo=datetime.timezone.utc)
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/grid",
    pinterest_title="Grid post",
    pinterest_description="A grid of jokes",
    pinterest_post_time=ts,
  )
  post.key = "post1"

  data = post.to_dict()
  assert data["type"] == "JOKE_GRID"
  assert "key" not in data
  assert data["pinterest_post_time"] == ts
  assert data["link_url"] == "https://snickerdoodlejokes.com/jokes/grid"


def test_joke_social_post_from_firestore_requires_type():
  """JokeSocialPost requires a type field."""
  with pytest.raises(ValueError):
    models.JokeSocialPost.from_firestore_dict(
      {
        "pinterest_title": "Title",
        "link_url": "https://example.com"
      },
      key="post1",
    )


def test_joke_social_post_from_firestore_requires_link_url():
  """JokeSocialPost requires a link_url field."""
  with pytest.raises(ValueError):
    models.JokeSocialPost.from_firestore_dict(
      {
        "type": "JOKE_GRID",
        "pinterest_title": "Title"
      },
      key="post1",
    )


def test_joke_social_post_from_firestore_invalid_type():
  """JokeSocialPost rejects invalid type values."""
  with pytest.raises(ValueError):
    models.JokeSocialPost.from_firestore_dict(
      {
        "type": "BAD",
        "pinterest_title": "Title",
        "link_url": "https://example.com",
      },
      key="post1",
    )


def test_joke_social_post_from_firestore_filters_jokes():
  """JokeSocialPost should keep only dict entries in jokes."""
  ts = datetime.datetime(2024, 4, 5, 6, 7, 8, tzinfo=datetime.timezone.utc)
  post = models.JokeSocialPost.from_firestore_dict(
    {
      "type":
      "JOKE_GRID_TEASER",
      "link_url":
      "https://snickerdoodlejokes.com/jokes/test",
      "pinterest_title":
      "Title",
      "pinterest_description":
      "Desc",
      "jokes": [{
        "key": "j1",
        "setup_text": "Setup",
        "punchline_text": "Punch",
      }, "bad", 123],
      "facebook_post_time":
      ts,
    },
    key="post1",
  )
  assert post.type == models.JokeSocialPostType.JOKE_GRID_TEASER
  assert len(post.jokes) == 1
  assert post.jokes[0].key == "j1"
  assert post.facebook_post_time == ts


def test_joke_social_post_from_firestore_keeps_creation_time():
  """JokeSocialPost should keep creation_time when present."""
  created_at = datetime.datetime(2024,
                                 6,
                                 7,
                                 8,
                                 9,
                                 10,
                                 tzinfo=datetime.timezone.utc)
  post = models.JokeSocialPost.from_firestore_dict(
    {
      "type": "JOKE_GRID",
      "link_url": "https://snickerdoodlejokes.com/jokes/test",
      "creation_time": created_at,
    },
    key="post1",
  )

  assert post.creation_time == created_at


def test_joke_social_post_type_description():
  assert "grid" in models.JokeSocialPostType.JOKE_GRID.description.lower()
  assert "teaser" in models.JokeSocialPostType.JOKE_GRID_TEASER.description.lower(
  )
  assert "video" in models.JokeSocialPostType.JOKE_REEL_VIDEO.description.lower(
  )


def test_joke_social_post_video_uri_fields_round_trip():
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_REEL_VIDEO,
    link_url="https://snickerdoodlejokes.com/jokes/video-joke",
    pinterest_video_gcs_uri="gs://bucket/social/video.mp4",
    instagram_video_gcs_uri="gs://bucket/social/video.mp4",
    facebook_video_gcs_uri="gs://bucket/social/video.mp4",
  )
  post.key = "post-video-1"

  payload = post.to_dict()
  assert payload["type"] == "JOKE_REEL_VIDEO"
  assert payload["pinterest_video_gcs_uri"] == "gs://bucket/social/video.mp4"
  assert payload["instagram_video_gcs_uri"] == "gs://bucket/social/video.mp4"
  assert payload["facebook_video_gcs_uri"] == "gs://bucket/social/video.mp4"

  restored = models.JokeSocialPost.from_firestore_dict(payload,
                                                       key="post-video-1")
  assert restored.type == models.JokeSocialPostType.JOKE_REEL_VIDEO
  assert restored.pinterest_video_gcs_uri == "gs://bucket/social/video.mp4"
  assert restored.instagram_video_gcs_uri == "gs://bucket/social/video.mp4"
  assert restored.facebook_video_gcs_uri == "gs://bucket/social/video.mp4"


def test_joke_social_post_platform_summary_pinterest_with_time():
  ts = datetime.datetime(2024, 5, 6, 7, 8)
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/grid",
    pinterest_post_time=ts,
    pinterest_title="Grid title",
    pinterest_description="Grid desc",
    pinterest_alt_text="Grid alt",
  )

  summary = post.platform_summary(models.SocialPlatform.PINTEREST)

  assert summary == "\n".join([
    "Pinterest post:",
    "Title: Grid title",
    "Description: Grid desc",
    "Alt text: Grid alt",
    "Posted at 2024-05-06 07:08",
  ])


def test_joke_social_post_platform_summary_instagram_without_time():
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/grid",
    instagram_caption="Caption text",
    instagram_alt_text="Alt text",
  )

  summary = post.platform_summary(models.SocialPlatform.INSTAGRAM)

  assert summary == "\n".join([
    "Instagram post:",
    "Caption: Caption text",
    "Alt text: Alt text",
  ])


def test_joke_social_post_platform_summary_facebook_with_time():
  ts = datetime.datetime(2024, 8, 9, 10, 11)
  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/grid",
    facebook_post_time=ts,
    facebook_message="Hello friends",
  )

  summary = post.platform_summary(models.SocialPlatform.FACEBOOK)

  assert summary == "\n".join([
    "Facebook post:",
    "Message: Hello friends",
    "Posted at 2024-08-09 10:11",
  ])


def test_jokesheet_slug_builds_from_category_and_index():
  sheet = models.JokeSheet(category_id="reptiles_and_dinosaurs", index=2)
  assert sheet.slug == "free-reptiles-and-dinosaurs-jokes-3"


def test_jokesheet_slug_uses_sheet_slug_when_set():
  sheet = models.JokeSheet(
    category_id="cats",
    index=1,
    sheet_slug="custom-notes-pack",
  )
  assert sheet.slug == "custom-notes-pack"


def test_jokesheet_display_index_returns_one_based_value():
  sheet = models.JokeSheet(category_id="cats", index=0)
  assert sheet.display_index == 1
  sheet = models.JokeSheet(category_id="cats", index=None)
  assert sheet.display_index is None


def test_jokesheet_slug_none_when_missing_fields():
  sheet = models.JokeSheet(category_id=None, index=2)
  assert sheet.slug is None
  sheet = models.JokeSheet(category_id="cats", index=None)
  assert sheet.slug is None


def test_jokesheet_parse_slug_returns_category_and_index():
  category_id, index = models.JokeSheet.parse_slug(
    "free-reptiles-and-dinosaurs-jokes-3")
  assert category_id == "reptiles_and_dinosaurs"
  assert index == 2


def test_jokesheet_parse_slug_rejects_invalid_slug():
  category_id, index = models.JokeSheet.parse_slug("bad-slug")
  assert category_id is None
  assert index is None
  category_id, index = models.JokeSheet.parse_slug("free-animals-jokes-0")
  assert category_id is None
  assert index is None


def test_jokecategory_from_firestore_parses_negative_tags():
  data = {
    "display_name": "Cats",
    "negative_tags": ["nsfw", "  politics  ", 123],
  }
  category = models.JokeCategory.from_firestore_dict(data, key="cats")
  assert category.negative_tags == ["nsfw", "politics"]


def test_amazon_ads_daily_campaign_stats_to_and_from_dict():
  source = models.AmazonAdsDailyCampaignStats(
    campaign_id="camp-1",
    campaign_name="Animal P - Auto",
    date=datetime.date(2026, 2, 18),
    spend=12.5,
    impressions=1500,
    clicks=45,
    kenp_royalties_usd=0.75,
    total_attributed_sales_usd=54.0,
    total_units_sold=9,
    gross_profit_before_ads_usd=44.75,
    gross_profit_usd=32.25,
    sale_items_by_asin_country={
      "B09XYZ": {
        "US":
        models.AmazonProductStats(
          asin="B09XYZ",
          units_sold=2,
          total_sales_usd=20.0,
          total_profit_usd=9.0,
        )
      }
    },
  )

  payload = source.to_dict()
  restored = models.AmazonAdsDailyCampaignStats.from_dict(payload,
                                                          key="daily-key")

  assert restored.key == "daily-key"
  assert restored.campaign_id == "camp-1"
  assert restored.campaign_name == "Animal P - Auto"
  assert restored.date == datetime.date(2026, 2, 18)
  assert restored.gross_profit_before_ads_usd == 44.75
  assert restored.gross_profit_usd == 32.25
  assert restored.sale_items[0].asin == "B09XYZ"
  assert restored.sale_items[0].total_profit_usd == 9.0


def test_amazon_ads_report_from_amazon_payload_supports_camel_case_fields():
  report = models.AmazonAdsReport.from_amazon_payload(
    {
      "reportId": "r-1",
      "name": "20260219_060000_spCampaigns_US",
      "status": "PENDING",
      "configuration": {
        "reportTypeId": "spCampaigns"
      },
      "startDate": "2026-02-18",
      "endDate": "2026-02-18",
      "createdAt": "2026-02-19T06:00:00Z",
      "updatedAt": "2026-02-19T06:05:00Z",
      "generatedAt": "2026-02-19T06:07:00Z",
      "fileSize": 1234,
      "url": "https://example.com/report.gz",
      "urlExpiresAt": "2026-02-19T07:00:00Z",
      "failureReason": "",
    },
    key="doc-key",
  )

  assert report.key == "doc-key"
  assert report.report_id == "r-1"
  assert report.report_name == "20260219_060000_spCampaigns_US"
  assert report.report_type_id == "spCampaigns"
  assert report.start_date == datetime.date(2026, 2, 18)
  assert report.end_date == datetime.date(2026, 2, 18)
  assert report.created_at == datetime.datetime(
    2026,
    2,
    19,
    6,
    0,
    0,
    tzinfo=datetime.timezone.utc,
  )
  assert report.file_size == 1234
  assert report.url == "https://example.com/report.gz"


def test_amazon_ads_report_from_dict_rejects_camel_case_fields():
  with pytest.raises(ValueError):
    models.AmazonAdsReport.from_dict(
      {
        "reportId": "r-1",
        "name": "20260219_060000_spCampaigns_US",
        "status": "PENDING",
        "reportTypeId": "spCampaigns",
        "startDate": "2026-02-18",
        "endDate": "2026-02-18",
        "createdAt": "2026-02-19T06:00:00Z",
        "updatedAt": "2026-02-19T06:05:00Z",
      }, )


def test_amazon_ads_event_to_and_from_dict():
  source = models.AmazonAdsEvent(
    date=datetime.date(2026, 2, 26),
    title="Campaign launch",
    created_at=datetime.datetime(
      2026,
      2,
      26,
      4,
      30,
      tzinfo=datetime.timezone.utc,
    ),
    updated_at=datetime.datetime(
      2026,
      2,
      26,
      5,
      30,
      tzinfo=datetime.timezone.utc,
    ),
  )

  payload = source.to_dict()
  restored = models.AmazonAdsEvent.from_dict(payload, key="event-key")

  assert restored.key == "event-key"
  assert restored.date == datetime.date(2026, 2, 26)
  assert restored.title == "Campaign launch"
  assert restored.created_at == datetime.datetime(
    2026,
    2,
    26,
    4,
    30,
    tzinfo=datetime.timezone.utc,
  )
  assert restored.updated_at == datetime.datetime(
    2026,
    2,
    26,
    5,
    30,
    tzinfo=datetime.timezone.utc,
  )


def test_amazon_ads_event_requires_title():
  with pytest.raises(ValueError):
    models.AmazonAdsEvent.from_dict({
      "date": "2026-02-26",
      "title": "   ",
    }, )
