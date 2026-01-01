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

  mock_metadata = models.GenerationMetadata()

  with mock.patch('functions.prompts.joke_operation_prompts.generate_joke_metadata', return_value=("Seasonal", ["Tag1", "Tag2"], mock_metadata)) as mock_prompt:
    joke_operations.generate_joke_metadata(joke)

    mock_prompt.assert_called_once_with(setup_text="Setup", punchline_text="Punchline")
    assert joke.seasonal == "Seasonal"
    assert joke.tags == ["Tag1", "Tag2"]
    # Verify metadata was added.
    # Since we added `mock_metadata` (which is empty by default) to the joke's existing metadata,
    # and the joke's metadata was empty, the result depends on how add_generation handles empty.
    # In `models.py`, `add_generation` only adds if `not other.is_empty` or if it's a `GenerationMetadata`
    # it filters for non-empty generations.
    # So if mock_metadata is empty, nothing gets added.

    # Correction: The code under test ran with the *original* mock_metadata.
    # If that was empty, `add_generation` added nothing.
    assert len(joke.generation_metadata.generations) == 0

def test_generate_joke_metadata_adds_generation_metadata():
  joke = models.PunnyJoke(setup_text="Setup", punchline_text="Punchline")

  single_gen = models.SingleGenerationMetadata(model_name="test_model", cost=0.1)
  mock_metadata = models.GenerationMetadata(generations=[single_gen])

  with mock.patch('functions.prompts.joke_operation_prompts.generate_joke_metadata', return_value=("Seasonal", ["Tag1"], mock_metadata)):
    joke_operations.generate_joke_metadata(joke)

    assert len(joke.generation_metadata.generations) == 1
    assert joke.generation_metadata.generations[0].model_name == "test_model"
