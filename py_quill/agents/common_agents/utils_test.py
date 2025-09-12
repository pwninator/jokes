"""Unit tests for utility functions."""

from common.utils import extract_json_dict


class TestExtractJsonDict:
  """Tests for the extract_json_dict function."""

  def test_extract_json_dict_valid(self):
    """Test extracting a valid JSON dictionary."""
    test_str = '{"key": "value", "number": 42}'
    result = extract_json_dict(test_str)
    assert result == {"key": "value", "number": 42}

  def test_extract_json_dict_with_surrounding_text(self):
    """Test extracting a JSON dictionary with surrounding text."""
    test_str = 'Here is some data: {"key": "value", "number": 42} and more text'
    result = extract_json_dict(test_str)
    assert result == {"key": "value", "number": 42}

  def test_extract_json_dict_complex(self):
    """Test extracting a complex JSON dictionary."""
    test_str = '{"nested": {"a": 1, "b": [2, 3, 4]}, "boolean": true, "null_value": null}'
    result = extract_json_dict(test_str)
    assert result == {
      "nested": {
        "a": 1,
        "b": [2, 3, 4]
      },
      "boolean": True,
      "null_value": None
    }

  def test_extract_json_dict_no_json(self):
    """Test when no JSON is present."""
    test_str = 'This string has no JSON dictionary'
    result = extract_json_dict(test_str)
    assert result is None

  def test_extract_json_dict_malformed(self):
    """Test with malformed JSON."""
    test_str = '{"key": "unclosed string, "missing": "comma"}'
    result = extract_json_dict(test_str)
    assert result is None

  def test_extract_json_dict_with_multiline(self):
    """Test extracting a multiline JSON dictionary."""
    test_str = '''
        Some text before
        {
            "key": "value",
            "array": [1, 2, 3],
            "object": {
                "nested": "property"
            }
        }
        Some text after
        '''
    result = extract_json_dict(test_str)
    assert result == {
      "key": "value",
      "array": [1, 2, 3],
      "object": {
        "nested": "property"
      }
    }
