"""Unit tests for image_generation module."""

import unittest
from unittest.mock import patch

from common import image_generation, models
from common.image_generation import _strip_prompt_preamble


class ModifyImageTest(unittest.TestCase):
  """Tests for the modify_image function."""

  @patch('common.image_generation.cloud_storage.download_bytes_from_gcs')
  @patch('common.image_generation.image_client.ImageClient.generate_image')
  def test_modify_image_success(self, mock_generate_image,
                                mock_download_bytes):
    """Test that modify_image successfully modifies an image."""
    # Arrange
    mock_download_bytes.return_value = b'test_image_bytes'

    mock_generated_image = models.Image(
      url='http://new-image.com/test.png',
      gcs_uri='gs://new-image/test.png',
    )
    mock_generate_image.return_value = mock_generated_image

    image = models.Image(
      url='http://example.com/test.png',
      gcs_uri='gs://example/test.png',
    )
    instruction = 'make it better'

    # Act
    new_image = image_generation.modify_image(image, instruction)

    # Assert
    expected_prompt = "make it better Make sure to the exact same artistic style, color palette, background texture, and overall aesthetic as the original image. Make sure the characters, objects, fonts, color palette, etc. are consistent."
    mock_download_bytes.assert_called_once_with('gs://example/test.png')
    mock_generate_image.assert_called_once_with(
      expected_prompt,
      reference_images=[b'test_image_bytes'],
      save_to_firestore=False,
    )
    self.assertEqual(new_image.url, 'http://new-image.com/test.png')
    self.assertEqual(new_image.original_prompt, instruction)
    self.assertEqual(new_image.final_prompt, instruction)


def test_basic_strip_preamble_and_postamble():
  """Test basic functionality of stripping both preamble and postamble."""
  preamble = "Generate another image using the same artistic style, color palette, background texture, and overall aesthetic as the reference images. Make sure the characters, objects, etc. are consistent."
  postamble = """The only text on the image is the phrase "A pen-grin!", prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch."""
  image_description = """Generate another image using the same artistic style, color palette, background texture, and overall aesthetic as the reference images. Make sure the characters, objects, etc. are consistent. Generate another image using the same artistic style, color palette, background texture, and overall aesthetic as the reference images. Make sure the characters, objects, etc. are consistent. The same adorable, fluffy baby penguin, now with an enormous, joyful, beaming grin that stretches across its entire face. Its eyes are squeezed shut in pure happiness, and its little flippers are thrown up in the air with glee. The text 'A pen-grin!' is prominently displayed. The only text on the image is the phrase "A pen-grin!", prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch. The only text on the image is the phrase "A pen-grin!", prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch."""

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "The same adorable, fluffy baby penguin, now with an enormous, joyful, beaming grin that stretches across its entire face. Its eyes are squeezed shut in pure happiness, and its little flippers are thrown up in the air with glee. The text 'A pen-grin!' is prominently displayed."


def test_multiple_preambles_and_postambles():
  """Test stripping multiple occurrences of preamble and postamble."""
  preamble = "PREFIX"
  postamble = "SUFFIX"
  image_description = "PREFIXPREFIXPREFIXCORE CONTENTSUFFIXSUFFIXSUFFIX"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "CORE CONTENT"


def test_only_preamble_present():
  """Test stripping when only preamble is present."""
  preamble = "Begin: "
  postamble = " :Finish"
  image_description = "Begin: Begin: Content here"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Content here"


def test_only_postamble_present():
  """Test stripping when only postamble is present."""
  preamble = "Start: "
  postamble = " END"
  image_description = "Content here END END"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Content here"


def test_neither_preamble_nor_postamble_present():
  """Test when neither preamble nor postamble are present."""
  preamble = "BEFORE"
  postamble = "AFTER"
  image_description = "Just some content in the middle"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Just some content in the middle"


def test_empty_image_description():
  """Test with empty image description."""
  preamble = "PRE"
  postamble = "POST"
  image_description = ""

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == ""


def test_whitespace_handling():
  """Test proper handling of whitespace."""
  preamble = "START"
  postamble = "END"
  image_description = "  START  Content with spaces  END  "

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Content with spaces"


def test_preamble_and_postamble_as_substring():
  """Test when preamble/postamble appear as substrings within content."""
  preamble = "THE"
  postamble = "DOG"
  image_description = "THE cat and THE dog played together DOG"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "cat and THE dog played together"


def test_same_preamble_and_postamble():
  """Test when preamble and postamble are the same."""
  preamble = "MARKER"
  postamble = "MARKER"
  image_description = "MARKERMARKER Content here MARKERMARKER"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Content here"


def test_empty_preamble_and_postamble():
  """Test with empty preamble and postamble."""
  preamble = ""
  postamble = ""
  image_description = "Content remains unchanged"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Content remains unchanged"


def test_content_identical_to_preamble_postamble():
  """Test when content is exactly the preamble followed by postamble."""
  preamble = "HELLO"
  postamble = "WORLD"
  image_description = "HELLOWORLD"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == ""


def test_nested_preamble_postamble_patterns():
  """Test complex nested patterns."""
  preamble = "A"
  postamble = "Z"
  image_description = "AAAA Content ZZZZ"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Content"


def test_whitespace_only_after_stripping():
  """Test when only whitespace remains after stripping."""
  preamble = "START"
  postamble = "END"
  image_description = "START   END"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == ""


def test_multiline_content():
  """Test with multiline content."""
  preamble = "BEGIN"
  postamble = "FINISH"
  image_description = "BEGIN\nLine 1\nLine 2\nFINISH"

  result = _strip_prompt_preamble(image_description, preamble, postamble)

  assert result == "Line 1\nLine 2"
