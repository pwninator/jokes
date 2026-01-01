from unittest import mock
import pytest
from common import models, joke_operations
from functions import joke_creation_fns
from functions import function_utils

@pytest.fixture
def mock_joke_operations():
  with mock.patch('functions.joke_creation_fns.joke_operations') as mock_ops:
    yield mock_ops

@pytest.fixture
def mock_firestore():
  with mock.patch('functions.joke_creation_fns.firestore') as mock_fs:
    yield mock_fs

def test_joke_creation_process_generates_metadata_on_text_change(mock_joke_operations, mock_firestore):
  # Setup
  mock_req = mock.Mock()
  mock_req.method = 'POST'
  mock_req.path = '/'
  mock_req.is_json = True
  mock_req.get_json.return_value = {
    'data': {
        'user_id': 'test_user',
        'setup_text': 'Why did the chicken cross the road?',
        'punchline_text': 'To get to the other side!'
    }
  }

  # Configure mock request headers as a dictionary to support .get() and .split()
  mock_req.headers = {
    'Authorization': 'Bearer test_token'
  }

  # Mock initialize_joke to return a joke object
  mock_joke = models.PunnyJoke(
    setup_text='Why did the chicken cross the road?',
    punchline_text='To get to the other side!'
  )
  mock_joke_operations.initialize_joke.return_value = mock_joke

  # Mock generate_joke_metadata to verify it's called
  mock_joke_operations.generate_joke_metadata.return_value = mock_joke

  # Mock other operations
  mock_joke_operations.regenerate_scene_ideas.return_value = mock_joke
  mock_firestore.upsert_punny_joke.return_value = mock_joke

  # Mock to_response_joke to return a JSON serializable dict
  mock_joke_operations.to_response_joke.return_value = {
      'setup_text': 'Why did the chicken cross the road?',
      'punchline_text': 'To get to the other side!',
      'seasonal': None,
      'tags': []
  }

  # Mock get_user_id to avoid authorization issues
  with mock.patch('functions.joke_creation_fns.get_user_id', return_value='test_user'):
    # Execute
    joke_creation_fns.joke_creation_process(mock_req)

  # Verify
  mock_joke_operations.generate_joke_metadata.assert_called_once_with(mock_joke)

def test_joke_creation_process_skips_metadata_if_no_text(mock_joke_operations, mock_firestore):
  # Setup
  mock_req = mock.Mock()
  mock_req.method = 'POST'
  mock_req.path = '/'
  mock_req.is_json = True
  mock_req.get_json.return_value = {
      'data': {
          'user_id': 'test_user',
          'joke_id': 'existing_joke'
      }
  }

  # Configure mock request headers
  mock_req.headers = {
    'Authorization': 'Bearer test_token'
  }

  # Mock initialize_joke
  mock_joke = models.PunnyJoke(
      setup_text='Existing setup',
      punchline_text='Existing punchline'
  )
  mock_joke_operations.initialize_joke.return_value = mock_joke

  # Mock other operations
  mock_firestore.upsert_punny_joke.return_value = mock_joke

  # Mock to_response_joke to return a JSON serializable dict
  mock_joke_operations.to_response_joke.return_value = {
      'setup_text': 'Existing setup',
      'punchline_text': 'Existing punchline'
  }

  # Mock get_user_id to avoid authorization issues
  with mock.patch('functions.joke_creation_fns.get_user_id', return_value='test_user'):
    # Execute
    joke_creation_fns.joke_creation_process(mock_req)

  # Verify
  mock_joke_operations.generate_joke_metadata.assert_not_called()

def test_joke_creation_process_handles_partial_data_gracefully(mock_joke_operations, mock_firestore):
  # Setup: Request with only setup_text
  mock_req = mock.Mock()
  mock_req.method = 'POST'
  mock_req.path = '/'
  mock_req.is_json = True
  mock_req.get_json.return_value = {
      'data': {
          'user_id': 'test_user',
          'setup_text': 'Why did the chicken cross the road?'
          # Missing punchline_text
      }
  }

  mock_req.headers = {
    'Authorization': 'Bearer test_token'
  }

  # Mock initialize_joke to return a joke with only setup
  mock_joke = models.PunnyJoke(
      setup_text='Why did the chicken cross the road?',
      punchline_text=''
  )
  mock_joke_operations.initialize_joke.return_value = mock_joke

  # Mock generate_joke_metadata to do nothing
  mock_joke_operations.generate_joke_metadata.return_value = mock_joke

  # Mock other operations
  mock_firestore.upsert_punny_joke.return_value = mock_joke

  # Mock to_response_joke
  mock_joke_operations.to_response_joke.return_value = {
      'setup_text': 'Why did the chicken cross the road?',
      'punchline_text': ''
  }

  # Mock get_user_id
  with mock.patch('functions.joke_creation_fns.get_user_id', return_value='test_user'):
    # Execute
    joke_creation_fns.joke_creation_process(mock_req)

  # Verify: generate_joke_metadata is called
  # The controller calls it because setup_text is present.
  mock_joke_operations.generate_joke_metadata.assert_called_once_with(mock_joke)
