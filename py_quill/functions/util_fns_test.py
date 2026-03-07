"""Tests for Firestore migrations in util_fns.py."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from common import models
from functions import util_fns


class _DummyDoc:

  def __init__(self, doc_id: str, data: dict, exists: bool = True):
    self.id = doc_id
    self._data = data
    self.exists = exists

  def to_dict(self):
    return self._data


class _DummyQuery:

  def __init__(self, docs: list[_DummyDoc]):
    self._docs = docs

  def where(self, *, filter):
    _ = filter
    return self

  def order_by(self, _field_path, direction=None):
    _ = direction
    return self

  def start_after(self, _doc):
    return self

  def limit(self, _limit):
    return self

  def stream(self):
    return self._docs


class _DummyCollection:

  def __init__(self, docs: list[_DummyDoc]):
    self._docs = docs

  def where(self, *, filter):
    _ = filter
    return _DummyQuery(self._docs)

  def document(self, doc_id):
    for doc in self._docs:
      if doc.id == doc_id:
        return _DummyDocRef(doc)
    return _DummyDocRef(_DummyDoc(doc_id, {}, exists=False))


class _DummyDocRef:

  def __init__(self, doc: _DummyDoc):
    self._doc = doc

  def get(self):
    return self._doc


class _DummyDB:

  def __init__(self, docs: list[_DummyDoc]):
    self._docs = docs

  def collection(self, name):
    assert name == "joke_social_posts"
    return _DummyCollection(self._docs)


def _make_reel_post(
  *,
  post_id: str,
  joke_id: str,
  creation_time: datetime.datetime,
  video_uri: str = "gs://bucket/video.mp4",
  intro: str = "Psst!",
  response: str = "What?",
  setup: str = "Setup",
  punchline: str = "Punchline",
):
  return _DummyDoc(
    post_id,
    {
      "type": "JOKE_REEL_VIDEO",
      "creation_time": creation_time,
      "instagram_video_gcs_uri": video_uri,
      "reel_intro_script": intro,
      "reel_response_script": response,
      "jokes": [{
        "key": joke_id,
        "setup_text": setup,
        "punchline_text": punchline,
      }],
    },
  )


def test_backfill_dry_run_uses_latest_post_per_joke():
  docs = [
    _make_reel_post(
      post_id="post-new",
      joke_id="j1",
      creation_time=datetime.datetime(2026, 2, 20, tzinfo=datetime.timezone.utc),
      intro="New",
    ),
    _make_reel_post(
      post_id="post-old",
      joke_id="j1",
      creation_time=datetime.datetime(2026, 2, 10, tzinfo=datetime.timezone.utc),
      intro="Old",
    ),
    _make_reel_post(
      post_id="post-j2",
      joke_id="j2",
      creation_time=datetime.datetime(2026, 2, 18, tzinfo=datetime.timezone.utc),
    ),
  ]

  db_mock = _DummyDB(docs)
  create_calls: list[object] = []

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.joke_videos_firestore.get_latest_joke_video_for_joke',
               return_value=None):
      with patch('functions.util_fns.joke_videos_firestore.create_joke_video',
                 side_effect=lambda joke_video: create_calls.append(joke_video)):
        with patch('functions.util_fns.cloud_storage.download_bytes_from_gcs',
                   side_effect=AssertionError("Should not download in dry_run")):
          html = util_fns.run_joke_video_backfill_from_social_posts(
            dry_run=True,
            limit=0,
            start_after="",
          )

  assert create_calls == []
  assert "Dry Run: True" in html
  assert "Distinct Jokes Found: 2" in html
  assert "Joke Videos Created (or would create): 2" in html


def test_backfill_creates_joke_video_and_extracts_preview():
  docs = [
    _make_reel_post(
      post_id="post-1",
      joke_id="j1",
      creation_time=datetime.datetime(2026, 2, 20, tzinfo=datetime.timezone.utc),
      video_uri="gs://bucket/video_j1.mp4",
    ),
  ]

  db_mock = _DummyDB(docs)
  created: list[object] = []
  uploaded_previews: list[tuple[str, str]] = []

  preview_image = MagicMock()

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.joke_videos_firestore.get_latest_joke_video_for_joke',
               return_value=None):
      with patch(
        'functions.util_fns.cloud_storage.download_bytes_from_gcs',
        return_value=b"video-bytes",
      ):
        with patch(
          'functions.util_fns._extract_first_frame_image_from_video_bytes',
          return_value=preview_image,
        ):
          with patch(
            'functions.util_fns.cloud_storage.upload_image_to_gcs',
            side_effect=lambda image, base, ext: uploaded_previews.append(
              (base, ext)) or ("gs://bucket/preview_j1.png", b"img"),
          ):
            with patch(
              'functions.util_fns.joke_videos_firestore.create_joke_video',
              side_effect=lambda joke_video: created.append(joke_video)
              or joke_video,
            ):
              html = util_fns.run_joke_video_backfill_from_social_posts(
                dry_run=False,
                limit=0,
                start_after="",
              )

  assert "Dry Run: False" in html
  assert "Joke Videos Created (or would create): 1" in html
  assert len(created) == 1
  saved = created[0]
  assert saved.joke_id == "j1"
  assert saved.video_gcs_uri == "gs://bucket/video_j1.mp4"
  assert saved.preview_image_gcs_uri == "gs://bucket/preview_j1.png"
  assert saved.script_intro == "Psst!"
  assert saved.script_setup == "Setup"
  assert uploaded_previews == [("joke_video_preview_j1", "png")]
  preview_image.close.assert_called_once()


def test_backfill_skips_when_preview_extraction_fails_and_continues():
  docs = [
    _make_reel_post(
      post_id="post-bad",
      joke_id="j1",
      creation_time=datetime.datetime(2026, 2, 20, tzinfo=datetime.timezone.utc),
      video_uri="gs://bucket/bad.mp4",
    ),
    _make_reel_post(
      post_id="post-good",
      joke_id="j2",
      creation_time=datetime.datetime(2026, 2, 19, tzinfo=datetime.timezone.utc),
      video_uri="gs://bucket/good.mp4",
    ),
  ]

  db_mock = _DummyDB(docs)
  created: list[object] = []

  def _extract_first_frame(video_bytes: bytes):
    if video_bytes == b"bad-bytes":
      raise ValueError("broken video")
    return MagicMock(close=MagicMock())

  def _download(video_uri: str):
    return b"bad-bytes" if video_uri.endswith("bad.mp4") else b"good-bytes"

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.joke_videos_firestore.get_latest_joke_video_for_joke',
               return_value=None):
      with patch('functions.util_fns.cloud_storage.download_bytes_from_gcs',
                 side_effect=_download):
        with patch(
          'functions.util_fns._extract_first_frame_image_from_video_bytes',
          side_effect=_extract_first_frame,
        ):
          with patch(
            'functions.util_fns.cloud_storage.upload_image_to_gcs',
            return_value=("gs://bucket/preview.png", b"img"),
          ):
            with patch(
              'functions.util_fns.joke_videos_firestore.create_joke_video',
              side_effect=lambda joke_video: created.append(joke_video)
              or joke_video,
            ):
              html = util_fns.run_joke_video_backfill_from_social_posts(
                dry_run=False,
                limit=0,
                start_after="",
              )

  assert len(created) == 1
  assert created[0].joke_id == "j2"
  assert "Skipped (preview extraction failure): 1" in html
  assert "Errors (1)" in html


def test_backfill_is_idempotent_and_skips_existing_joke_video():
  docs = [
    _make_reel_post(
      post_id="post-j1",
      joke_id="j1",
      creation_time=datetime.datetime(2026, 2, 20, tzinfo=datetime.timezone.utc),
      video_uri="gs://bucket/j1.mp4",
    ),
    _make_reel_post(
      post_id="post-j2",
      joke_id="j2",
      creation_time=datetime.datetime(2026, 2, 19, tzinfo=datetime.timezone.utc),
      video_uri="gs://bucket/j2.mp4",
    ),
  ]
  db_mock = _DummyDB(docs)
  created: list[object] = []
  downloaded_video_uris: list[str] = []
  preview_image = MagicMock()

  existing_j1_video = models.JokeVideo(
    joke_id="j1",
    video_gcs_uri="gs://already/j1.mp4",
    preview_image_gcs_uri="gs://already/j1.png",
    script_intro="Intro",
    script_setup="Setup",
    script_response="Response",
    script_punchline="Punchline",
    teller_character_def_id="cat_orange_tabby",
    listener_character_def_id="dog_beagle",
    generation_metadata=models.GenerationMetadata(),
  )

  def _get_latest_for_joke(joke_id: str) -> models.JokeVideo | None:
    if joke_id == "j1":
      return existing_j1_video
    return None

  def _download(video_uri: str) -> bytes:
    downloaded_video_uris.append(video_uri)
    return b"video-bytes"

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.joke_videos_firestore.get_latest_joke_video_for_joke',
               side_effect=_get_latest_for_joke):
      with patch('functions.util_fns.cloud_storage.download_bytes_from_gcs',
                 side_effect=_download):
        with patch('functions.util_fns._extract_first_frame_image_from_video_bytes',
                   return_value=preview_image):
          with patch(
            'functions.util_fns.cloud_storage.upload_image_to_gcs',
            return_value=("gs://bucket/preview.png", b"img"),
          ):
            with patch(
              'functions.util_fns.joke_videos_firestore.create_joke_video',
              side_effect=lambda joke_video: created.append(joke_video)
              or joke_video,
            ):
              html = util_fns.run_joke_video_backfill_from_social_posts(
                dry_run=False,
                limit=0,
                start_after="",
              )

  assert len(created) == 1
  assert created[0].joke_id == "j2"
  assert downloaded_video_uris == ["gs://bucket/j2.mp4"]
  assert "Skipped (already has joke video): 1" in html
