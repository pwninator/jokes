import unittest
from unittest.mock import patch

from google.api_core.exceptions import ResourceExhausted

from services import llm_client


class _FakeUsageMetadata:

  def __init__(
    self,
    *,
    prompt_token_count: int | None,
    cached_content_token_count: int | None,
    candidates_token_count: int | None,
  ):
    self.prompt_token_count = prompt_token_count
    self.cached_content_token_count = cached_content_token_count
    self.candidates_token_count = candidates_token_count


class _FakePart:

  def __init__(self, *, text: str, thought: bool):
    self.text = text
    self.thought = thought


class _FakeResponse:

  def __init__(
    self,
    *,
    text: str | None,
    thought_text: str | None = None,
    usage_metadata: _FakeUsageMetadata | None = None,
  ):
    self.text = text
    self.usage_metadata = usage_metadata
    self._parts = []
    if thought_text is not None:
      self._parts.append(_FakePart(text=thought_text, thought=True))

  @property
  def parts(self):  # Match google.genai.types.GenerateContentResponse.parts
    return self._parts


class _FakeModels:

  def __init__(self, responses: list[_FakeResponse]):
    self._responses = responses
    self.last_config = None

  def generate_content_stream(self, *, model: str, contents, config):  # pylint: disable=unused-argument
    self.last_config = config
    return iter(self._responses)


class _FakeGenaiClient:

  def __init__(self, responses: list[_FakeResponse]):
    self.models = _FakeModels(responses)


class LlmClientRoutingTest(unittest.TestCase):

  def test_get_client_routes_gemini_3_preview_to_gemini_client(self):
    client = llm_client.get_client(
      label="test",
      model=llm_client.LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=0.1,
      system_instructions=[],
      response_schema=None,
      thinking_tokens=0,
      output_tokens=10,
      max_retries=0,
    )
    self.assertIsInstance(client, llm_client.GeminiClient)

  def test_get_client_routes_gemini_2_5_to_vertex_client(self):
    client = llm_client.get_client(
      label="test",
      model=llm_client.LlmModel.GEMINI_2_5_FLASH,
      temperature=0.1,
      system_instructions=[],
      response_schema=None,
      thinking_tokens=0,
      output_tokens=10,
      max_retries=0,
    )
    self.assertIsInstance(client, llm_client.VertexClient)


class GeminiClientStreamingTest(unittest.TestCase):

  @patch.object(llm_client.config, "get_gemini_api_key", return_value="test-key")
  def test_stream_internal_emits_deltas_and_final_usage(self, _mock_key):
    client = llm_client.GeminiClient(
      label="test",
      model=llm_client.LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=0.0,
      system_instructions=[],
      response_schema=None,
      thinking_tokens=0,
      output_tokens=10,
      max_retries=0,
    )

    responses = [
      _FakeResponse(text="Hello", thought_text="Think1"),
      _FakeResponse(text="Hello world", thought_text="Think1Think2"),
      _FakeResponse(
        text="Hello world!",
        thought_text="Think1Think2",
        usage_metadata=_FakeUsageMetadata(
          prompt_token_count=10,
          cached_content_token_count=2,
          candidates_token_count=5,
        ),
      ),
    ]
    fake_client = _FakeGenaiClient(responses)
    client._model_client = fake_client  # pylint: disable=protected-access

    chunks = list(client._stream_internal(prompt_chunks=["prompt"]))  # pylint: disable=protected-access
    self.assertGreaterEqual(len(chunks), 2)

    # Gemini API does not support labels in GenerateContentConfig.
    self.assertIsNone(fake_client.models.last_config.labels)

    # First chunk should contain the initial delta.
    self.assertEqual(chunks[0].text, "Hello")
    self.assertEqual(chunks[0].text_delta, "Hello")
    self.assertEqual(chunks[0].thinking_text, "Think1")
    self.assertEqual(chunks[0].thinking_text_delta, "Think1")
    self.assertFalse(chunks[0].is_final)

    # Final chunk should include usage metadata mapped to our token naming.
    final = chunks[-1]
    self.assertTrue(final.is_final)
    self.assertIsNotNone(final.metadata)
    self.assertEqual(
      final.metadata.token_counts,
      {
        "prompt_tokens": 8,
        "cached_prompt_tokens": 2,
        "output_tokens": 5,
      },
    )

  def test_is_retryable_error(self):
    client = llm_client.GeminiClient(
      label="test",
      model=llm_client.LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=0.0,
      system_instructions=[],
      response_schema=None,
      thinking_tokens=0,
      output_tokens=10,
      max_retries=0,
    )
    self.assertTrue(client._is_retryable_error(ResourceExhausted("quota")))  # pylint: disable=protected-access


