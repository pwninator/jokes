import base64
import io
import wave
from unittest.mock import MagicMock, patch

import pytest
from common import audio_timing
from services import audio_client, gen_audio


class _InlineData:

  def __init__(self, data: bytes):
    self.data = data


class _Part:

  def __init__(self, data: bytes):
    self.inline_data = _InlineData(data)


class _Content:

  def __init__(self, parts):
    self.parts = parts


class _Candidate:

  def __init__(self, content):
    self.content = content


class _Response:

  def __init__(self, candidates, usage_metadata=None):
    self.candidates = candidates
    self.usage_metadata = usage_metadata


class _UsageMetadata:

  def __init__(self, prompt_token_count, cached_content_token_count,
               candidates_token_count):
    self.prompt_token_count = prompt_token_count
    self.cached_content_token_count = cached_content_token_count
    self.candidates_token_count = candidates_token_count


class _FakeModels:

  def __init__(self, response):
    self._response = response
    self.generate_content_calls = []

  def generate_content(self, **kwargs):
    self.generate_content_calls.append(kwargs)
    return self._response


class _FakeClient:

  def __init__(self, response):
    self.models = _FakeModels(response)


def test_generate_multi_turn_dialog_stitches_turns_and_uploads_wav_bytes():
  pcm_bytes = b"\x00\x01" * 200
  usage_metadata = _UsageMetadata(
    prompt_token_count=100,
    cached_content_token_count=0,
    candidates_token_count=3200,
  )
  response = _Response([_Candidate(_Content([_Part(pcm_bytes)]))],
                       usage_metadata=usage_metadata)
  fake_client = _FakeClient(response)

  upload_mock = MagicMock()

  client = audio_client.GeminiAudioClient(
    label="test",
    model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False), \
      patch.object(audio_client.config, "get_gemini_api_key",
                   return_value="fake-key"), \
      patch.object(audio_client.genai,
                   "Client",
                   return_value=fake_client), \
      patch.object(audio_client.cloud_storage,
                   "get_audio_gcs_uri",
                   return_value="gs://gen_audio/out.wav"), \
      patch.object(audio_client.cloud_storage,
                   "upload_bytes_to_gcs",
                   upload_mock):
    result = client.generate_multi_turn_dialog(
      turns=[
        audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_PUCK,
                                script="Hello\n\nthere"),
        audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_KORE,
                                script="Hi"),
        audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_PUCK,
                                script="Ok"),
      ],
      output_filename_base="out",
    )

  assert result.gcs_uri == "gs://gen_audio/out.wav"
  assert result.timing is None
  assert result.metadata.token_counts["characters"] > 0
  assert result.metadata.token_counts["prompt_tokens"] == 100
  assert result.metadata.token_counts["output_tokens"] == 3200

  assert result.metadata.model_name == audio_client.AudioModel.GEMINI_2_5_FLASH_TTS.value
  assert result.metadata.cost is not None
  assert result.metadata.cost > 0.0

  assert upload_mock.call_count == 1
  uploaded_bytes = upload_mock.call_args.args[0]
  uploaded_uri = upload_mock.call_args.args[1]
  uploaded_content_type = upload_mock.call_args.kwargs["content_type"]

  assert uploaded_uri == "gs://gen_audio/out.wav"
  assert uploaded_content_type == "audio/wav"
  assert uploaded_bytes[:4] == b"RIFF"
  assert b"WAVE" in uploaded_bytes[:64]

  assert fake_client.models.generate_content_calls
  call = fake_client.models.generate_content_calls[0]
  assert call["model"] == audio_client.AudioModel.GEMINI_2_5_FLASH_TTS.value
  assert call["contents"] == "Alex: Hello\nAlex: there\nSam: Hi\nAlex: Ok"
  response_modalities = getattr(call["config"], "response_modalities",
                                None) or []
  assert "AUDIO" in response_modalities


def test_generate_multi_turn_dialog_includes_pause_markers():
  pcm_bytes = b"\x00\x01" * 20
  usage_metadata = _UsageMetadata(
    prompt_token_count=10,
    cached_content_token_count=0,
    candidates_token_count=20,
  )
  response = _Response([_Candidate(_Content([_Part(pcm_bytes)]))],
                       usage_metadata=usage_metadata)
  fake_client = _FakeClient(response)

  client = audio_client.GeminiAudioClient(
    label="test",
    model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False), \
      patch.object(audio_client.config, "get_gemini_api_key",
                   return_value="fake-key"), \
      patch.object(audio_client.genai,
                   "Client",
                   return_value=fake_client), \
      patch.object(audio_client.cloud_storage,
                   "get_audio_gcs_uri",
                   return_value="gs://gen_audio/out.wav"), \
      patch.object(audio_client.cloud_storage,
                   "upload_bytes_to_gcs",
                   MagicMock()):
    _ = client.generate_multi_turn_dialog(
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.GEMINI_PUCK,
          script="Hello",
          pause_sec_before=1,
          pause_sec_after=0.5,
        ),
      ],
      output_filename_base="out",
    )

  call = fake_client.models.generate_content_calls[0]
  assert call[
    "contents"] == "Alex: [pause for 1 seconds] Hello [pause for 0.5 seconds]"


def test_generate_multi_turn_dialog_rejects_more_than_two_voices():
  client = audio_client.GeminiAudioClient(
    label="test",
    model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False):
    with pytest.raises(audio_client.AudioGenerationError,
                       match="up to 2 speakers"):
      client.generate_multi_turn_dialog(
        turns=[
          audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_KORE,
                                  script="A"),
          audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_PUCK,
                                  script="B"),
          audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_ORUS,
                                  script="C"),
        ],
        output_filename_base="out",
      )


def test_generate_multi_turn_dialog_rejects_non_gemini_voices():
  client = audio_client.GeminiAudioClient(
    label="test",
    model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False):
    with pytest.raises(audio_client.AudioGenerationError,
                       match="requires GEMINI voices"):
      client.generate_multi_turn_dialog(
        turns=[
          audio_client.DialogTurn(
            voice=gen_audio.Voice.EN_US_STANDARD_FEMALE_1,
            script="Hello",
          ),
        ],
        output_filename_base="out",
      )


class _FakeElevenlabsRawClient:

  def __init__(self, response):
    self._response = response
    self.convert_calls: list[dict] = []

  def convert_with_timestamps(self, **kwargs):
    self.convert_calls.append(kwargs)
    return self._response


def test_elevenlabs_generate_multi_turn_dialog_uploads_audio_bytes():
  audio_bytes = b"fake-mp3-bytes"
  audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

  from elevenlabs.types.audio_with_timestamps_and_voice_segments_response_model import \
      AudioWithTimestampsAndVoiceSegmentsResponseModel
  from elevenlabs.types.character_alignment_response_model import \
      CharacterAlignmentResponseModel
  from elevenlabs.types.voice_segment import VoiceSegment

  class _FakeHttpResponse:

    def __init__(self, *, headers, data):
      self.headers = headers
      self.data = data

  normalized_alignment = CharacterAlignmentResponseModel(
    characters=["[", "g", "i", "g", "g", "l", "e", "s", "]", "H", "i"],
    character_start_times_seconds=[
      0.00,
      0.01,
      0.02,
      0.03,
      0.04,
      0.05,
      0.06,
      0.07,
      0.08,
      0.09,
      0.10,
    ],
    character_end_times_seconds=[
      0.01,
      0.02,
      0.03,
      0.04,
      0.05,
      0.06,
      0.07,
      0.08,
      0.09,
      0.10,
      0.11,
    ],
  )
  voice_segments = [
    VoiceSegment(
      voice_id="fake_voice",
      start_time_seconds=0.0,
      end_time_seconds=0.2,
      character_start_index=0,
      character_end_index=11,
      dialogue_input_index=0,
    )
  ]
  response_data = AudioWithTimestampsAndVoiceSegmentsResponseModel(
    audio_base_64=audio_b64,
    voice_segments=voice_segments,
    normalized_alignment=normalized_alignment,
  )
  response = _FakeHttpResponse(
    headers={
      "x-character-count": str(len("Hello") + len("Hi")),
      "request-id": "req_123",
    },
    data=response_data,
  )

  upload_mock = MagicMock()

  fake_raw = _FakeElevenlabsRawClient(response)

  class _FakeTextToDialogue:

    def __init__(self, raw):
      self.with_raw_response = raw

  class _FakeElevenlabsClient:

    def __init__(self, raw):
      self.text_to_dialogue = _FakeTextToDialogue(raw)

  client = audio_client.ElevenlabsAudioClient(
    label="test",
    model=audio_client.AudioModel.ELEVENLABS_ELEVEN_V3,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False), \
      patch.object(audio_client.ElevenlabsAudioClient,
                   "_create_model_client",
                   return_value=_FakeElevenlabsClient(fake_raw)), \
      patch.object(audio_client.cloud_storage,
                   "get_audio_gcs_uri",
                   return_value="gs://gen_audio/out.mp3"), \
      patch.object(audio_client.cloud_storage,
                   "upload_bytes_to_gcs",
                   upload_mock):
    result = client.generate_multi_turn_dialog(
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP,
          script="Hello",
          pause_sec_before=2,
        ),
        audio_client.DialogTurn(voice=gen_audio.Voice.ELEVENLABS_MINNIE,
                                script="Hi"),
      ],
      output_filename_base="out",
    )

  assert result.gcs_uri == "gs://gen_audio/out.mp3"
  assert result.timing is not None
  assert result.timing.normalized_alignment is not None
  assert [w.word for w in result.timing.normalized_alignment] == ["Hi"]
  assert result.timing.normalized_alignment[0].start_time == pytest.approx(
    0.00,
    rel=1e-6,
  )
  assert result.timing.normalized_alignment[0].end_time == pytest.approx(
    0.11,
    rel=1e-6,
  )
  assert [(c.char, c.start_time, c.end_time)
          for c in result.timing.normalized_alignment[0].char_timings] == [
            ("H", pytest.approx(0.00, rel=1e-6), pytest.approx(0.055,
                                                               rel=1e-6)),
            ("i", pytest.approx(0.055, rel=1e-6), pytest.approx(0.11,
                                                                rel=1e-6)),
          ]
  assert result.timing.voice_segments == [
    audio_timing.VoiceSegment(
      voice_id="fake_voice",
      start_time_seconds=0.0,
      end_time_seconds=0.2,
      word_start_index=0,
      word_end_index=1,
      dialogue_input_index=0,
    )
  ]
  assert result.metadata.model_name == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3.value
  assert result.metadata.token_counts["characters"] == len("Hello") + len("Hi")
  assert result.metadata.token_counts["unique_voice_ids"] == 2
  assert result.metadata.token_counts["audio_bytes"] == len(audio_bytes)
  expected_cost = (
    (len("Hello") + len("Hi")) *
    audio_client.ElevenlabsAudioClient.GENERATION_COSTS[
      audio_client.AudioModel.ELEVENLABS_ELEVEN_V3]["characters"])
  assert result.metadata.cost == pytest.approx(expected_cost, rel=1e-9)

  assert upload_mock.call_count == 1
  uploaded_bytes = upload_mock.call_args.args[0]
  uploaded_uri = upload_mock.call_args.args[1]
  uploaded_content_type = upload_mock.call_args.kwargs["content_type"]

  assert uploaded_bytes == audio_bytes
  assert uploaded_uri == "gs://gen_audio/out.mp3"
  assert uploaded_content_type == "audio/mpeg"

  assert fake_raw.convert_calls
  call = fake_raw.convert_calls[0]
  assert call["output_format"] == "mp3_44100_128"
  assert call["model_id"] == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3.value
  assert call["inputs"] == [{
    "text":
    "[pause for 2 seconds] Hello",
    "voice_id":
    gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP.voice_name,
  }, {
    "text":
    "Hi",
    "voice_id":
    gen_audio.Voice.ELEVENLABS_MINNIE.voice_name,
  }]


def test_elevenlabs_rejects_more_than_ten_unique_voice_ids():
  client = audio_client.ElevenlabsAudioClient(
    label="test",
    model=audio_client.AudioModel.ELEVENLABS_ELEVEN_V3,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False):
    turns = [
      audio_client.DialogTurn(voice=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP,
                              script="Hi") for _ in range(11)
    ]
    client._normalize_inputs = lambda _turns: [  # type: ignore[method-assign]
      {
        "text": "Hi",
        "voice_id": f"voice_{i}",
      } for i in range(11)
    ]
    with pytest.raises(audio_client.AudioGenerationError,
                       match="up to 10 unique voice IDs"):
      client._generate_multi_turn_dialog_internal(turns=turns, label="test")


def test_elevenlabs_timing_trims_trailing_silence_using_audio_energy():
  import math
  import struct

  # Build a WAV with a short burst of sound, then trailing silence.
  sr = 1000
  duration_sec = 4.0
  n = int(sr * duration_sec)
  samples: list[int] = []
  for i in range(n):
    t = float(i) / float(sr)
    if 2.60 <= t < 2.75:
      samples.append(int(12000 * math.sin(2.0 * math.pi * 50.0 * t)))
    else:
      samples.append(0)

  buffer = io.BytesIO()
  with wave.open(buffer, "wb") as wf:
    # pylint: disable=no-member
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr)
    wf.writeframes(struct.pack("<" + ("h" * len(samples)), *samples))
    # pylint: enable=no-member
  audio_bytes = buffer.getvalue()
  audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

  from elevenlabs.types.audio_with_timestamps_and_voice_segments_response_model import \
      AudioWithTimestampsAndVoiceSegmentsResponseModel
  from elevenlabs.types.character_alignment_response_model import \
      CharacterAlignmentResponseModel
  from elevenlabs.types.voice_segment import VoiceSegment

  class _FakeHttpResponse:

    def __init__(self, *, headers, data):
      self.headers = headers
      self.data = data

  # "What" is (incorrectly) spread over ~0.9s by the alignment.
  normalized_alignment = CharacterAlignmentResponseModel(
    characters=["W", "h", "a", "t"],
    character_start_times_seconds=[2.604, 2.828, 3.052, 3.276],
    character_end_times_seconds=[2.828, 3.052, 3.276, 3.500],
  )
  voice_segments = [
    VoiceSegment(
      voice_id="fake_voice",
      start_time_seconds=0.0,
      end_time_seconds=4.0,
      character_start_index=0,
      character_end_index=4,
      dialogue_input_index=0,
    )
  ]
  response_data = AudioWithTimestampsAndVoiceSegmentsResponseModel(
    audio_base_64=audio_b64,
    voice_segments=voice_segments,
    normalized_alignment=normalized_alignment,
  )
  response = _FakeHttpResponse(
    headers={
      "x-character-count": "4",
      "request-id": "req_123",
    },
    data=response_data,
  )

  upload_mock = MagicMock()
  fake_raw = _FakeElevenlabsRawClient(response)

  class _FakeTextToDialogue:

    def __init__(self, raw):
      self.with_raw_response = raw

  class _FakeElevenlabsClient:

    def __init__(self, raw):
      self.text_to_dialogue = _FakeTextToDialogue(raw)

  client = audio_client.ElevenlabsAudioClient(
    label="test",
    model=audio_client.AudioModel.ELEVENLABS_ELEVEN_V3,
    max_retries=0,
    output_format="wav_1000",
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False), \
      patch.object(audio_client.ElevenlabsAudioClient,
                   "_create_model_client",
                   return_value=_FakeElevenlabsClient(fake_raw)), \
      patch.object(audio_client.cloud_storage,
                   "get_audio_gcs_uri",
                   return_value="gs://gen_audio/out.wav"), \
      patch.object(audio_client.cloud_storage,
                   "upload_bytes_to_gcs",
                   upload_mock):
    result = client.generate_multi_turn_dialog(
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP,
          script="What",
        ),
      ],
      output_filename_base="out",
    )

  assert result.timing is not None
  assert result.timing.normalized_alignment is not None
  assert [w.word for w in result.timing.normalized_alignment] == ["What"]
  word = result.timing.normalized_alignment[0]
  assert word.start_time == pytest.approx(2.604, rel=1e-6)
  # Trailing silence should be trimmed well before the raw 3.5s end.
  assert word.end_time < 3.2
  assert word.end_time > 2.7
  assert word.char_timings[-1].end_time == pytest.approx(word.end_time,
                                                         rel=1e-6)

  assert result.timing.voice_segments == [
    audio_timing.VoiceSegment(
      voice_id="fake_voice",
      start_time_seconds=0.0,
      end_time_seconds=4.0,
      word_start_index=0,
      word_end_index=1,
      dialogue_input_index=0,
    )
  ]

  assert upload_mock.call_count == 1
  uploaded_bytes = upload_mock.call_args.args[0]
  uploaded_uri = upload_mock.call_args.args[1]
  uploaded_content_type = upload_mock.call_args.kwargs["content_type"]
  assert uploaded_bytes == audio_bytes
  assert uploaded_uri == "gs://gen_audio/out.wav"
  assert uploaded_content_type == "audio/wav"


def test_elevenlabs_timing_rejects_collapsed_timestamp_plateau():
  from elevenlabs.types.audio_with_timestamps_and_voice_segments_response_model import \
      AudioWithTimestampsAndVoiceSegmentsResponseModel
  from elevenlabs.types.character_alignment_response_model import \
      CharacterAlignmentResponseModel
  from elevenlabs.types.voice_segment import VoiceSegment

  spoken_text = "HeyWhatdoyoucallasmallValentinesDaycard"
  characters = list(spoken_text)
  starts: list[float] = []
  ends: list[float] = []
  for index, _char in enumerate(characters):
    if index < 10:
      t0 = 0.08 * float(index)
      t1 = t0 + 0.08
    else:
      t0 = 1.518
      t1 = 1.518
    starts.append(t0)
    ends.append(t1)

  normalized_alignment = CharacterAlignmentResponseModel(
    characters=characters,
    character_start_times_seconds=starts,
    character_end_times_seconds=ends,
  )
  voice_segments = [
    VoiceSegment(
      voice_id="fake_voice",
      start_time_seconds=0.0,
      end_time_seconds=4.0,
      character_start_index=0,
      character_end_index=len(characters),
      dialogue_input_index=0,
    )
  ]
  response_data = AudioWithTimestampsAndVoiceSegmentsResponseModel(
    audio_base_64="",
    voice_segments=voice_segments,
    normalized_alignment=normalized_alignment,
  )

  with pytest.raises(audio_client.AudioGenerationError) as excinfo:
    _ = audio_client._extract_elevenlabs_timing(  # pylint: disable=protected-access
      response_data,
      audio_bytes=b"",
      file_extension="wav",
    )
  error_text = str(excinfo.value)
  assert "collapsed" in error_text
  assert "segment_diagnostics=" in error_text
  assert "status=bad" in error_text
  assert "sample_run=" in error_text


def test_gemini_create_forced_alignment_raises_not_implemented():
  client = audio_client.GeminiAudioClient(
    label="test",
    model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
    max_retries=0,
  )

  with pytest.raises(NotImplementedError, match="not supported"):
    _ = client.create_forced_alignment(
      audio_bytes=b"audio",
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.GEMINI_PUCK,
          script="hello",
        ),
      ],
      audio_filename="clip.wav",
    )


def test_elevenlabs_create_forced_alignment_maps_words_directly():
  from elevenlabs.types.forced_alignment_character_response_model import \
      ForcedAlignmentCharacterResponseModel
  from elevenlabs.types.forced_alignment_response_model import \
      ForcedAlignmentResponseModel
  from elevenlabs.types.forced_alignment_word_response_model import \
      ForcedAlignmentWordResponseModel

  class _FakeForcedAlignment:

    def __init__(self, response):
      self.response = response
      self.calls: list[dict] = []
      self.with_raw_response = self

    def create(self, **kwargs):
      self.calls.append(kwargs)
      return self.response

  class _FakeElevenlabsClient:

    def __init__(self, forced_alignment):
      self.forced_alignment = forced_alignment

  class _FakeRawResponse:

    def __init__(self, *, headers, data):
      self.headers = headers
      self.data = data

  response_data = ForcedAlignmentResponseModel(
    characters=[
      ForcedAlignmentCharacterResponseModel(text="H", start=0.00, end=0.10),
      ForcedAlignmentCharacterResponseModel(text="i", start=0.10, end=0.20),
    ],
    words=[
      ForcedAlignmentWordResponseModel(
        text="Hi",
        start=0.00,
        end=0.20,
        loss=0.05,
      ),
      ForcedAlignmentWordResponseModel(
        text="there",
        start=0.21,
        end=0.60,
        loss=0.08,
      ),
    ],
    loss=0.07,
  )
  response = _FakeRawResponse(
    headers={
      "x-character-count": "8",
      "request-id": "req_fa_123",
    },
    data=response_data,
  )
  fake_forced_alignment = _FakeForcedAlignment(response)

  client = audio_client.ElevenlabsAudioClient(
    label="test",
    model=audio_client.AudioModel.ELEVENLABS_ELEVEN_V3,
    max_retries=0,
  )
  with patch.object(
      audio_client.ElevenlabsAudioClient,
      "_create_model_client",
      return_value=_FakeElevenlabsClient(fake_forced_alignment)), \
      patch.object(audio_client, "_log_response") as log_response_mock:
    timing, metadata = client.create_forced_alignment(
      audio_bytes=b"fake-audio",
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP,
          script="[playfully] Hi",
        ),
        audio_client.DialogTurn(
          voice=gen_audio.Voice.ELEVENLABS_MINNIE,
          script="there",
        ),
      ],
      audio_filename="clip.mp3",
    )

  assert timing.alignment is None
  assert timing.normalized_alignment is not None
  assert [w.word for w in timing.normalized_alignment] == ["Hi", "there"]
  assert timing.normalized_alignment[0].start_time == pytest.approx(0.00,
                                                                    rel=1e-6)
  assert timing.normalized_alignment[0].end_time == pytest.approx(0.20,
                                                                  rel=1e-6)
  assert timing.normalized_alignment[0].char_timings == []
  assert timing.voice_segments == [
    audio_timing.VoiceSegment(
      voice_id=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP.voice_name,
      start_time_seconds=0.0,
      end_time_seconds=0.2,
      word_start_index=0,
      word_end_index=1,
      dialogue_input_index=0,
    ),
    audio_timing.VoiceSegment(
      voice_id=gen_audio.Voice.ELEVENLABS_MINNIE.voice_name,
      start_time_seconds=0.21,
      end_time_seconds=0.6,
      word_start_index=1,
      word_end_index=2,
      dialogue_input_index=1,
    ),
  ]
  assert fake_forced_alignment.calls == [{
    "file": ("clip.mp3", b"fake-audio"),
    "text": "Hi\nthere",
  }]
  log_response_mock.assert_called_once()
  assert log_response_mock.call_args.args[0] == "Forced Alignment"
  assert metadata.model_name == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3.value
  assert metadata.token_counts["characters"] == 8
  assert metadata.token_counts["characters_input"] == len("Hi\nthere")


def test_elevenlabs_create_forced_alignment_handles_empty_words():
  from elevenlabs.types.forced_alignment_response_model import \
      ForcedAlignmentResponseModel

  class _FakeForcedAlignment:

    def __init__(self, response):
      self.response = response
      self.with_raw_response = self

    def create(self, **_kwargs):
      return self.response

  class _FakeElevenlabsClient:

    def __init__(self, forced_alignment):
      self.forced_alignment = forced_alignment

  class _FakeRawResponse:

    def __init__(self, *, headers, data):
      self.headers = headers
      self.data = data

  response_data = ForcedAlignmentResponseModel(
    characters=[],
    words=[],
    loss=0.0,
  )
  response = _FakeRawResponse(headers={}, data=response_data)
  client = audio_client.ElevenlabsAudioClient(
    label="test",
    model=audio_client.AudioModel.ELEVENLABS_ELEVEN_V3,
    max_retries=0,
  )
  with patch.object(
      audio_client.ElevenlabsAudioClient,
      "_create_model_client",
      return_value=_FakeElevenlabsClient(_FakeForcedAlignment(response))):
    timing, metadata = client.create_forced_alignment(
      audio_bytes=b"fake-audio",
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP,
          script="anything",
        ),
      ],
    )

  assert timing.normalized_alignment == []
  assert timing.voice_segments == []
  assert metadata.model_name == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3.value


def test_log_response_logs_word_timings_for_forced_alignment_model():
  from elevenlabs.types.forced_alignment_response_model import \
      ForcedAlignmentResponseModel
  from elevenlabs.types.forced_alignment_word_response_model import \
      ForcedAlignmentWordResponseModel

  response = ForcedAlignmentResponseModel(
    characters=[],
    words=[
      ForcedAlignmentWordResponseModel(
        text="Hello",
        start=0.10,
        end=0.30,
        loss=0.01,
      ),
      ForcedAlignmentWordResponseModel(
        text="world",
        start=0.35,
        end=0.60,
        loss=0.02,
      ),
    ],
    loss=0.015,
  )

  with patch.object(audio_client.logger, "info") as log_info:
    audio_client._log_response(  # pylint: disable=protected-access
      "Forced Alignment",
      response,
    )

  assert log_info.call_count == 1
  logged_text = log_info.call_args.args[0]
  assert "Forced Alignment" in logged_text
  assert "Hello @ 0.100s - 0.300s" in logged_text
  assert "world @ 0.350s - 0.600s" in logged_text


def test_elevenlabs_generate_multi_turn_dialog_returns_empty_timing_when_provider_alignment_is_invalid(
):
  audio_bytes = b"fake-mp3-bytes"
  audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

  from elevenlabs.types.audio_with_timestamps_and_voice_segments_response_model import \
      AudioWithTimestampsAndVoiceSegmentsResponseModel

  class _FakeHttpResponse:

    def __init__(self, *, headers, data):
      self.headers = headers
      self.data = data

  response_data = AudioWithTimestampsAndVoiceSegmentsResponseModel(
    audio_base_64=audio_b64,
    voice_segments=[],
    normalized_alignment=None,
  )
  response = _FakeHttpResponse(
    headers={
      "x-character-count": "2",
      "request-id": "req_456",
    },
    data=response_data,
  )

  fake_raw = _FakeElevenlabsRawClient(response)

  class _FakeTextToDialogue:

    def __init__(self, raw):
      self.with_raw_response = raw

  class _FakeElevenlabsClient:

    def __init__(self, raw):
      self.text_to_dialogue = _FakeTextToDialogue(raw)

  client = audio_client.ElevenlabsAudioClient(
    label="test",
    model=audio_client.AudioModel.ELEVENLABS_ELEVEN_V3,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False), \
      patch.object(audio_client.ElevenlabsAudioClient,
                   "_create_model_client",
                   return_value=_FakeElevenlabsClient(fake_raw)), \
      patch.object(audio_client, "_extract_elevenlabs_timing",
                   side_effect=audio_client.AudioGenerationError("invalid alignment")), \
      patch.object(audio_client.cloud_storage,
                   "get_audio_gcs_uri",
                   return_value="gs://gen_audio/out.mp3"), \
      patch.object(audio_client.cloud_storage,
                   "upload_bytes_to_gcs",
                   MagicMock()):
    result = client.generate_multi_turn_dialog(
      turns=[
        audio_client.DialogTurn(
          voice=gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP,
          script="Hello",
        ),
      ],
      output_filename_base="out",
    )

  assert result.timing is not None
  assert result.timing.alignment is None
  assert result.timing.normalized_alignment is None
  assert result.timing.voice_segments == []
