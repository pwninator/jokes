from unittest.mock import MagicMock, patch

import pytest

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
  assert call["contents"] == "A: Hello\nA: there\nB: Hi\nA: Ok"
  response_modalities = getattr(call["config"], "response_modalities", None) or []
  assert "AUDIO" in response_modalities


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

