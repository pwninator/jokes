import array
import io
import os
import wave
from unittest.mock import MagicMock, patch

import pytest
from common import audio_timing, models
from common.mouth_events import MouthEvent
from common.posable_character import MouthState, PosableCharacter
from PIL import Image
from services import gen_video
from services.video import scene_video_renderer as portrait_scene
from services.video.mouth import apply_forced_closures


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


class _FakeVideoClip:

  def __init__(self, make_frame, duration=None):
    self.make_frame = make_frame
    self.duration = duration
    self.audio = None

  def set_audio(self, audio):
    self.audio = audio
    return self

  def with_audio(self, audio):
    return self.set_audio(audio)

  def write_videofile(self, output_path, **_kwargs):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as file_handle:
      file_handle.write(b"fake")

  def close(self):
    pass


_DUMMY_CHAR_DEF = models.PosableCharacterDef(
  width=100,
  height=80,
  head_gcs_uri="gs://test/head.png",
  surface_line_gcs_uri="gs://test/surface_line.png",
  left_hand_gcs_uri="gs://test/left_hand.png",
  right_hand_gcs_uri="gs://test/right_hand.png",
  mouth_open_gcs_uri="gs://test/mouth_open.png",
  mouth_closed_gcs_uri="gs://test/mouth_closed.png",
  mouth_o_gcs_uri="gs://test/mouth_o.png",
  left_eye_open_gcs_uri="gs://test/left_eye_open.png",
  left_eye_closed_gcs_uri="gs://test/left_eye_closed.png",
  right_eye_open_gcs_uri="gs://test/right_eye_open.png",
  right_eye_closed_gcs_uri="gs://test/right_eye_closed.png",
)


class _DummyCharacter(PosableCharacter):

  def __init__(self):
    super().__init__(definition=_DUMMY_CHAR_DEF)


def _make_png_bytes(size=(32, 32), color=(255, 0, 0, 255)) -> bytes:
  image = Image.new("RGBA", size, color=color)
  buffer = io.BytesIO()
  image.save(buffer, format="PNG")
  return buffer.getvalue()


def _make_wav_bytes(
  *,
  duration_sec: float = 1.0,
  sample_rate: int = 8000,
  pulses: list[tuple[float, float]] | None = None,
  amplitude: int = 20000,
) -> bytes:
  if pulses is None:
    pulses = [(0.1, 0.18), (0.4, 0.48), (0.7, 0.78)]
  total_samples = int(duration_sec * sample_rate)
  samples = [0] * total_samples
  for start, end in pulses:
    start_idx = int(start * sample_rate)
    end_idx = int(end * sample_rate)
    for idx in range(start_idx, min(end_idx, total_samples)):
      samples[idx] = amplitude
  buffer = io.BytesIO()
  with wave.open(buffer, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(array.array("h", samples).tobytes())
  return buffer.getvalue()


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


def test_apply_forced_closures_inserts_closed_between_same_shapes():
  """Closure inserted when gap exists between same-shape syllables."""
  syllables = [
    MouthEvent(start_time=0.0, end_time=0.1, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.14, end_time=0.24, mouth_shape=MouthState.OPEN),
  ]
  timeline = apply_forced_closures(syllables)

  assert any(state == MouthState.CLOSED for state, _, _ in timeline)
  # Verify timeline is sorted
  starts = [start for _, start, _ in timeline]
  assert starts == sorted(starts)


def test_apply_forced_closures_no_closure_for_different_shapes():
  """No closure between syllables with different mouth shapes."""
  syllables = [
    MouthEvent(start_time=0.0, end_time=0.1, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.14, end_time=0.24, mouth_shape=MouthState.O),
  ]
  timeline = apply_forced_closures(syllables)

  assert not any(state == MouthState.CLOSED for state, _, _ in timeline)


def test_apply_forced_closures_skips_very_short_syllables():
  """No closure for syllables shorter than min_syllable_for_closure_sec."""
  syllables = [
    MouthEvent(start_time=0.0, end_time=0.03, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.05, end_time=0.08, mouth_shape=MouthState.OPEN),
  ]
  timeline = apply_forced_closures(
    syllables,
    min_syllable_for_closure_sec=0.05,
  )

  # Both syllables are < 50ms, so no closure should be inserted
  assert not any(state == MouthState.CLOSED for state, _, _ in timeline)


def test_apply_forced_closures_creates_space_for_adjacent_syllables():
  """Closure created by stealing time from adjacent same-shape syllables."""
  syllables = [
    MouthEvent(start_time=0.0, end_time=0.15, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.15, end_time=0.30, mouth_shape=MouthState.OPEN),
  ]
  timeline = apply_forced_closures(syllables)

  # Should have closure even with zero gap
  assert any(state == MouthState.CLOSED for state, _, _ in timeline)


def test_apply_forced_closures_no_closure_for_large_gap():
  """No closure when gap exceeds max_gap_sec (natural silence)."""
  syllables = [
    MouthEvent(start_time=0.0, end_time=0.1, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.5, end_time=0.6, mouth_shape=MouthState.OPEN),
  ]
  timeline = apply_forced_closures(
    syllables,
    max_gap_sec=0.15,
  )

  # Gap is 0.4s which exceeds max_gap_sec, so no closure
  assert not any(state == MouthState.CLOSED for state, _, _ in timeline)


def test_apply_forced_closures_dynamic_duration():
  """Closure duration scales with syllable duration."""
  # Long syllables should get longer closures
  long_syllables = [
    MouthEvent(start_time=0.0, end_time=0.2, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.25, end_time=0.45, mouth_shape=MouthState.OPEN),
  ]
  long_timeline = apply_forced_closures(long_syllables)
  long_closures = [(s, e) for state, s, e in long_timeline
                   if state == MouthState.CLOSED]

  # Short syllables should get shorter closures
  short_syllables = [
    MouthEvent(start_time=0.0, end_time=0.08, mouth_shape=MouthState.OPEN),
    MouthEvent(start_time=0.12, end_time=0.20, mouth_shape=MouthState.OPEN),
  ]
  short_timeline = apply_forced_closures(short_syllables)
  short_closures = [(s, e) for state, s, e in short_timeline
                    if state == MouthState.CLOSED]

  assert len(long_closures) == 1
  assert len(short_closures) == 1

  long_closure_duration = long_closures[0][1] - long_closures[0][0]
  short_closure_duration = short_closures[0][1] - short_closures[0][0]

  # Long syllables should produce longer closure (or at least not shorter)
  assert long_closure_duration >= short_closure_duration


def test_apply_forced_closures_empty_input():
  """Empty syllable list returns empty timeline."""
  timeline = apply_forced_closures([])
  assert timeline == []


def test_apply_forced_closures_single_syllable():
  """Single syllable returns timeline with just that syllable."""
  syllables = [
    MouthEvent(start_time=0.0, end_time=0.1, mouth_shape=MouthState.OPEN),
  ]
  timeline = apply_forced_closures(syllables)

  assert len(timeline) == 1
  assert timeline[0] == (MouthState.OPEN, 0.0, 0.1)


def test_create_portrait_character_video_uploads_mp4():
  joke_images = [
    ("gs://bucket/image1.png", 0.0),
    ("gs://bucket/image2.png", 0.2),
  ]
  timing = [
    audio_timing.WordTiming(word="hi",
                            start_time=0.0,
                            end_time=0.1,
                            char_timings=[])
  ]
  character_dialogs = [
    (_DummyCharacter(), [("gs://bucket/audio1.wav", 0.0, "hello world", timing)
                         ]),
    (_DummyCharacter(), [("gs://bucket/audio2.wav", 0.2, "hi there", timing)]),
  ]
  upload_mock = MagicMock()
  get_uri_mock = MagicMock(return_value="gs://files/video/portrait.mp4")

  def download_bytes(uri):
    if uri.endswith(".wav"):
      return _make_wav_bytes(duration_sec=0.4)
    return _make_png_bytes()

  def download_image(_uri):
    return Image.new("RGBA", (32, 32), color=(0, 255, 0, 255))

  detect_calls: list[object] = []

  def detect_stub(_wav_bytes, *, mode: str, transcript=None, timing=None):
    detect_calls.append((mode, transcript, timing))
    return []

  with patch.object(gen_video.utils, "is_emulator", return_value=False), \
      patch.object(gen_video.cloud_storage, "get_video_gcs_uri", get_uri_mock), \
      patch.object(gen_video.cloud_storage, "download_bytes_from_gcs",
                   side_effect=download_bytes), \
      patch.object(gen_video.cloud_storage, "download_image_from_gcs",
                   side_effect=download_image), \
      patch.object(gen_video.mouth_event_detection,
                   "detect_mouth_events",
                   side_effect=detect_stub), \
      patch.object(gen_video.cloud_storage, "upload_file_to_gcs",
                   upload_mock), \
      patch.object(portrait_scene, "VideoClip", _FakeVideoClip), \
      patch.object(portrait_scene, "AudioFileClip", _FakeAudioFileClip), \
      patch.object(portrait_scene, "CompositeAudioClip", _FakeCompositeAudioClip):
    gcs_uri, metadata = gen_video.create_portrait_character_video(
      joke_images=joke_images,
      character_dialogs=character_dialogs,
      footer_background_gcs_uri="gs://bucket/footer.png",
      total_duration_sec=0.6,
      output_filename_base="portrait",
      temp_output=True,
    )

  assert gcs_uri == "gs://files/video/portrait.mp4"
  assert metadata.model_name == "moviepy"
  assert metadata.token_counts["num_images"] == 5
  assert metadata.token_counts["num_audio_files"] == 2
  assert metadata.token_counts["num_characters"] == 2
  assert [mode for mode, _transcript, _timing in detect_calls] == [
    "timing",
    "timing",
  ]
  assert {transcript
          for _mode, transcript, _timing in detect_calls} == {
            "hello world",
            "hi there",
          }

  get_uri_mock.assert_called_once()
  assert get_uri_mock.call_args.kwargs["temp"] is True
  upload_mock.assert_called_once()
  uploaded_path = upload_mock.call_args.args[0]
  uploaded_uri = upload_mock.call_args.args[1]
  uploaded_content_type = upload_mock.call_args.kwargs["content_type"]
  assert uploaded_uri == "gs://files/video/portrait.mp4"
  assert uploaded_content_type == "video/mp4"
  assert uploaded_path.endswith("scene.mp4")


def test_create_portrait_character_test_video_uploads_mp4():
  timing = [
    audio_timing.WordTiming(word="hi",
                            start_time=0.0,
                            end_time=0.1,
                            char_timings=[])
  ]
  character_dialogs = [
    (_DummyCharacter(), [("gs://bucket/audio1.wav", 0.0, "hello world", timing)
                         ]),
    (_DummyCharacter(), [("gs://bucket/audio2.wav", 0.0, "hi there", timing)]),
  ]
  upload_mock = MagicMock()
  get_uri_mock = MagicMock(return_value="gs://files/video/portrait_test.mp4")

  def download_bytes(uri):
    if uri.endswith(".wav"):
      return _make_wav_bytes(duration_sec=0.4)
    return b"data"

  def download_image(_uri):
    return Image.new("RGBA", (32, 32), color=(0, 255, 0, 255))

  detect_calls: list[object] = []

  def detect_stub(_wav_bytes, *, mode: str, transcript=None, timing=None):
    detect_calls.append((mode, transcript, timing is not None))
    assert mode == "timing"
    return []

  with patch.object(gen_video.utils, "is_emulator", return_value=False), \
      patch.object(gen_video.cloud_storage, "get_video_gcs_uri", get_uri_mock), \
      patch.object(gen_video.cloud_storage, "download_bytes_from_gcs",
                   side_effect=download_bytes), \
      patch.object(gen_video.cloud_storage, "download_image_from_gcs",
                   side_effect=download_image), \
      patch.object(gen_video.mouth_event_detection,
                   "detect_mouth_events",
                   side_effect=detect_stub), \
      patch.object(gen_video.cloud_storage, "upload_file_to_gcs",
                   upload_mock), \
      patch.object(portrait_scene, "VideoClip", _FakeVideoClip), \
      patch.object(portrait_scene, "AudioFileClip", _FakeAudioFileClip), \
      patch.object(portrait_scene, "CompositeAudioClip", _FakeCompositeAudioClip):
    gcs_uri, metadata = gen_video.create_portrait_character_test_video(
      character_dialogs=character_dialogs,
      footer_background_gcs_uri="gs://bucket/footer.png",
      total_duration_sec=0.4,
      output_filename_base="portrait_test",
      temp_output=True,
    )

  assert gcs_uri == "gs://files/video/portrait_test.mp4"
  assert metadata.model_name == "moviepy"
  assert metadata.token_counts["num_images"] == 1
  assert metadata.token_counts["num_characters"] == 2

  # Sequence generation runs lip-sync detection once per character track.
  assert len(detect_calls) == 2
  assert all(mode == "timing"
             for mode, _transcript, _has_timing in detect_calls)
  assert all(_has_timing for _mode, _transcript, _has_timing in detect_calls)
  assert {transcript for _mode, transcript, _has_timing in detect_calls} == {
    "hello world",
    "hi there",
  }

  get_uri_mock.assert_called_once()
  assert get_uri_mock.call_args.kwargs["temp"] is True
  upload_mock.assert_called_once()
  uploaded_path = upload_mock.call_args.args[0]
  uploaded_uri = upload_mock.call_args.args[1]
  uploaded_content_type = upload_mock.call_args.kwargs["content_type"]
  assert uploaded_uri == "gs://files/video/portrait_test.mp4"
  assert uploaded_content_type == "video/mp4"
  assert uploaded_path.endswith("scene.mp4")
