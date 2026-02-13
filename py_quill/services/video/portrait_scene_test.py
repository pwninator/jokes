from unittest.mock import MagicMock, patch

import pytest

from common import audio_timing, models
from common.posable_character import MouthState, PosableCharacter, Transform
from common.posable_character_sequence import (PosableCharacterSequence,
                                               SequenceMouthEvent,
                                               SequenceSoundEvent,
                                               SequenceTransformEvent)
from PIL import Image
from services.video import scene_video_renderer
from services.video import joke_social_script_builder
from services.video.script import (SceneCanvas, SceneRect, SceneScript,
                                   TimedCharacterSequence, TimedImage)


class _DummyCharacter(PosableCharacter):
  def __init__(self):
    super().__init__(definition=models.PosableCharacterDef(
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
    ))


def _simple_sequence() -> PosableCharacterSequence:
  sequence = PosableCharacterSequence(
    sequence_mouth_state=[
      SequenceMouthEvent(
        start_time=0.0,
        end_time=0.2,
        mouth_state=MouthState.OPEN,
      )
    ],
    sequence_left_hand_transform=[
      SequenceTransformEvent(
        start_time=0.0,
        end_time=0.2,
        target_transform=Transform(translate_y=-10.0),
      )
    ],
    sequence_sound_events=[
      SequenceSoundEvent(
        start_time=0.0,
        end_time=0.2,
        gcs_uri="gs://bucket/a.wav",
        volume=1.0,
      )
    ],
  )
  sequence.validate()
  return sequence


class _ProbingVideoClip:
  def __init__(self, make_frame, duration=None):
    self.make_frame = make_frame
    self.duration = duration
    self.audio = None

  def with_audio(self, audio):
    self.audio = audio
    return self

  def write_videofile(self, output_path, **_kwargs):
    self.make_frame(0.1)
    with open(output_path, "wb") as file_handle:
      file_handle.write(b"fake")

  def close(self):
    pass


class _FakeAudioClip:
  def __init__(self, _path):
    self.start = None
    self.duration = None

  def with_start(self, start):
    self.start = start
    return self

  def with_duration(self, duration):
    self.duration = duration
    return self

  def close(self):
    pass


class _FakeCompositeAudio:
  def __init__(self, _clips):
    pass

  def close(self):
    pass


def test_generate_scene_video_applies_sequence_pose():
  character = _DummyCharacter()
  script = SceneScript(
    canvas=SceneCanvas(width_px=1080, height_px=1920),
    items=[
      TimedImage(
        gcs_uri="gs://bucket/top.png",
        start_time_sec=0.0,
        end_time_sec=1.0,
        z_index=10,
        rect=SceneRect(x_px=0, y_px=0, width_px=1080, height_px=1080),
        fit_mode="fill",
      ),
      TimedImage(
        gcs_uri="gs://bucket/footer.png",
        start_time_sec=0.0,
        end_time_sec=1.0,
        z_index=5,
        rect=SceneRect(x_px=0, y_px=1080, width_px=1080, height_px=840),
        fit_mode="fill",
      ),
      TimedCharacterSequence(
        actor_id="left",
        character=character,
        sequence=_simple_sequence(),
        start_time_sec=0.0,
        end_time_sec=1.0,
        z_index=20,
        rect=SceneRect(x_px=220, y_px=1120, width_px=640, height_px=760),
      ),
    ],
    duration_sec=1.0,
  )

  upload_mock = MagicMock()

  with patch.object(scene_video_renderer.cloud_storage,
                    "download_image_from_gcs",
                    return_value=Image.new("RGBA", (1080, 1080), (0, 0, 0, 255))), \
      patch.object(scene_video_renderer.cloud_storage,
                   "download_bytes_from_gcs",
                   return_value=b"RIFF"), \
      patch.object(scene_video_renderer.cloud_storage,
                   "upload_file_to_gcs",
                   upload_mock), \
      patch.object(scene_video_renderer, "VideoClip", _ProbingVideoClip), \
      patch.object(scene_video_renderer, "AudioFileClip", _FakeAudioClip), \
      patch.object(scene_video_renderer, "CompositeAudioClip", _FakeCompositeAudio):
    scene_video_renderer.generate_scene_video(
      script=script,
      output_gcs_uri="gs://files/video/out.mp4",
      label="create_portrait_character_video",
      fps=24,
    )

  assert character.mouth_state == MouthState.OPEN
  assert character.left_hand_transform.translate_y == pytest.approx(-5.0)
  upload_mock.assert_called_once()


def test_generate_scene_video_reports_metadata():
  character = _DummyCharacter()
  script = SceneScript(
    canvas=SceneCanvas(width_px=1080, height_px=1920),
    items=[
      TimedImage(
        gcs_uri="gs://bucket/footer.png",
        start_time_sec=0.0,
        end_time_sec=0.5,
        z_index=5,
        rect=SceneRect(x_px=0, y_px=1080, width_px=1080, height_px=840),
        fit_mode="fill",
      ),
      TimedCharacterSequence(
        actor_id="actor",
        character=character,
        sequence=_simple_sequence(),
        start_time_sec=0.0,
        end_time_sec=0.5,
        z_index=20,
        rect=SceneRect(x_px=220, y_px=1120, width_px=640, height_px=760),
      ),
    ],
    duration_sec=0.5,
  )

  with patch.object(scene_video_renderer.cloud_storage,
                    "download_image_from_gcs",
                    return_value=Image.new("RGBA", (1080, 1080), (0, 0, 0, 255))), \
      patch.object(scene_video_renderer.cloud_storage,
                   "download_bytes_from_gcs",
                   return_value=b"RIFF"), \
      patch.object(scene_video_renderer.cloud_storage,
                   "upload_file_to_gcs"), \
      patch.object(scene_video_renderer, "VideoClip", _ProbingVideoClip), \
      patch.object(scene_video_renderer, "AudioFileClip", _FakeAudioClip), \
      patch.object(scene_video_renderer, "CompositeAudioClip", _FakeCompositeAudio):
    _uri, metadata = scene_video_renderer.generate_scene_video(
      script=script,
      output_gcs_uri="gs://files/video/test.mp4",
      label="create_portrait_character_video",
      fps=24,
    )

  assert metadata.label == "create_portrait_character_video"
  assert metadata.token_counts["num_characters"] == 1


def test_scene_script_disallows_overlapping_actor_sequences():
  character = _DummyCharacter()
  sequence = _simple_sequence()
  script = SceneScript(
    canvas=SceneCanvas(width_px=1080, height_px=1920),
    items=[
      TimedCharacterSequence(
        actor_id="actor",
        character=character,
        sequence=sequence,
        start_time_sec=0.0,
        end_time_sec=0.3,
        z_index=10,
        rect=SceneRect(x_px=220, y_px=1120, width_px=640, height_px=760),
      ),
      TimedCharacterSequence(
        actor_id="actor",
        character=character,
        sequence=sequence,
        start_time_sec=0.2,
        end_time_sec=0.5,
        z_index=10,
        rect=SceneRect(x_px=220, y_px=1120, width_px=640, height_px=760),
      ),
    ],
    duration_sec=0.5,
  )

  with pytest.raises(ValueError, match="Overlapping character sequence items"):
    script.validate()


def test_scene_script_rejects_zero_duration_items():
  character = _DummyCharacter()
  sequence = _simple_sequence()
  image_script = SceneScript(
    canvas=SceneCanvas(width_px=1080, height_px=1920),
    items=[
      TimedImage(
        gcs_uri="gs://bucket/top.png",
        start_time_sec=0.2,
        end_time_sec=0.2,
        z_index=10,
        rect=SceneRect(x_px=0, y_px=0, width_px=1080, height_px=1080),
        fit_mode="fill",
      )
    ],
    duration_sec=1.0,
  )
  with pytest.raises(ValueError, match="must be > start_time_sec"):
    image_script.validate()

  character_script = SceneScript(
    canvas=SceneCanvas(width_px=1080, height_px=1920),
    items=[
      TimedCharacterSequence(
        actor_id="actor",
        character=character,
        sequence=sequence,
        start_time_sec=0.5,
        end_time_sec=0.5,
        z_index=10,
        rect=SceneRect(x_px=220, y_px=1120, width_px=640, height_px=760),
      )
    ],
    duration_sec=1.0,
  )
  with pytest.raises(ValueError, match="must be > start_time_sec"):
    character_script.validate()


def test_scene_renderer_respects_cross_type_z_order():
  character = _DummyCharacter()
  script = SceneScript(
    canvas=SceneCanvas(width_px=100, height_px=100),
    items=[
      TimedCharacterSequence(
        actor_id="actor",
        character=character,
        sequence=PosableCharacterSequence(),
        start_time_sec=0.0,
        end_time_sec=1.0,
        z_index=5,
        rect=SceneRect(x_px=0, y_px=0, width_px=100, height_px=100),
        fit_mode="fill",
      ),
      TimedImage(
        gcs_uri="gs://bucket/top.png",
        start_time_sec=0.0,
        end_time_sec=1.0,
        z_index=10,
        rect=SceneRect(x_px=0, y_px=0, width_px=100, height_px=100),
        fit_mode="fill",
      ),
    ],
    duration_sec=1.0,
  )

  def _image_stub(gcs_uri: str) -> Image.Image:
    if str(gcs_uri) == "gs://bucket/top.png":
      return Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    return Image.new("RGBA", (100, 100), (0, 255, 0, 255))

  with patch.object(scene_video_renderer.cloud_storage,
                    "download_image_from_gcs",
                    side_effect=_image_stub):
    prepared_images = scene_video_renderer._prepare_images(script)  # pylint: disable=protected-access
    actor_renders = scene_video_renderer._prepare_actor_renders(script)  # pylint: disable=protected-access
    frame = scene_video_renderer._render_scene_frame(  # pylint: disable=protected-access
      time_sec=0.5,
      canvas=script.canvas,
      prepared_images=prepared_images,
      actor_renders=actor_renders,
    )

  pixel = frame[50, 50]
  assert tuple(int(value) for value in pixel.tolist()) == (255, 0, 0)


def test_scene_renderer_uses_half_open_image_windows():
  script = SceneScript(
    canvas=SceneCanvas(width_px=10, height_px=10),
    items=[
      TimedImage(
        gcs_uri="gs://bucket/first.png",
        start_time_sec=0.0,
        end_time_sec=1.0,
        z_index=10,
        rect=SceneRect(x_px=0, y_px=0, width_px=10, height_px=10),
        fit_mode="fill",
      ),
      TimedImage(
        gcs_uri="gs://bucket/second.png",
        start_time_sec=1.0,
        end_time_sec=2.0,
        z_index=10,
        rect=SceneRect(x_px=0, y_px=0, width_px=10, height_px=10),
        fit_mode="fill",
      ),
    ],
    duration_sec=2.0,
  )

  def _image_stub(gcs_uri: str) -> Image.Image:
    if str(gcs_uri).endswith("first.png"):
      return Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    return Image.new("RGBA", (10, 10), (0, 0, 255, 255))

  with patch.object(scene_video_renderer.cloud_storage,
                    "download_image_from_gcs",
                    side_effect=_image_stub):
    prepared_images = scene_video_renderer._prepare_images(script)  # pylint: disable=protected-access
    frame = scene_video_renderer._render_scene_frame(  # pylint: disable=protected-access
      time_sec=1.0,
      canvas=script.canvas,
      prepared_images=prepared_images,
      actor_renders=[],
    )

  pixel = frame[5, 5]
  assert tuple(int(value) for value in pixel.tolist()) == (0, 0, 255)


def test_build_portrait_joke_scene_script_adds_intro_and_end_drumming():
  left_character = _DummyCharacter()
  right_character = _DummyCharacter()
  intro_timing = [
    audio_timing.WordTiming("hey", 0.0, 0.3, char_timings=[]),
    audio_timing.WordTiming("joke", 0.3, 0.6, char_timings=[]),
  ]
  setup_timing = [
    audio_timing.WordTiming("setup", 0.0, 0.5, char_timings=[]),
  ]
  response_timing = [
    audio_timing.WordTiming("what", 0.0, 0.2, char_timings=[]),
  ]
  punchline_timing = [
    audio_timing.WordTiming("punchline", 0.0, 0.5, char_timings=[]),
  ]
  character_dialogs = [
    (left_character, [
      ("gs://bucket/intro.wav", 0.0, "Hey... want to hear a joke?", intro_timing),
      ("gs://bucket/setup.wav", 1.6, "Setup line", setup_timing),
      ("gs://bucket/punchline.wav", 4.0, "Punchline line", punchline_timing),
    ]),
    (right_character, [
      ("gs://bucket/response.wav", 3.0, "what?", response_timing),
    ]),
  ]

  with patch.object(
    _DummyCharacter,
    "get_image",
    return_value=Image.new("RGBA", (100, 80), (0, 0, 0, 255)),
  ):
    script = joke_social_script_builder.build_portrait_joke_scene_script(
      joke_images=[
        ("gs://bucket/setup.png", 0.0),
        ("gs://bucket/punchline.png", 4.0),
      ],
      character_dialogs=character_dialogs,
      footer_background_gcs_uri="gs://bucket/footer.png",
      total_duration_sec=6.5,
      detect_mouth_events_fn=lambda *_args, **_kwargs: [],
      include_drumming=True,
      drumming_duration_sec=2.0,
    )

  character_items = [
    item for item in script.items if isinstance(item, TimedCharacterSequence)
  ]
  drumming_items = [
    item for item in character_items
    if not item.sequence.sequence_sound_events
    and item.sequence.sequence_left_hand_transform
    and item.sequence.sequence_right_hand_transform
  ]
  assert len(drumming_items) == 4

  drumming_by_actor: dict[str, list[TimedCharacterSequence]] = {}
  for item in drumming_items:
    drumming_by_actor.setdefault(item.actor_id, []).append(item)
  assert set(drumming_by_actor.keys()) == {"actor_0", "actor_1"}

  for actor_items in drumming_by_actor.values():
    actor_items.sort(key=lambda item: float(item.start_time_sec))
    assert actor_items[0].start_time_sec == pytest.approx(0.6)
    assert actor_items[0].end_time_sec == pytest.approx(1.6)
    assert actor_items[1].start_time_sec == pytest.approx(4.5)
    assert actor_items[1].end_time_sec == pytest.approx(6.5)


def test_build_portrait_joke_scene_script_adds_top_banner_and_shifts_layout():
  character = _DummyCharacter()
  timing = [
    audio_timing.WordTiming("hello", 0.0, 0.2, char_timings=[]),
  ]
  character_dialogs = [
    (character, [
      ("gs://bucket/audio.wav", 0.0, "hello", timing),
    ]),
  ]

  with patch.object(
    _DummyCharacter,
    "get_image",
    return_value=Image.new("RGBA", (100, 80), (0, 0, 0, 255)),
  ):
    script = joke_social_script_builder.build_portrait_joke_scene_script(
      joke_images=[
        ("gs://bucket/setup.png", 0.0),
      ],
      character_dialogs=character_dialogs,
      footer_background_gcs_uri="gs://bucket/footer.png",
      total_duration_sec=1.0,
      detect_mouth_events_fn=lambda *_args, **_kwargs: [],
      include_drumming=False,
      drumming_duration_sec=0.0,
    )

  image_items = [item for item in script.items if isinstance(item, TimedImage)]
  assert len(image_items) == 4

  banner_item = next(item for item in image_items
                     if item.gcs_uri.endswith("icon_words_transparent_light.png"))
  assert banner_item.rect == SceneRect(x_px=80, y_px=0, width_px=920, height_px=240)

  top_image_item = next(item for item in image_items
                        if item.gcs_uri == "gs://bucket/setup.png")
  assert top_image_item.rect == SceneRect(
    x_px=0,
    y_px=240,
    width_px=1080,
    height_px=1080,
  )

  footer_items = [item for item in image_items
                  if item.gcs_uri == "gs://bucket/footer.png"]
  assert len(footer_items) == 2

  top_banner_background_item = next(item for item in footer_items
                                    if item.rect.y_px == 0)
  assert top_banner_background_item.rect == SceneRect(
    x_px=0,
    y_px=0,
    width_px=1080,
    height_px=240,
  )

  footer_item = next(item for item in footer_items if item.rect.y_px == 1320)
  assert footer_item.rect == SceneRect(
    x_px=0,
    y_px=1320,
    width_px=1080,
    height_px=600,
  )

  character_item = next(item for item in script.items
                        if isinstance(item, TimedCharacterSequence))
  assert character_item.rect.y_px == 1440
