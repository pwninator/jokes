import base64
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
        audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_KORE, script="Hi"),
        audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_PUCK, script="Ok"),
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
  response_modalities = getattr(call["config"], "response_modalities", None) or []
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
  assert call["contents"] == "Alex: [pause for 1 seconds] Hello [pause for 0.5 seconds]"


def test_generate_multi_turn_dialog_rejects_more_than_two_voices():
  client = audio_client.GeminiAudioClient(
    label="test",
    model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
    max_retries=0,
  )

  with patch.object(audio_client.utils, "is_emulator", return_value=False):
    with pytest.raises(audio_client.AudioGenerationError, match="up to 2 speakers"):
      client.generate_multi_turn_dialog(
        turns=[
          audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_KORE, script="A"),
          audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_PUCK, script="B"),
          audio_client.DialogTurn(voice=gen_audio.Voice.GEMINI_ORUS, script="C"),
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
    with pytest.raises(audio_client.AudioGenerationError, match="requires GEMINI voices"):
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

  from elevenlabs.types.audio_with_timestamps_and_voice_segments_response_model import (
    AudioWithTimestampsAndVoiceSegmentsResponseModel,
  )
  from elevenlabs.types.character_alignment_response_model import (
    CharacterAlignmentResponseModel,
  )
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
  assert result.timing.normalized_alignment.characters == [
    "H",
    "i",
  ]
  assert result.timing.normalized_alignment.character_start_times_seconds == pytest.approx(
    [0.00, 0.055],
    rel=1e-6,
  )
  assert result.timing.normalized_alignment.character_end_times_seconds == pytest.approx(
    [0.055, 0.11],
    rel=1e-6,
  )
  assert result.timing.voice_segments == [
    audio_timing.VoiceSegment(
      voice_id="fake_voice",
      start_time_seconds=0.0,
      end_time_seconds=0.2,
      character_start_index=0,
      character_end_index=2,
      dialogue_input_index=0,
    )
  ]
  assert result.metadata.model_name == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3.value
  assert result.metadata.token_counts["characters"] == len("Hello") + len("Hi")
  assert result.metadata.token_counts["unique_voice_ids"] == 2
  assert result.metadata.token_counts["audio_bytes"] == len(audio_bytes)
  assert result.metadata.cost == 0.0

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
    "text": "[pause for 2 seconds] Hello",
    "voice_id": gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP.voice_name,
  }, {
    "text": "Hi",
    "voice_id": gen_audio.Voice.ELEVENLABS_MINNIE.voice_name,
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
                              script="Hi")
      for _ in range(11)
    ]
    client._normalize_inputs = lambda _turns: [  # type: ignore[method-assign]
      {
        "text": "Hi",
        "voice_id": f"voice_{i}",
      } for i in range(11)
    ]
    with pytest.raises(audio_client.AudioGenerationError, match="up to 10 unique voice IDs"):
      client._generate_multi_turn_dialog_internal(turns=turns, label="test")
