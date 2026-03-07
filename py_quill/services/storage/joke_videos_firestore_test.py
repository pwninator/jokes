"""Tests for the joke_videos_firestore module."""

from common import models
from services.storage import joke_videos_firestore


def test_create_joke_video_creates_document(monkeypatch):
  captured: dict[str, object] = {}

  class DummyDoc:
    exists = False

  class DummyDocRef:

    def get(self):
      return DummyDoc()

    def set(self, data):
      captured["data"] = data

  class DummyCollection:

    def document(self, doc_id):
      captured["doc_id"] = doc_id
      return DummyDocRef()

  class DummyDB:

    def collection(self, name):
      captured["collection"] = name
      return DummyCollection()

  monkeypatch.setattr(joke_videos_firestore.firestore, "db", DummyDB)
  monkeypatch.setattr(joke_videos_firestore, "SERVER_TIMESTAMP", "TS")
  monkeypatch.setattr(joke_videos_firestore.utils,
                      "create_timestamped_firestore_key",
                      lambda *_args: "video-doc-1")

  joke_video = models.JokeVideo(
    joke_id="j1",
    video_gcs_uri="gs://bucket/video/j1.mp4",
    script_intro="Hey!",
    script_setup="Setup",
    script_response="What?",
    script_punchline="Punchline",
  )
  created = joke_videos_firestore.create_joke_video(joke_video)

  assert created is not None
  assert created.key == "video-doc-1"
  assert captured["collection"] == "joke_videos"
  assert captured["doc_id"] == "video-doc-1"
  assert captured["data"]["joke_id"] == "j1"
  assert captured["data"]["video_gcs_uri"] == "gs://bucket/video/j1.mp4"
  assert captured["data"]["creation_time"] == "TS"


def test_get_latest_joke_video_for_joke_returns_newest(monkeypatch):

  class DummyDoc:

    def __init__(self, doc_id, data):
      self.id = doc_id
      self._data = data
      self.exists = True

    def to_dict(self):
      return self._data

  class DummyQuery:

    def __init__(self):
      self.filters = []

    def where(self, *, filter):
      self.filters.append(filter)
      return self

    def order_by(self, _field, direction=None):
      _ = direction
      return self

    def limit(self, _n):
      return self

    def stream(self):
      return [
        DummyDoc(
          "video-doc-1",
          {
            "joke_id": "j1",
            "video_gcs_uri": "gs://bucket/video/j1.mp4",
            "script_intro": "Hey!",
            "script_setup": "Setup",
            "script_response": "What?",
            "script_punchline": "Punchline",
          },
        )
      ]

  class DummyDB:

    def collection(self, name):
      assert name == "joke_videos"
      return DummyQuery()

  monkeypatch.setattr(joke_videos_firestore.firestore, "db", DummyDB)
  joke_video = joke_videos_firestore.get_latest_joke_video_for_joke("j1")
  assert joke_video is not None
  assert joke_video.key == "video-doc-1"
  assert joke_video.joke_id == "j1"
  assert joke_video.video_gcs_uri == "gs://bucket/video/j1.mp4"


def test_get_recent_joke_videos_returns_list(monkeypatch):

  class DummyDoc:

    def __init__(self, doc_id):
      self.id = doc_id
      self.exists = True

    def to_dict(self):
      return {
        "joke_id": "j1",
        "video_gcs_uri": f"gs://bucket/video/{self.id}.mp4",
        "script_intro": "Hey!",
        "script_setup": "Setup",
        "script_response": "What?",
        "script_punchline": "Punchline",
      }

  class DummyQuery:

    def order_by(self, _field, direction=None):
      _ = direction
      return self

    def limit(self, _n):
      return self

    def stream(self):
      return [DummyDoc("video-1"), DummyDoc("video-2")]

  class DummyDB:

    def collection(self, name):
      assert name == "joke_videos"
      return DummyQuery()

  monkeypatch.setattr(joke_videos_firestore.firestore, "db", DummyDB)
  videos = joke_videos_firestore.get_recent_joke_videos(limit=2)
  assert len(videos) == 2
  assert videos[0].key == "video-1"
  assert videos[1].key == "video-2"

