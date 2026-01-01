from unittest import mock
import pytest
from common import models, joke_operations
from functions.prompts import joke_operation_prompts

def test_generate_joke_metadata_skips_if_incomplete():
  joke = models.PunnyJoke(setup_text="Setup", punchline_text="")
  with mock.patch('functions.prompts.joke_operation_prompts.generate_joke_metadata') as mock_prompt:
    joke_operations.generate_joke_metadata(joke)
    mock_prompt.assert_not_called()

def test_generate_joke_metadata_calls_prompt_if_complete():
  joke = models.PunnyJoke(setup_text="Setup", punchline_text="Punchline")

  # Mock returning a SingleGenerationMetadata, which is what generate_joke_metadata now returns
  mock_metadata = models.SingleGenerationMetadata(model_name="test_model", cost=0.1)

  with mock.patch('functions.prompts.joke_operation_prompts.generate_joke_metadata', return_value=("Seasonal", ["Tag1", "Tag2"], mock_metadata)) as mock_prompt:
    joke_operations.generate_joke_metadata(joke)

    mock_prompt.assert_called_once_with(setup_text="Setup", punchline_text="Punchline")
    assert joke.seasonal == "Seasonal"
    assert joke.tags == ["Tag1", "Tag2"]

    # Verify metadata was added
    assert len(joke.generation_metadata.generations) == 1
    assert joke.generation_metadata.generations[0].model_name == "test_model"

def test_generate_joke_metadata_adds_generation_metadata():
  joke = models.PunnyJoke(setup_text="Setup", punchline_text="Punchline")

  single_gen = models.SingleGenerationMetadata(model_name="test_model", cost=0.1)

  with mock.patch('functions.prompts.joke_operation_prompts.generate_joke_metadata', return_value=("Seasonal", ["Tag1"], single_gen)):
    joke_operations.generate_joke_metadata(joke)

    assert len(joke.generation_metadata.generations) == 1
    assert joke.generation_metadata.generations[0].model_name == "test_model"
