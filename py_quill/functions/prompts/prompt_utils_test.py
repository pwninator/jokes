"""Unit tests for prompt_utils helpers."""

import functions.prompts.prompt_utils as prompt_utils


def test_parse_llm_response_line_separated_standard():
  response = """
SETUP_SCENE_DESCRIPTION:
Line 1 of setup
Line 2 of setup

PUNCHLINE_SCENE_DESCRIPTION:
Line A of punchline
Line B of punchline
"""

  result = prompt_utils.parse_llm_response_line_separated(
    ["SETUP_SCENE_DESCRIPTION", "PUNCHLINE_SCENE_DESCRIPTION"], response)

  assert result["SETUP_SCENE_DESCRIPTION"] == "Line 1 of setup\nLine 2 of setup"
  assert (
    result["PUNCHLINE_SCENE_DESCRIPTION"] ==
    "Line A of punchline\nLine B of punchline")


def test_parse_llm_response_line_separated_handles_missing_sections():
  response = """
SETUP_SCENE_DESCRIPTION:
Only setup content here
"""

  result = prompt_utils.parse_llm_response_line_separated(
    ["SETUP_SCENE_DESCRIPTION", "PUNCHLINE_SCENE_DESCRIPTION"], response)

  assert result["SETUP_SCENE_DESCRIPTION"] == "Only setup content here"
  assert result["PUNCHLINE_SCENE_DESCRIPTION"] == ""


def test_parse_llm_response_line_separated_is_case_insensitive_and_trims():
  response = """
setup_scene_description :
  Setup line with indentation

punchline_scene_description:
Punchline line
"""

  result = prompt_utils.parse_llm_response_line_separated(
    ["SETUP_SCENE_DESCRIPTION", "PUNCHLINE_SCENE_DESCRIPTION"], response)

  assert result["SETUP_SCENE_DESCRIPTION"] == "Setup line with indentation"
  assert result["PUNCHLINE_SCENE_DESCRIPTION"] == "Punchline line"


def test_parse_llm_response_line_separated_ignores_text_outside_sections():
  response = """
Preface text that should be ignored

SETUP_SCENE_DESCRIPTION:
Setup info
Unrecognized header:
Still part of setup

PUNCHLINE_SCENE_DESCRIPTION:
Punchline info
"""

  result = prompt_utils.parse_llm_response_line_separated(
    ["SETUP_SCENE_DESCRIPTION", "PUNCHLINE_SCENE_DESCRIPTION"], response)

  assert result["SETUP_SCENE_DESCRIPTION"] == "Setup info\nUnrecognized header:\nStill part of setup"
  assert result["PUNCHLINE_SCENE_DESCRIPTION"] == "Punchline info"

