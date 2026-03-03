"""Tests for the joke_media_operations module."""
import array
import io
import wave
from unittest.mock import Mock

import pytest
from common import audio_timing, joke_media_operations, models
from common.character_animator import CharacterAnimator


@pytest.fixture(name='mock_firestore')
def mock_firestore_fixture(monkeypatch):
  """Fixture that mocks the firestore service."""
  mock_firestore = Mock()
  mock_firestore.get_posable_character_def.side_effect = (
    lambda character_def_id: models.PosableCharacterDef(
      key=character_def_id,
      width=1,
      height=1,
    ))
  monkeypatch.setattr(joke_media_operations, 'firestore', mock_firestore)
  return mock_firestore


@pytest.fixture(name='mock_cloud_storage')
def mock_cloud_storage_fixture(monkeypatch):
  """Fixture that mocks the cloud_storage service."""
  mock_cloud_storage = Mock()
  mock_cloud_storage.get_and_convert_wave_bytes_from_gcs.side_effect = (
    lambda gcs_uri: mock_cloud_storage.download_bytes_from_gcs(gcs_uri))
  monkeypatch.setattr(joke_media_operations, 'cloud_storage',
                      mock_cloud_storage)
  return mock_cloud_storage


def test_generate_joke_audio_splits_on_two_one_second_pauses_and_uploads(
  monkeypatch,
  mock_cloud_storage,
):
  """generate_joke_audio should upload dialog + split clips."""

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  rate = 24000
  one_second_silence = array.array("h", [0] * rate).tobytes()
  intro_audio = array.array("h", [500] * int(rate * 0.15)).tobytes()
  setup_audio = array.array("h", [1000] * int(rate * 0.2)).tobytes()
  response_audio = array.array("h", [2000] * int(rate * 0.1)).tobytes()
  punchline_audio = array.array("h", [3000] * int(rate * 0.3)).tobytes()
  dialog_frames = (intro_audio + one_second_silence + setup_audio +
                   one_second_silence + response_audio + one_second_silence +
                   punchline_audio)
  dialog_wav_bytes = make_wav_bytes(dialog_frames, rate=rate)
  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.15,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=1.15,
        end_time_seconds=1.35,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=2.35,
        end_time_seconds=2.45,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=3.45,
        end_time_seconds=3.75,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("intro", 0.0, 0.15, char_timings=[]),
      audio_timing.WordTiming("setup", 1.15, 1.35, char_timings=[]),
      audio_timing.WordTiming("response", 2.35, 2.45, char_timings=[]),
      audio_timing.WordTiming("punchline", 3.45, 3.75, char_timings=[]),
    ],
  )

  generation_metadata = models.SingleGenerationMetadata(
    model_name="gemini-tts",
    token_counts={
      "prompt_tokens": 10,
      "output_tokens": 20,
    },
    cost=0.123,
  )
  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = (
    joke_media_operations.audio_client.AudioGenerationResult(
      gcs_uri="gs://temp/dialog.wav",
      metadata=generation_metadata,
      timing=timing,
    ))
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )

  mock_cloud_storage.download_bytes_from_gcs.return_value = dialog_wav_bytes
  dialog_uri = "gs://temp/dialog.wav"
  intro_uri = "gs://public/audio/intro.wav"
  setup_uri = "gs://public/audio/setup.wav"
  response_uri = "gs://public/audio/response.wav"
  punchline_uri = "gs://public/audio/punchline.wav"
  mock_cloud_storage.get_audio_gcs_uri.side_effect = [
    intro_uri,
    setup_uri,
    response_uri,
    punchline_uri,
  ]

  uploaded: list[tuple[str, bytes, str]] = []

  def record_upload(content_bytes: bytes, gcs_uri: str, content_type: str):
    uploaded.append((gcs_uri, content_bytes, content_type))
    return gcs_uri

  mock_cloud_storage.upload_bytes_to_gcs.side_effect = record_upload

  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup text",
    punchline_text="Punchline text",
  )

  result = joke_media_operations.generate_joke_audio(joke)

  assert result.dialog_gcs_uri == dialog_uri
  assert result.intro_gcs_uri == intro_uri
  assert result.setup_gcs_uri == setup_uri
  assert result.response_gcs_uri == response_uri
  assert result.punchline_gcs_uri == punchline_uri
  assert result.generation_metadata.generations == [generation_metadata]
  assert result.clip_timing is not None
  assert [u[0] for u in uploaded] == [
    intro_uri,
    setup_uri,
    response_uri,
    punchline_uri,
  ]
  assert all(u[2] == "audio/wav" for u in uploaded)
  assert all(u[1][:4] == b"RIFF" for u in uploaded)

  def num_frames(wav_bytes: bytes) -> int:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
      # pylint: disable=no-member
      return wf.getnframes()

  assert 0 < num_frames(uploaded[0][1]) < int(rate * 0.3)
  assert 0 < num_frames(uploaded[1][1]) < int(rate * 0.3)
  assert int(rate * 0.8) < num_frames(uploaded[2][1]) < int(rate * 1.2)
  assert int(rate * 1.0) < num_frames(uploaded[3][1]) < int(rate * 1.4)


def test_generate_joke_audio_uses_turn_templates(monkeypatch,
                                                 mock_cloud_storage):

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  rate = 24000
  one_second_silence = array.array("h", [0] * rate).tobytes()
  intro_audio = array.array("h", [500] * int(rate * 0.15)).tobytes()
  setup_audio = array.array("h", [1000] * int(rate * 0.2)).tobytes()
  response_audio = array.array("h", [2000] * int(rate * 0.1)).tobytes()
  punchline_audio = array.array("h", [3000] * int(rate * 0.3)).tobytes()
  dialog_frames = (intro_audio + one_second_silence + setup_audio +
                   one_second_silence + response_audio + one_second_silence +
                   punchline_audio)
  dialog_wav_bytes = make_wav_bytes(dialog_frames, rate=rate)
  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.15,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=1.15,
        end_time_seconds=1.35,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=2.35,
        end_time_seconds=2.45,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=3.45,
        end_time_seconds=3.75,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("intro", 0.0, 0.15, char_timings=[]),
      audio_timing.WordTiming("setup", 1.15, 1.35, char_timings=[]),
      audio_timing.WordTiming("response", 2.35, 2.45, char_timings=[]),
      audio_timing.WordTiming("punchline", 3.45, 3.75, char_timings=[]),
    ],
  )

  generation_metadata = models.SingleGenerationMetadata(
    model_name="gemini-tts")
  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = (
    joke_media_operations.audio_client.AudioGenerationResult(
      gcs_uri="gs://temp/dialog.wav",
      metadata=generation_metadata,
      timing=timing,
    ))
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )

  mock_cloud_storage.download_bytes_from_gcs.return_value = dialog_wav_bytes
  mock_cloud_storage.get_audio_gcs_uri.side_effect = [
    "gs://public/audio/intro.wav",
    "gs://public/audio/setup.wav",
    "gs://public/audio/response.wav",
    "gs://public/audio/punchline.wav",
  ]
  mock_cloud_storage.upload_bytes_to_gcs.return_value = None

  joke = models.PunnyJoke(
    key="joke-9",
    setup_text="Setup text",
    punchline_text="Punchline text",
  )

  script_template = [
    joke_media_operations.audio_client.DialogTurn(
      voice=joke_media_operations.audio_voices.Voice.GEMINI_KORE,
      script="Intro line",
      pause_sec_after=1.0,
    ),
    joke_media_operations.audio_client.DialogTurn(
      voice=joke_media_operations.audio_voices.Voice.GEMINI_KORE,
      script="{setup_text}",
      pause_sec_after=1.0,
    ),
    joke_media_operations.audio_client.DialogTurn(
      voice=joke_media_operations.audio_voices.Voice.GEMINI_PUCK,
      script="what?",
      pause_sec_after=1.0,
    ),
    joke_media_operations.audio_client.DialogTurn(
      voice=joke_media_operations.audio_voices.Voice.GEMINI_KORE,
      script="{punchline_text}\n[giggles]",
    ),
  ]

  _ = joke_media_operations.generate_joke_audio(
    joke,
    script_template=script_template,
  )

  mock_client.generate_multi_turn_dialog.assert_called_once()
  call_kwargs = mock_client.generate_multi_turn_dialog.call_args.kwargs
  turns = call_kwargs["turns"]
  assert [
    (t.voice, t.script, t.pause_sec_before, t.pause_sec_after) for t in turns
  ] == [
    (joke_media_operations.audio_voices.Voice.GEMINI_KORE, "Intro line", None,
     1.0),
    (joke_media_operations.audio_voices.Voice.GEMINI_KORE, "Setup text", None,
     1.0),
    (joke_media_operations.audio_voices.Voice.GEMINI_PUCK, "what?", None, 1.0),
    (joke_media_operations.audio_voices.Voice.GEMINI_KORE,
     "Punchline text\n[giggles]", None, None),
  ]


def test_generate_joke_audio_returns_dialog_when_split_fails_and_allow_partial(
  monkeypatch,
  mock_cloud_storage,
):

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  dialog_wav_bytes = make_wav_bytes(array.array("h", [1000] * 100).tobytes())

  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.1,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=1.1,
        end_time_seconds=1.2,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=2.2,
        end_time_seconds=2.3,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=3.3,
        end_time_seconds=3.4,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("intro", 0.0, 0.1, char_timings=[]),
      audio_timing.WordTiming("setup", 1.1, 1.2, char_timings=[]),
      audio_timing.WordTiming("response", 2.2, 2.3, char_timings=[]),
      audio_timing.WordTiming("punchline", 3.3, 3.4, char_timings=[]),
    ],
  )

  generation_metadata = models.SingleGenerationMetadata(
    model_name="gemini-tts")
  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = (
    joke_media_operations.audio_client.AudioGenerationResult(
      gcs_uri="gs://temp/dialog.wav",
      metadata=generation_metadata,
      timing=timing,
    ))
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )

  monkeypatch.setattr(
    joke_media_operations,
    "_split_joke_dialog_wav_by_timing",
    Mock(side_effect=ValueError("split failed")),
  )

  mock_cloud_storage.download_bytes_from_gcs.return_value = dialog_wav_bytes
  dialog_uri = "gs://temp/dialog.wav"

  uploaded: list[tuple[str, bytes, str]] = []

  def record_upload(content_bytes: bytes, gcs_uri: str, content_type: str):
    uploaded.append((gcs_uri, content_bytes, content_type))
    return gcs_uri

  mock_cloud_storage.upload_bytes_to_gcs.side_effect = record_upload

  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup text",
    punchline_text="Punchline text",
  )

  result = joke_media_operations.generate_joke_audio(joke, allow_partial=True)

  assert result.dialog_gcs_uri == dialog_uri
  assert result.intro_gcs_uri is None
  assert result.setup_gcs_uri is None
  assert result.response_gcs_uri is None
  assert result.punchline_gcs_uri is None
  assert result.generation_metadata.generations == [generation_metadata]
  assert result.clip_timing is None
  assert uploaded == []


def test_generate_joke_audio_calls_forced_alignment_when_timing_is_missing(
    monkeypatch, mock_cloud_storage):

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  dialog_wav_bytes = make_wav_bytes(array.array("h", [500] * 200).tobytes())
  generation_metadata = models.SingleGenerationMetadata(
    model_name="elevenlabs")
  forced_alignment_metadata = models.SingleGenerationMetadata(
    model_name="elevenlabs",
    label="generate_joke_audio_forced_alignment",
    token_counts={
      "characters": 10,
    },
  )
  forced_timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.1,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.2,
        end_time_seconds=0.3,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=0.4,
        end_time_seconds=0.5,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.6,
        end_time_seconds=0.7,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("hey", 0.0, 0.1, char_timings=[]),
      audio_timing.WordTiming("setup", 0.2, 0.3, char_timings=[]),
      audio_timing.WordTiming("what", 0.4, 0.5, char_timings=[]),
      audio_timing.WordTiming("punchline", 0.6, 0.7, char_timings=[]),
    ],
  )

  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = (
    joke_media_operations.audio_client.AudioGenerationResult(
      gcs_uri="gs://temp/dialog.wav",
      metadata=generation_metadata,
      timing=None,
    ))
  mock_client.create_forced_alignment.return_value = (
    forced_timing, forced_alignment_metadata)
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )
  monkeypatch.setattr(
    joke_media_operations,
    "_split_joke_dialog_wav_by_timing",
    Mock(return_value=(
      [dialog_wav_bytes, dialog_wav_bytes, dialog_wav_bytes, dialog_wav_bytes],
      [
        [audio_timing.WordTiming("a", 0.0, 0.1, char_timings=[])],
        [audio_timing.WordTiming("b", 0.0, 0.1, char_timings=[])],
        [audio_timing.WordTiming("c", 0.0, 0.1, char_timings=[])],
        [audio_timing.WordTiming("d", 0.0, 0.1, char_timings=[])],
      ],
    )),
  )

  mock_cloud_storage.download_bytes_from_gcs.return_value = dialog_wav_bytes
  mock_cloud_storage.get_audio_gcs_uri.side_effect = [
    "gs://public/audio/intro.wav",
    "gs://public/audio/setup.wav",
    "gs://public/audio/response.wav",
    "gs://public/audio/punchline.wav",
  ]
  mock_cloud_storage.upload_bytes_to_gcs.side_effect = (
    lambda _bytes, gcs_uri, content_type=None: gcs_uri)

  joke = models.PunnyJoke(
    key="joke-force-align",
    setup_text="Setup text",
    punchline_text="Punchline text",
  )

  result = joke_media_operations.generate_joke_audio(joke)

  assert result.dialog_gcs_uri == "gs://temp/dialog.wav"
  mock_client.create_forced_alignment.assert_called_once()
  forced_call = mock_client.create_forced_alignment.call_args.kwargs
  assert forced_call["audio_bytes"] == dialog_wav_bytes
  assert len(forced_call["turns"]) == 4
  turn_scripts = [turn.script for turn in forced_call["turns"]]
  assert any("Setup text" in script for script in turn_scripts)
  assert any("Punchline text" in script for script in turn_scripts)
  assert result.generation_metadata.generations == [
    generation_metadata, forced_alignment_metadata
  ]


def test_generate_joke_audio_returns_partial_early_when_forced_alignment_fails(
    monkeypatch, mock_cloud_storage):
  dialog_wav_bytes = b"fake-wav"
  generation_metadata = models.SingleGenerationMetadata(
    model_name="elevenlabs")

  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = (
    joke_media_operations.audio_client.AudioGenerationResult(
      gcs_uri="gs://temp/dialog.wav",
      metadata=generation_metadata,
      timing=None,
    ))
  mock_client.create_forced_alignment.side_effect = ValueError(
    "forced alignment failed")
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )

  split_mock = Mock(side_effect=AssertionError("split should not run"))
  monkeypatch.setattr(
    joke_media_operations,
    "_split_joke_dialog_wav_by_timing",
    split_mock,
  )
  mock_cloud_storage.download_bytes_from_gcs.return_value = dialog_wav_bytes

  joke = models.PunnyJoke(
    key="joke-force-align-partial",
    setup_text="Setup text",
    punchline_text="Punchline text",
  )

  result = joke_media_operations.generate_joke_audio(joke, allow_partial=True)

  assert result.dialog_gcs_uri == "gs://temp/dialog.wav"
  assert result.intro_gcs_uri is None
  assert result.setup_gcs_uri is None
  assert result.response_gcs_uri is None
  assert result.punchline_gcs_uri is None
  assert result.clip_timing is None
  assert result.generation_metadata.generations == [generation_metadata]
  split_mock.assert_not_called()


def test_generate_joke_audio_raises_early_when_forced_alignment_fails(
    monkeypatch, mock_cloud_storage):
  generation_metadata = models.SingleGenerationMetadata(
    model_name="elevenlabs")

  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = (
    joke_media_operations.audio_client.AudioGenerationResult(
      gcs_uri="gs://temp/dialog.wav",
      metadata=generation_metadata,
      timing=None,
    ))
  mock_client.create_forced_alignment.side_effect = ValueError(
    "forced alignment failed")
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )
  mock_cloud_storage.download_bytes_from_gcs.return_value = b"fake-wav"

  joke = models.PunnyJoke(
    key="joke-force-align-error",
    setup_text="Setup text",
    punchline_text="Punchline text",
  )

  with pytest.raises(ValueError, match="Forced alignment fallback failed"):
    _ = joke_media_operations.generate_joke_audio(joke, allow_partial=False)


def test_get_joke_lip_sync_media_uses_cached_audio_when_enabled(monkeypatch):
  joke = models.PunnyJoke(
    key="joke-cache-enabled",
    setup_text="Setup",
    punchline_text="Punchline",
  )
  rendered_turns = [
    joke_media_operations.audio_client.DialogTurn(
      voice=joke_media_operations.audio_voices.Voice.GEMINI_LEDA,
      script="intro",
    )
  ]
  transcripts = joke_media_operations.JokeAudioTranscripts(
    intro="intro",
    setup="setup",
    response="response",
    punchline="punchline",
  )

  monkeypatch.setattr(
    joke_media_operations,
    "_render_dialog_turns_from_template",
    Mock(return_value=rendered_turns),
  )
  monkeypatch.setattr(
    joke_media_operations,
    "_resolve_clip_transcripts",
    Mock(return_value=transcripts),
  )

  def _sequence(transcript: str, gcs_uri: str):
    return joke_media_operations.PosableCharacterSequence(
      transcript=transcript,
      sequence_sound_events=[
        joke_media_operations.SequenceSoundEvent(
          start_time=0.0,
          end_time=1.0,
          gcs_uri=gcs_uri,
          volume=1.0,
        )
      ],
    )

  cached_sequences = {
    "intro": _sequence("intro", "gs://audio/intro.wav"),
    "setup": _sequence("setup", "gs://audio/setup.wav"),
    "response": _sequence("response", "gs://audio/response.wav"),
    "punchline": _sequence("punchline", "gs://audio/punchline.wav"),
  }
  load_cached_mock = Mock(return_value=cached_sequences)
  monkeypatch.setattr(
    joke_media_operations,
    "_load_cached_lip_sync_sequences",
    load_cached_mock,
  )
  generate_mock = Mock(side_effect=AssertionError(
    "_generate_joke_lip_sync_sequences should not run on cache hit"))
  monkeypatch.setattr(
    joke_media_operations,
    "_generate_joke_lip_sync_sequences",
    generate_mock,
  )

  result = joke_media_operations.get_joke_lip_sync_media(
    joke,
    use_audio_cache=True,
  )

  assert result.dialog_gcs_uri == ""
  assert result.intro_audio_gcs_uri == "gs://audio/intro.wav"
  assert result.setup_audio_gcs_uri == "gs://audio/setup.wav"
  assert result.response_audio_gcs_uri == "gs://audio/response.wav"
  assert result.punchline_audio_gcs_uri == "gs://audio/punchline.wav"
  assert result.audio_generation_metadata is None
  load_cached_mock.assert_called_once_with(joke_id="joke-cache-enabled",
                                           transcripts=transcripts)
  generate_mock.assert_not_called()


def test_get_joke_lip_sync_media_bypasses_cache_when_disabled(monkeypatch):
  joke = models.PunnyJoke(
    key="joke-cache-disabled",
    setup_text="Setup",
    punchline_text="Punchline",
  )
  rendered_turns = [
    joke_media_operations.audio_client.DialogTurn(
      voice=joke_media_operations.audio_voices.Voice.GEMINI_LEDA,
      script="intro",
    )
  ]
  transcripts = joke_media_operations.JokeAudioTranscripts(
    intro="intro",
    setup="setup",
    response="response",
    punchline="punchline",
  )

  monkeypatch.setattr(
    joke_media_operations,
    "_render_dialog_turns_from_template",
    Mock(return_value=rendered_turns),
  )
  monkeypatch.setattr(
    joke_media_operations,
    "_resolve_clip_transcripts",
    Mock(return_value=transcripts),
  )

  load_cached_mock = Mock(return_value={"unused": None})
  monkeypatch.setattr(
    joke_media_operations,
    "_load_cached_lip_sync_sequences",
    load_cached_mock,
  )

  generated = joke_media_operations.JokeLipSyncResult(
    dialog_gcs_uri="gs://audio/dialog.wav",
    intro_audio_gcs_uri="gs://audio/intro.wav",
    setup_audio_gcs_uri="gs://audio/setup.wav",
    response_audio_gcs_uri="gs://audio/response.wav",
    punchline_audio_gcs_uri="gs://audio/punchline.wav",
    transcripts=transcripts,
    intro_sequence=None,
    setup_sequence=None,
    response_sequence=None,
    punchline_sequence=None,
    audio_generation_metadata=None,
  )
  generate_mock = Mock(return_value=generated)
  monkeypatch.setattr(
    joke_media_operations,
    "_generate_joke_lip_sync_sequences",
    generate_mock,
  )

  result = joke_media_operations.get_joke_lip_sync_media(
    joke,
    use_audio_cache=False,
  )

  assert result == generated
  load_cached_mock.assert_not_called()
  generate_mock.assert_called_once_with(
    joke=joke,
    temp_output=False,
    script_template=rendered_turns,
    audio_model=None,
    allow_partial=False,
    transcripts=transcripts,
  )


def test_generate_joke_video_builds_timeline(monkeypatch, mock_cloud_storage,
                                             mock_firestore):
  joke = models.PunnyJoke(
    key="joke-42",
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )

  audio_metadata = models.SingleGenerationMetadata(model_name="audio-model")
  video_metadata = models.SingleGenerationMetadata(model_name="video-model")
  monkeypatch.setattr(
    joke_media_operations,
    "get_joke_lip_sync_media",
    Mock(return_value=joke_media_operations.JokeLipSyncResult(
      dialog_gcs_uri="gs://audio/dialog.wav",
      intro_audio_gcs_uri="gs://audio/intro.wav",
      setup_audio_gcs_uri="gs://audio/setup.wav",
      response_audio_gcs_uri="gs://audio/response.wav",
      punchline_audio_gcs_uri="gs://audio/punchline.wav",
      transcripts=joke_media_operations.JokeAudioTranscripts(
        intro="intro",
        setup="setup",
        response="response",
        punchline="punchline",
      ),
      intro_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/intro.wav",
        transcript="intro",
        timing=None,
      ),
      setup_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/setup.wav",
        transcript="setup",
        timing=None,
      ),
      response_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/response.wav",
        transcript="response",
        timing=None,
      ),
      punchline_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/punchline.wav",
        transcript="punchline",
        timing=None,
      ),
      audio_generation_metadata=audio_metadata,
    )),
  )

  create_video_mock = Mock(return_value=("gs://videos/joke.mp4",
                                         video_metadata))
  monkeypatch.setattr(
    joke_media_operations.gen_video,
    "create_portrait_character_video",
    create_video_mock,
  )

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://images/setup.png",
    "gs://images/punchline.png",
  ]
  result = joke_media_operations.generate_joke_video(
    joke,
    teller_character_def_id="char-teller",
    listener_character_def_id="char-listener",
  )

  assert result.video_gcs_uri == "gs://videos/joke.mp4"
  assert [
    gen.model_name for gen in result.video_generation_metadata.generations
  ] == [
    "audio-model",
    "video-model",
  ]

  create_video_mock.assert_called_once()
  call_kwargs = create_video_mock.call_args.kwargs
  assert call_kwargs["setup_image_gcs_uri"] == "gs://images/setup.png"
  assert call_kwargs["punchline_image_gcs_uri"] == "gs://images/punchline.png"
  assert isinstance(call_kwargs["teller_character"],
                    joke_media_operations.PosableCharacter)
  assert isinstance(call_kwargs["listener_character"],
                    joke_media_operations.PosableCharacter)
  assert call_kwargs["teller_character"].definition.key == "char-teller"
  assert call_kwargs["listener_character"].definition.key == "char-listener"
  assert call_kwargs[
    "teller_voice"] == joke_media_operations.DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE
  assert call_kwargs[
    "listener_voice"] == joke_media_operations.DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE
  assert call_kwargs["output_filename_base"] == "joke_video_joke-42"
  assert call_kwargs["temp_output"] is False
  assert mock_firestore.get_posable_character_def.call_count == 2
  mock_firestore.get_posable_character_def.assert_any_call("char-teller")
  mock_firestore.get_posable_character_def.assert_any_call("char-listener")


def test_generate_joke_video_splits_intro_and_setup_when_timing_available(
  monkeypatch,
  mock_cloud_storage,
  mock_firestore,
):

  joke = models.PunnyJoke(
    key="joke-42",
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )

  audio_metadata = models.SingleGenerationMetadata(model_name="audio-model")
  video_metadata = models.SingleGenerationMetadata(model_name="video-model")
  monkeypatch.setattr(
    joke_media_operations, "get_joke_lip_sync_media",
    Mock(return_value=joke_media_operations.JokeLipSyncResult(
      dialog_gcs_uri="gs://audio/dialog.wav",
      intro_audio_gcs_uri="gs://audio/intro.wav",
      setup_audio_gcs_uri="gs://audio/setup.wav",
      response_audio_gcs_uri="gs://audio/response.wav",
      punchline_audio_gcs_uri="gs://audio/punchline.wav",
      transcripts=joke_media_operations.JokeAudioTranscripts(
        intro="intro",
        setup="setup",
        response="response",
        punchline="punchline",
      ),
      intro_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/intro.wav", transcript="intro", timing=None),
      setup_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/setup.wav", transcript="setup", timing=None),
      response_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/response.wav",
        transcript="response",
        timing=None),
      punchline_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/punchline.wav",
        transcript="punchline",
        timing=None),
      audio_generation_metadata=audio_metadata,
    )))

  create_video_mock = Mock(return_value=("gs://videos/joke.mp4",
                                         video_metadata))
  monkeypatch.setattr(
    joke_media_operations.gen_video,
    "create_portrait_character_video",
    create_video_mock,
  )

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://images/setup.png",
    "gs://images/punchline.png",
  ]
  result = joke_media_operations.generate_joke_video(
    joke,
    teller_character_def_id="char-teller",
    listener_character_def_id="char-listener",
  )

  assert result.video_gcs_uri == "gs://videos/joke.mp4"
  assert [
    gen.model_name for gen in result.video_generation_metadata.generations
  ] == [
    "audio-model",
    "video-model",
  ]

  create_video_mock.assert_called_once()
  call_kwargs = create_video_mock.call_args.kwargs
  assert call_kwargs["intro_sequence"] is not None
  assert call_kwargs["response_sequence"] is not None
  assert call_kwargs[
    "teller_voice"] == joke_media_operations.DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE
  assert call_kwargs[
    "listener_voice"] == joke_media_operations.DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE
  assert call_kwargs["output_filename_base"] == "joke_video_joke-42"
  assert mock_firestore.get_posable_character_def.call_count == 2
  mock_firestore.get_posable_character_def.assert_any_call("char-teller")
  mock_firestore.get_posable_character_def.assert_any_call("char-listener")


def test_generate_joke_video_requires_images():
  joke = models.PunnyJoke(
    setup_text="Setup",
    punchline_text="Punchline",
  )

  with pytest.raises(ValueError, match="setup and punchline images"):
    joke_media_operations.generate_joke_video(
      joke,
      teller_character_def_id="char-teller",
      listener_character_def_id="char-listener",
    )


def test_generate_joke_video_requires_teller_character_id(mock_cloud_storage):
  joke = models.PunnyJoke(
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )
  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://images/setup.png",
    "gs://images/punchline.png",
  ]

  with pytest.raises(ValueError,
                     match="Teller character definition ID is required"):
    joke_media_operations.generate_joke_video(
      joke,
      teller_character_def_id="",
      listener_character_def_id="char-listener",
    )


def test_generate_joke_video_requires_listener_character_when_response_present(
  monkeypatch,
  mock_cloud_storage,
  mock_firestore,
):
  joke = models.PunnyJoke(
    key="joke-listener-required",
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )

  monkeypatch.setattr(
    joke_media_operations,
    "get_joke_lip_sync_media",
    Mock(return_value=joke_media_operations.JokeLipSyncResult(
      dialog_gcs_uri="gs://audio/dialog.wav",
      intro_audio_gcs_uri=None,
      setup_audio_gcs_uri="gs://audio/setup.wav",
      response_audio_gcs_uri="gs://audio/response.wav",
      punchline_audio_gcs_uri="gs://audio/punchline.wav",
      transcripts=joke_media_operations.JokeAudioTranscripts(
        intro="intro",
        setup="setup",
        response="response",
        punchline="punchline",
      ),
      intro_sequence=None,
      setup_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/setup.wav",
        transcript="setup",
        timing=None,
      ),
      response_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/response.wav",
        transcript="response",
        timing=None,
      ),
      punchline_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/punchline.wav",
        transcript="punchline",
        timing=None,
      ),
      audio_generation_metadata=models.SingleGenerationMetadata(
        model_name="audio-model"),
    )),
  )

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://images/setup.png",
    "gs://images/punchline.png",
  ]

  with pytest.raises(ValueError,
                     match="Listener character definition ID is required"):
    joke_media_operations.generate_joke_video(
      joke,
      teller_character_def_id="char-teller",
      listener_character_def_id=None,
    )


def test_generate_joke_video_allows_missing_listener_character_when_no_response(
  monkeypatch,
  mock_cloud_storage,
  mock_firestore,
):
  joke = models.PunnyJoke(
    key="joke-no-listener-needed",
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )

  monkeypatch.setattr(
    joke_media_operations,
    "get_joke_lip_sync_media",
    Mock(return_value=joke_media_operations.JokeLipSyncResult(
      dialog_gcs_uri="gs://audio/dialog.wav",
      intro_audio_gcs_uri=None,
      setup_audio_gcs_uri="gs://audio/setup.wav",
      response_audio_gcs_uri=None,
      punchline_audio_gcs_uri="gs://audio/punchline.wav",
      transcripts=joke_media_operations.JokeAudioTranscripts(
        intro="intro",
        setup="setup",
        response="response",
        punchline="punchline",
      ),
      intro_sequence=None,
      setup_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/setup.wav",
        transcript="setup",
        timing=None,
      ),
      response_sequence=None,
      punchline_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/punchline.wav",
        transcript="punchline",
        timing=None,
      ),
      audio_generation_metadata=models.SingleGenerationMetadata(
        model_name="audio-model"),
    )),
  )

  video_metadata = models.SingleGenerationMetadata(model_name="video-model")
  create_video_mock = Mock(return_value=("gs://videos/joke.mp4",
                                         video_metadata))
  monkeypatch.setattr(
    joke_media_operations.gen_video,
    "create_portrait_character_video",
    create_video_mock,
  )

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://images/setup.png",
    "gs://images/punchline.png",
  ]

  result = joke_media_operations.generate_joke_video(
    joke,
    teller_character_def_id="char-teller",
    listener_character_def_id=None,
  )

  assert result.video_gcs_uri == "gs://videos/joke.mp4"
  create_video_mock.assert_called_once()
  call_kwargs = create_video_mock.call_args.kwargs
  assert call_kwargs["listener_character"] is None
  assert call_kwargs["listener_voice"] is None
  assert mock_firestore.get_posable_character_def.call_count == 1
  mock_firestore.get_posable_character_def.assert_called_once_with(
    "char-teller")


def test_generate_joke_video_raises_when_character_def_not_found(
  monkeypatch,
  mock_cloud_storage,
  mock_firestore,
):
  joke = models.PunnyJoke(
    key="joke-404",
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )

  monkeypatch.setattr(
    joke_media_operations,
    "get_joke_lip_sync_media",
    Mock(return_value=joke_media_operations.JokeLipSyncResult(
      dialog_gcs_uri="gs://audio/dialog.wav",
      intro_audio_gcs_uri=None,
      setup_audio_gcs_uri="gs://audio/setup.wav",
      response_audio_gcs_uri=None,
      punchline_audio_gcs_uri="gs://audio/punchline.wav",
      transcripts=joke_media_operations.JokeAudioTranscripts(
        intro="intro",
        setup="setup",
        response="response",
        punchline="punchline",
      ),
      intro_sequence=None,
      setup_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/setup.wav",
        transcript="setup",
        timing=None,
      ),
      response_sequence=None,
      punchline_sequence=joke_media_operations._build_lipsync_sequence(
        audio_gcs_uri="gs://audio/punchline.wav",
        transcript="punchline",
        timing=None,
      ),
      audio_generation_metadata=models.SingleGenerationMetadata(
        model_name="audio-model"),
    )),
  )

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://images/setup.png",
    "gs://images/punchline.png",
  ]

  def get_character_def(character_def_id: str):
    if character_def_id == "missing-char":
      return None
    return models.PosableCharacterDef(
      key=character_def_id,
      width=1,
      height=1,
    )

  mock_firestore.get_posable_character_def.side_effect = get_character_def

  with pytest.raises(ValueError,
                     match="Teller posable character definition not found"):
    joke_media_operations.generate_joke_video(
      joke,
      teller_character_def_id="missing-char",
      listener_character_def_id="char-listener",
    )


def test_generate_joke_audio_uses_scan_and_split_with_timing(
  monkeypatch,
  mock_cloud_storage,
):
  """Verify that scan-and-split is used when timing is present."""

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  sr = 24000

  def _tone(dur):
    return array.array("h", [1000] * int(sr * dur)).tobytes()

  def _sil(dur):
    return array.array("h", [0] * int(sr * dur)).tobytes()

  wav_frames = (_tone(0.3) + _sil(1.0) + _tone(0.5) + _sil(1.0) + _tone(0.5) +
                _sil(1.0) + _tone(0.5))
  wav_bytes = make_wav_bytes(wav_frames, rate=sr)

  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.3,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=1.3,
        end_time_seconds=1.8,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=2.8,
        end_time_seconds=3.3,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=4.3,
        end_time_seconds=4.8,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("intro", 0.0, 0.3, char_timings=[]),
      audio_timing.WordTiming("setup", 1.3, 1.8, char_timings=[]),
      audio_timing.WordTiming("response", 2.8, 3.3, char_timings=[]),
      audio_timing.WordTiming("punchline", 4.3, 4.8, char_timings=[]),
    ],
  )

  mock_result = Mock()
  mock_result.gcs_uri = "gs://temp/dialog.wav"
  mock_result.metadata = models.SingleGenerationMetadata()
  mock_result.timing = timing

  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = mock_result
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )

  mock_cloud_storage.download_bytes_from_gcs.return_value = wav_bytes
  mock_cloud_storage.get_audio_gcs_uri.side_effect = (
    lambda x, y, temp=False: f"gs://{x}.{y}")
  mock_cloud_storage.upload_bytes_to_gcs.return_value = None

  joke = models.PunnyJoke(key="j1", setup_text="s", punchline_text="p")
  result = joke_media_operations.generate_joke_audio(joke)

  assert result.clip_timing.intro[0].start_time == pytest.approx(0.0, abs=0.1)
  assert result.clip_timing.setup[0].start_time == pytest.approx(0.0, abs=0.1)
  assert result.clip_timing.response[0].start_time == pytest.approx(0.0,
                                                                    abs=0.1)
  assert result.clip_timing.punchline[0].start_time == pytest.approx(1.0,
                                                                     abs=0.1)


def test_split_joke_dialog_wav_by_timing_returns_one_clip_per_voice_segment():

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  sr = 24000

  def _tone(sec: float, amp: int = 1000) -> bytes:
    return array.array("h", [amp] * int(sr * sec)).tobytes()

  def _sil(sec: float) -> bytes:
    return array.array("h", [0] * int(sr * sec)).tobytes()

  wav_bytes = make_wav_bytes(
    _tone(0.20) + _sil(0.25) + _tone(0.15) + _sil(0.25) + _tone(0.10),
    rate=sr,
  )
  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.2,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.45,
        end_time_seconds=0.60,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=0.85,
        end_time_seconds=0.95,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("one", 0.0, 0.2, char_timings=[]),
      audio_timing.WordTiming("two", 0.45, 0.60, char_timings=[]),
      audio_timing.WordTiming("three", 0.85, 0.95, char_timings=[]),
    ],
  )

  split_wavs, split_timing = (
    joke_media_operations._split_joke_dialog_wav_by_timing(
      wav_bytes,
      timing,
    ))

  assert len(split_wavs) == len(timing.voice_segments)
  assert len(split_timing) == len(timing.voice_segments)
  assert all(chunk[:4] == b"RIFF" for chunk in split_wavs)
  assert split_timing[0][0].start_time == pytest.approx(0.0, abs=0.1)
  assert split_timing[1][0].start_time == pytest.approx(0.2, abs=0.1)
  assert split_timing[2][0].start_time == pytest.approx(0.4, abs=0.1)


def test_split_joke_dialog_wav_by_timing_does_not_group_by_dialogue_input_index(
):

  def make_wav_bytes(frames: bytes, *, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(rate)
      wf.writeframes(frames)
      # pylint: enable=no-member
    return buffer.getvalue()

  sr = 24000

  def _tone(sec: float, amp: int = 1200) -> bytes:
    return array.array("h", [amp] * int(sr * sec)).tobytes()

  def _sil(sec: float) -> bytes:
    return array.array("h", [0] * int(sr * sec)).tobytes()

  wav_bytes = make_wav_bytes(
    _tone(0.12) + _sil(0.20) + _tone(0.12) + _sil(0.20) + _tone(0.12) +
    _sil(0.20) + _tone(0.12),
    rate=sr,
  )
  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.12,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.32,
        end_time_seconds=0.44,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=0.64,
        end_time_seconds=0.76,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=0.96,
        end_time_seconds=1.08,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=1,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("a", 0.0, 0.12, char_timings=[]),
      audio_timing.WordTiming("b", 0.32, 0.44, char_timings=[]),
      audio_timing.WordTiming("c", 0.64, 0.76, char_timings=[]),
      audio_timing.WordTiming("d", 0.96, 1.08, char_timings=[]),
    ],
  )

  split_wavs, split_timing = (
    joke_media_operations._split_joke_dialog_wav_by_timing(
      wav_bytes,
      timing,
    ))

  assert len(split_wavs) == len(timing.voice_segments)
  assert [words[0].word for words in split_timing] == ["a", "b", "c", "d"]


def test_split_joke_dialog_wav_by_timing_rejects_collapsed_word_windows(
  monkeypatch, ):
  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=1.5,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=1.5,
        end_time_seconds=3.0,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=3.0,
        end_time_seconds=3.8,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=3.8,
        end_time_seconds=8.9,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming("Hey", 0.2, 1.4, char_timings=[]),
      audio_timing.WordTiming("WhatdoyoucallasmallValentinesDaycard",
                              1.518,
                              1.518,
                              char_timings=[]),
      audio_timing.WordTiming("what", 3.0, 3.75, char_timings=[]),
      audio_timing.WordTiming("AValentiny", 4.0, 8.9, char_timings=[]),
    ],
  )
  monkeypatch.setattr(
    joke_media_operations.audio_operations,
    "split_audio",
    lambda wav_bytes, estimated_cut_points, trim=True: [  # noqa: ARG005
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"seg1",
        offset_sec=0.0,
      ),
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"seg2",
        offset_sec=1.5,
      ),
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"seg3",
        offset_sec=3.0,
      ),
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"seg4",
        offset_sec=3.8,
      ),
    ],
  )

  with pytest.raises(ValueError,
                     match="no positive-duration spoken word timing"):
    _ = joke_media_operations._split_joke_dialog_wav_by_timing(  # pylint: disable=protected-access
      b"fake-wav",
      timing,
    )


def test_generate_joke_audio_clamps_negative_shifted_word_timing(
  monkeypatch,
  mock_cloud_storage,
):
  """Clip-local timing is clamped to non-negative after split/trim offsets."""
  timing = audio_timing.TtsTiming(
    voice_segments=[
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.0,
        end_time_seconds=0.2,
        word_start_index=0,
        word_end_index=1,
        dialogue_input_index=0,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=0.6,
        end_time_seconds=1.2,
        word_start_index=1,
        word_end_index=2,
        dialogue_input_index=1,
      ),
      audio_timing.VoiceSegment(
        voice_id="v2",
        start_time_seconds=1.8,
        end_time_seconds=2.3,
        word_start_index=2,
        word_end_index=3,
        dialogue_input_index=2,
      ),
      audio_timing.VoiceSegment(
        voice_id="v1",
        start_time_seconds=2.8,
        end_time_seconds=3.3,
        word_start_index=3,
        word_end_index=4,
        dialogue_input_index=3,
      ),
    ],
    normalized_alignment=[
      audio_timing.WordTiming(
        "intro",
        0.0,
        0.2,
        char_timings=[],
      ),
      audio_timing.WordTiming(
        "setup",
        0.7,
        1.0,
        char_timings=[
          audio_timing.CharTiming("s", 0.72, 0.78),
        ],
      ),
      audio_timing.WordTiming(
        "response",
        1.9,
        2.1,
        char_timings=[],
      ),
      audio_timing.WordTiming(
        "punchline",
        2.9,
        3.2,
        char_timings=[],
      ),
    ],
  )

  mock_result = Mock()
  mock_result.gcs_uri = "gs://temp/dialog.wav"
  mock_result.metadata = models.SingleGenerationMetadata()
  mock_result.timing = timing

  mock_client = Mock()
  mock_client.generate_multi_turn_dialog.return_value = mock_result
  monkeypatch.setattr(
    joke_media_operations.audio_client,
    "get_audio_client",
    Mock(return_value=mock_client),
  )

  monkeypatch.setattr(
    joke_media_operations.audio_operations,
    "split_audio",
    Mock(return_value=[
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"intro",
        offset_sec=0.0,
      ),
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"setup",
        offset_sec=0.8,
      ),
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"response",
        offset_sec=1.8,
      ),
      joke_media_operations.audio_operations.SplitAudioSegment(
        wav_bytes=b"punchline",
        offset_sec=2.8,
      ),
    ]),
  )

  mock_cloud_storage.download_bytes_from_gcs.return_value = b"dialog"
  mock_cloud_storage.get_audio_gcs_uri.side_effect = (
    lambda x, y, temp=False: f"gs://{x}.{y}")
  mock_cloud_storage.upload_bytes_to_gcs.return_value = None

  joke = models.PunnyJoke(key="j1", setup_text="s", punchline_text="p")
  result = joke_media_operations.generate_joke_audio(joke)

  assert result.clip_timing is not None
  assert result.clip_timing.setup[0].start_time == 0.0
  assert result.clip_timing.setup[0].end_time >= 0.0
  assert result.clip_timing.setup[0].char_timings[0].start_time == 0.0


def test_build_lipsync_sequence_uses_actual_audio_duration(
  monkeypatch,
  mock_cloud_storage,
):

  def _make_wav_bytes(duration_sec: float, sr: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
      # pylint: disable=no-member
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(sr)
      wf.writeframes(
        array.array("h", [1000] * int(sr * duration_sec)).tobytes())
      # pylint: enable=no-member
    return buffer.getvalue()

  mock_cloud_storage.download_bytes_from_gcs.return_value = _make_wav_bytes(
    0.5)
  monkeypatch.setattr(
    joke_media_operations.mouth_event_detection,
    "detect_mouth_events",
    Mock(return_value=[]),
  )

  sequence = joke_media_operations._build_lipsync_sequence(
    audio_gcs_uri="gs://audio/setup.wav",
    transcript="Setup",
    timing=[audio_timing.WordTiming("setup", 0.0, 0.2, char_timings=[])],
  )

  assert sequence.sequence_sound_events[0].end_time == pytest.approx(0.5,
                                                                     abs=0.01)


def test_build_lipsync_sequence_falls_back_to_timing_duration_when_audio_read_fails(
  monkeypatch,
  mock_cloud_storage,
):
  mock_cloud_storage.download_bytes_from_gcs.side_effect = ValueError(
    "missing")
  monkeypatch.setattr(
    joke_media_operations.mouth_event_detection,
    "detect_mouth_events",
    Mock(return_value=[]),
  )

  sequence = joke_media_operations._build_lipsync_sequence(
    audio_gcs_uri="gs://audio/setup.wav",
    transcript="Setup",
    timing=[audio_timing.WordTiming("setup", 0.0, 0.33, char_timings=[])],
  )

  assert sequence.sequence_sound_events[0].end_time == pytest.approx(0.33,
                                                                     abs=0.001)


def test_build_lipsync_sequence_adds_subtitle_event_without_stage_directions(
  monkeypatch,
  mock_cloud_storage,
):
  mock_cloud_storage.download_bytes_from_gcs.return_value = b"not-used"
  monkeypatch.setattr(
    joke_media_operations,
    "_resolve_sound_event_end_time_sec",
    Mock(return_value=0.42),
  )
  monkeypatch.setattr(
    joke_media_operations.mouth_event_detection,
    "detect_mouth_events",
    Mock(return_value=[]),
  )

  sequence = joke_media_operations._build_lipsync_sequence(
    audio_gcs_uri="gs://audio/setup.wav",
    transcript="[playfully] Hey! want to hear a joke?",
    timing=[audio_timing.WordTiming("hey", 0.0, 0.2, char_timings=[])],
  )

  assert len(sequence.sequence_subtitle_events) == 1
  subtitle_event = sequence.sequence_subtitle_events[0]
  assert subtitle_event.start_time == pytest.approx(0.0)
  assert subtitle_event.end_time == pytest.approx(0.42)
  assert subtitle_event.text == "Hey! want to hear a joke?"


def _make_laugh_wav_bytes(
  *,
  duration_sec: float,
  sample_rate: int = 24000,
  pulses: list[tuple[float, float, int]],
) -> bytes:
  buffer = io.BytesIO()
  total_samples = int(round(float(duration_sec) * float(sample_rate)))
  samples = [0] * max(1, total_samples)
  for start_sec, end_sec, amplitude in pulses:
    start_idx = max(0, int(round(float(start_sec) * float(sample_rate))))
    end_idx = min(total_samples,
                  int(round(float(end_sec) * float(sample_rate))))
    for idx in range(start_idx, end_idx):
      samples[idx] = int(amplitude) if idx % 2 == 0 else -int(amplitude)
  with wave.open(buffer, "wb") as wf:
    # pylint: disable=no-member
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(array.array("h", samples).tobytes())
    # pylint: enable=no-member
  return buffer.getvalue()


def test_build_laugh_sequence_sets_static_face_tracks(mock_cloud_storage):
  wav_bytes = _make_laugh_wav_bytes(
    duration_sec=1.8,
    pulses=[
      (0.45, 0.52, 28000),
      (0.78, 0.85, 23000),
      (1.12, 1.19, 18000),
    ],
  )
  mock_cloud_storage.download_bytes_from_gcs.return_value = wav_bytes

  sequence = joke_media_operations.build_laugh_sequence("gs://audio/laugh.wav")
  duration_sec = joke_media_operations.audio_operations.get_wav_duration_sec(
    wav_bytes)

  assert len(sequence.sequence_sound_events) == 1
  assert sequence.sequence_sound_events[0].start_time == pytest.approx(0.0)
  assert sequence.sequence_sound_events[0].end_time == pytest.approx(
    duration_sec, abs=0.001)
  assert sequence.sequence_sound_events[0].gcs_uri == "gs://audio/laugh.wav"

  assert len(sequence.sequence_left_eye_open) == 1
  assert sequence.sequence_left_eye_open[0].value is False
  assert sequence.sequence_left_eye_open[0].start_time == pytest.approx(0.0)
  assert sequence.sequence_left_eye_open[0].end_time == pytest.approx(
    duration_sec, abs=0.001)

  assert len(sequence.sequence_right_eye_open) == 1
  assert sequence.sequence_right_eye_open[0].value is False
  assert sequence.sequence_right_eye_open[0].start_time == pytest.approx(0.0)
  assert sequence.sequence_right_eye_open[0].end_time == pytest.approx(
    duration_sec, abs=0.001)

  assert len(sequence.sequence_mouth_state) == 1
  assert sequence.sequence_mouth_state[0].mouth_state.value == "OPEN"
  assert sequence.sequence_mouth_state[0].start_time == pytest.approx(0.0)
  assert sequence.sequence_mouth_state[0].end_time == pytest.approx(
    duration_sec, abs=0.001)


def test_build_laugh_sequence_keeps_head_at_zero_during_initial_and_trailing_silence(
  mock_cloud_storage, ):
  wav_bytes = _make_laugh_wav_bytes(
    duration_sec=2.2,
    pulses=[
      (0.54, 0.60, 26000),
      (0.84, 0.90, 22000),
      (1.14, 1.20, 18000),
    ],
  )
  mock_cloud_storage.download_bytes_from_gcs.return_value = wav_bytes

  sequence = joke_media_operations.build_laugh_sequence("gs://audio/laugh.wav")
  animator = CharacterAnimator(sequence)

  initial_pose = animator.sample_pose(0.15)
  trailing_pose = animator.sample_pose(2.0)
  assert initial_pose.head_transform.translate_y == pytest.approx(0.0, abs=0.2)
  assert trailing_pose.head_transform.translate_y == pytest.approx(0.0,
                                                                   abs=0.2)
  assert initial_pose.left_eye_open is False
  assert trailing_pose.left_eye_open is False
  assert initial_pose.right_eye_open is False
  assert trailing_pose.right_eye_open is False
  assert initial_pose.mouth_state.value == "OPEN"
  assert trailing_pose.mouth_state.value == "OPEN"


def test_build_laugh_sequence_hits_peaks_and_midpoints(mock_cloud_storage):
  laugh_translate_y = 12
  wav_bytes = _make_laugh_wav_bytes(
    duration_sec=1.9,
    pulses=[
      (0.50, 0.56, 29000),
      (0.90, 0.96, 26000),
      (1.30, 1.36, 23000),
    ],
  )
  mock_cloud_storage.download_bytes_from_gcs.return_value = wav_bytes

  sequence = joke_media_operations.build_laugh_sequence(
    "gs://audio/laugh.wav",
    laugh_translate_y=laugh_translate_y,
  )
  animator = CharacterAnimator(sequence)

  assert animator.sample_pose(0.53).head_transform.translate_y > 7.5
  assert animator.sample_pose(0.93).head_transform.translate_y > 7.5
  assert animator.sample_pose(1.33).head_transform.translate_y > 7.5

  assert animator.sample_pose(
    0.73).head_transform.translate_y == pytest.approx(0.0, abs=1.5)
  assert animator.sample_pose(
    1.13).head_transform.translate_y == pytest.approx(0.0, abs=1.5)


def test_build_laugh_sequence_detects_variable_amplitude_peaks(
    mock_cloud_storage):
  laugh_translate_y = 11
  wav_bytes = _make_laugh_wav_bytes(
    duration_sec=2.2,
    pulses=[
      (0.38, 0.44, 31000),
      (0.66, 0.72, 14000),
      (0.94, 1.00, 24000),
      (1.22, 1.28, 10000),
      (1.50, 1.56, 7000),
    ],
  )
  mock_cloud_storage.download_bytes_from_gcs.return_value = wav_bytes

  sequence = joke_media_operations.build_laugh_sequence(
    "gs://audio/laugh.wav",
    laugh_translate_y=laugh_translate_y,
  )

  peak_target_events = [
    event for event in sequence.sequence_head_transform if abs(
      float(event.target_transform.translate_y) -
      float(laugh_translate_y)) < 1e-6
  ]
  assert len(peak_target_events) == 5

  animator = CharacterAnimator(sequence)
  peak_sample_times = [0.41, 0.69, 0.97, 1.25, 1.53]
  for sample_time in peak_sample_times:
    assert animator.sample_pose(sample_time).head_transform.translate_y > 4.0


def test_build_laugh_sequence_raises_for_invalid_wav(mock_cloud_storage):
  mock_cloud_storage.download_bytes_from_gcs.return_value = b"not-a-wav"

  with pytest.raises(ValueError, match="decode WAV"):
    _ = joke_media_operations.build_laugh_sequence("gs://audio/bad.wav")
