from unittest.mock import MagicMock, patch

import pytest

from common import models
from common.posable_character import MouthState, PosableCharacter, Transform
from services import cloud_storage as cloud_storage_module
from services.video import portrait_scene
from services.video.script import (CharacterTrackSpec, DialogClip,
                                   PortraitJokeVideoScript, TimedImage)
from PIL import Image


class _DummyCharacter(PosableCharacter):
  def __init__(self):
    super().__init__(definition=models.PosableCharacterDef(
      width=100,
      height=80,
      head_gcs_uri="gs://test/head.png",
      left_hand_gcs_uri="gs://test/left_hand.png",
      right_hand_gcs_uri="gs://test/right_hand.png",
      mouth_open_gcs_uri="gs://test/mouth_open.png",
      mouth_closed_gcs_uri="gs://test/mouth_closed.png",
      mouth_o_gcs_uri="gs://test/mouth_o.png",
      left_eye_open_gcs_uri="gs://test/left_eye_open.png",
      left_eye_closed_gcs_uri="gs://test/left_eye_closed.png",
      right_eye_open_gcs_uri="gs://test/right_eye_open.png",
      right_eye_closed_gcs_uri="gs://test/right_eye_closed.png",
    ))


def test_build_blink_timeline_is_deterministic():
  t1 = portrait_scene._build_blink_timeline(duration_sec=12.0, seed=123)
  t2 = portrait_scene._build_blink_timeline(duration_sec=12.0, seed=123)
  assert t1.segments == t2.segments
  assert any(seg.value is False for seg in t1.segments)


def test_blink_and_drumming_apply_to_pose():
  character = _DummyCharacter()
  mouth_timeline = portrait_scene.SegmentTimeline.from_value_segments([
    (MouthState.OPEN, 0.0, 0.5),
  ])
  blink_timeline = portrait_scene._build_blink_timeline(duration_sec=10.0,
                                                       seed=1)
  assert blink_timeline.segments
  blink_mid = (blink_timeline.segments[0].start_time +
               blink_timeline.segments[0].end_time) / 2.0

  left_hand_timeline, right_hand_timeline = portrait_scene._build_drumming_hand_timelines(
    start_time_sec=8.0,
    end_time_sec=10.0,
    step_sec=0.1,
    amplitude_px=10.0,
  )

  render = portrait_scene._CharacterRender(
    character=character,
    position=(0, 0),
    mouth_timeline=mouth_timeline,
    scale=1.0,
    blink_timeline=blink_timeline,
    left_hand_timeline=left_hand_timeline,
    right_hand_timeline=right_hand_timeline,
  )

  joke_images = [(0.0, Image.new("RGBA", (1080, 1080), (0, 0, 0, 255)))]
  footer = Image.new("RGBA", (1080, 840), (0, 0, 0, 255))

  # During blink window, both eyes should be closed.
  with patch.object(cloud_storage_module,
                    "download_image_from_gcs",
                    return_value=Image.new("RGBA", (32, 32), (0, 0, 0, 0))):
    portrait_scene._render_portrait_frame(
      time_sec=blink_mid,
      joke_images=joke_images,
      footer_background=footer,
      character_renders=[render],
    )
  assert character.left_eye_open is False
  assert character.right_eye_open is False

  # During drumming window, left and right hands should be opposite directions.
  with patch.object(cloud_storage_module,
                    "download_image_from_gcs",
                    return_value=Image.new("RGBA", (32, 32), (0, 0, 0, 0))):
    portrait_scene._render_portrait_frame(
      time_sec=8.05,
      joke_images=joke_images,
      footer_background=footer,
      character_renders=[render],
    )
  assert character.left_hand_transform.translate_y == pytest.approx(-10.0)
  assert character.right_hand_transform.translate_y == pytest.approx(10.0)

  with patch.object(cloud_storage_module,
                    "download_image_from_gcs",
                    return_value=Image.new("RGBA", (32, 32), (0, 0, 0, 0))):
    portrait_scene._render_portrait_frame(
      time_sec=8.15,
      joke_images=joke_images,
      footer_background=footer,
      character_renders=[render],
    )
  assert character.left_hand_transform.translate_y == pytest.approx(10.0)
  assert character.right_hand_transform.translate_y == pytest.approx(-10.0)


def test_generate_portrait_joke_video_appends_drumming_window():
  # Use a probing VideoClip that calls make_frame near the end so we can
  # assert drumming is applied without encoding a real video.
  class _ProbingVideoClip:
    def __init__(self, make_frame, duration=None):
      self.make_frame = make_frame
      self.duration = duration
      self.audio = None

    def with_audio(self, audio):
      self.audio = audio
      return self

    def write_videofile(self, output_path, **_kwargs):
      # sample a frame in the drumming window
      self.make_frame(float(self.duration) - 0.5)
      with open(output_path, "wb") as f:
        f.write(b"fake")

    def close(self):
      pass

  class _FakeAudioClip:
    def __init__(self, _path):
      self.start = None

    def with_start(self, start):
      self.start = start
      return self

    def close(self):
      pass

  class _FakeCompositeAudio:
    def __init__(self, _clips):
      pass

    def close(self):
      pass

  character = _DummyCharacter()
  script = PortraitJokeVideoScript(
    joke_images=[TimedImage(gcs_uri="gs://bucket/img.png", start_time_sec=0.0)],
    footer_background_gcs_uri="gs://bucket/footer.png",
    characters=[
      CharacterTrackSpec(
        character_id="c0",
        character=character,
        dialogs=[
          DialogClip(
            audio_gcs_uri="gs://bucket/a.wav",
            start_time_sec=0.0,
            transcript="hi",
            timing=[],
          )
        ],
      )
    ],
    duration_sec=6.0,
    fps=24,
    seed=42,
  )

  def download_image(_uri):
    if _uri.endswith("footer.png"):
      return Image.new("RGBA", (1080, 840), (0, 0, 0, 255))
    return Image.new("RGBA", (1080, 1080), (0, 0, 0, 255))

  upload_mock = MagicMock()

  with patch.object(portrait_scene.cloud_storage,
                    "download_image_from_gcs",
                    side_effect=download_image), \
      patch.object(portrait_scene.cloud_storage,
                   "download_bytes_from_gcs",
                   return_value=b"RIFF"), \
      patch.object(portrait_scene.cloud_storage,
                   "upload_file_to_gcs",
                   upload_mock), \
      patch.object(portrait_scene, "VideoClip", _ProbingVideoClip), \
      patch.object(portrait_scene, "AudioFileClip", _FakeAudioClip), \
      patch.object(portrait_scene, "CompositeAudioClip", _FakeCompositeAudio):
    portrait_scene.generate_portrait_joke_video(
      script=script,
      output_gcs_uri="gs://files/video/out.mp4",
    )

  # Probing frame render should have applied drumming transforms.
  assert abs(character.left_hand_transform.translate_y) == pytest.approx(10.0)
  assert abs(character.right_hand_transform.translate_y) == pytest.approx(10.0)
  assert character.left_hand_transform.translate_y == -character.right_hand_transform.translate_y
