"""Tests for generation metadata tooltip formatting."""

from __future__ import annotations

from common import models
from web.utils import generation_metadata as generation_metadata_utils


def test_format_generation_metadata_tooltip_matches_admin_summary_and_details(
):
  metadata = models.GenerationMetadata()
  metadata.add_generation(
    models.SingleGenerationMetadata(
      label="setup_image",
      model_name="gemini-2.5-flash-image",
      token_counts={
        "input": 123,
        "output_image": 1,
      },
      generation_time_sec=1.25,
      cost=0.125,
    ))
  metadata.add_generation(
    models.SingleGenerationMetadata(
      label="setup_image",
      model_name="gemini-2.5-flash-image",
      token_counts={
        "input": 150,
      },
      generation_time_sec=0.5,
      cost=0.075,
    ))
  metadata.add_generation(
    models.SingleGenerationMetadata(
      label="punchline_image",
      model_name="imagen-4.0-fast-generate-001",
      cost=0.3,
    ))

  text = generation_metadata_utils.format_generation_metadata_tooltip(metadata)

  assert text == """SUMMARY
Total Cost: $0.5000

setup_image
  gemini-2.5-flash-image: $0.2000 (2)

punchline_image
  imagen-4.0-fast-generate-001: $0.3000 (1)

DETAILS
setup_image
  model_name: gemini-2.5-flash-image
  cost: $0.1250
  time: 1.25s
  token_counts:
    input: 123
    output_image: 1

setup_image (2)
  model_name: gemini-2.5-flash-image
  cost: $0.0750
  time: 0.50s
  token_counts:
    input: 150

punchline_image
  model_name: imagen-4.0-fast-generate-001
  cost: $0.3000
  token_counts:"""


def test_format_generation_metadata_tooltip_handles_missing_metadata():
  assert (generation_metadata_utils.format_generation_metadata_tooltip(None) ==
          "No generation metadata available for this joke.")


def test_format_generation_metadata_tooltip_falls_back_to_raw_metadata():
  text = generation_metadata_utils.format_generation_metadata_tooltip({
    "unexpected": {
      "nested": 3,
    },
  })

  assert text == "unexpected:\n  nested: 3"
