import os
from unittest.mock import MagicMock, patch

import pytest

from services import gen_video


class _FakeImageClip:

  def __init__(self, path):
    self.path = path
    self.size = (640, 480)
    self.start = None
    self.duration = None

  def set_start(self, start):
    self.start = start
    return self

  def set_duration(self, duration):
    self.duration = duration
    return self

  def resize(self, newsize):
    self.size = newsize
    return self

  def with_start(self, start):
    return self.set_start(start)

  def with_duration(self, duration):
    return self.set_duration(duration)

  def resized(self, new_size=None, **_kwargs):
    if new_size is not None:
      self.size = new_size
    return self

  def close(self):
    pass


class _FakeAudioFileClip:

  def __init__(self, path):
    self.path = path
    self.start = None

  def set_start(self, start):
    self.start = start
    return self

  def with_start(self, start):
    return self.set_start(start)

  def close(self):
    pass


class _FakeCompositeAudioClip:

  def __init__(self, clips):
    self.clips = clips

  def close(self):
    pass


class _FakeCompositeVideoClip:

  def __init__(self, clips, size=None):
    self.clips = clips
    self.size = size
    self.duration = None
    self.audio = None

  def set_duration(self, duration):
    self.duration = duration
    return self

  def set_audio(self, audio):
    self.audio = audio
    return self

  def with_duration(self, duration):
    return self.set_duration(duration)

  def with_audio(self, audio):
    return self.set_audio(audio)

  def write_videofile(self, output_path, **_kwargs):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as file_handle:
      file_handle.write(b"fake")

  def close(self):
    pass


def test_create_slideshow_video_uploads_mp4():
  images = [
    ("gs://bucket/image1.jpg", 0.0),
    ("gs://bucket/image2.jpg", 2.0),
  ]
  audio_files = [
    ("gs://bucket/audio1.wav", 1.0),
  ]
  upload_mock = MagicMock()
  get_uri_mock = MagicMock(return_value="gs://files/video/out.mp4")

  with patch.object(gen_video.utils, "is_emulator", return_value=False), \
      patch.object(gen_video.cloud_storage, "get_video_gcs_uri", get_uri_mock), \
      patch.object(gen_video.cloud_storage,
                   "download_bytes_from_gcs",
                   return_value=b"data"), \
      patch.object(gen_video.cloud_storage,
                   "upload_file_to_gcs",
                   upload_mock), \
      patch.object(gen_video, "ImageClip", _FakeImageClip), \
      patch.object(gen_video, "CompositeVideoClip", _FakeCompositeVideoClip), \
      patch.object(gen_video, "AudioFileClip", _FakeAudioFileClip), \
      patch.object(gen_video, "CompositeAudioClip", _FakeCompositeAudioClip):
    gcs_uri, metadata = gen_video.create_slideshow_video(
      images=images,
      audio_files=audio_files,
      total_duration_sec=5.0,
      output_filename_base="out",
      temp_output=True,
    )

  assert gcs_uri == "gs://files/video/out.mp4"
  assert metadata.model_name == "moviepy"
  assert metadata.token_counts["num_images"] == 2
  assert metadata.token_counts["num_audio_files"] == 1
  assert metadata.token_counts["video_duration_sec"] == 5
  assert metadata.token_counts["output_file_size_bytes"] == 4

  get_uri_mock.assert_called_once()
  assert get_uri_mock.call_args.kwargs["temp"] is True
  upload_mock.assert_called_once()
  uploaded_path = upload_mock.call_args.args[0]
  uploaded_uri = upload_mock.call_args.args[1]
  uploaded_content_type = upload_mock.call_args.kwargs["content_type"]
  assert uploaded_uri == "gs://files/video/out.mp4"
  assert uploaded_content_type == "video/mp4"
  assert uploaded_path.endswith("slideshow.mp4")


def test_create_slideshow_video_requires_first_image_at_zero():
  with pytest.raises(gen_video.GenVideoError, match="First image must start"):
    gen_video.create_slideshow_video(
      images=[("gs://bucket/image1.jpg", 1.0)],
      audio_files=[],
      total_duration_sec=5.0,
      output_filename_base="out",
    )


def test_create_slideshow_video_rejects_audio_start_after_duration():
  with pytest.raises(gen_video.GenVideoError, match="Audio start time"):
    gen_video.create_slideshow_video(
      images=[("gs://bucket/image1.jpg", 0.0)],
      audio_files=[("gs://bucket/audio1.wav", 5.0)],
      total_duration_sec=5.0,
      output_filename_base="out",
    )


def test_create_slideshow_video_emulator_returns_test_uri():
  with patch.object(gen_video.utils, "is_emulator", return_value=True):
    gcs_uri, metadata = gen_video.create_slideshow_video(
      images=[("gs://bucket/image1.jpg", 0.0)],
      audio_files=[],
      total_duration_sec=5.0,
      output_filename_base="out",
    )

  assert gcs_uri.startswith("gs://test_story_video_data/")
  assert metadata.is_empty
