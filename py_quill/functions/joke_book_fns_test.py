"""Tests for the joke_book_fns module."""
from unittest.mock import MagicMock, Mock

import pytest
from functions import joke_book_fns


class DummyReq:
  """Dummy request class for testing."""

  def __init__(self,
               is_json=True,
               data=None,
               args=None,
               headers=None,
               path="",
               method='POST'):
    self.is_json = is_json
    self._data = data or {}
    self.args = args or {}
    self.headers = headers or {}
    self.path = path
    self.method = method

  def get_json(self):
    """Dummy request class for testing."""
    return {"data": self._data}


@pytest.fixture(name="mock_services")
def mock_services_fixture(monkeypatch):
  """Fixture that mocks external services using monkeypatch."""
  mock_firestore = Mock()
  mock_joke_ops = Mock()
  mock_auth = Mock()
  mock_utils = Mock()

  monkeypatch.setattr(joke_book_fns, 'firestore', mock_firestore)
  monkeypatch.setattr(joke_book_fns, 'joke_operations', mock_joke_ops)
  monkeypatch.setattr(joke_book_fns, 'auth', mock_auth)
  monkeypatch.setattr(joke_book_fns, 'create_timestamped_firestore_key',
                      mock_utils)

  # Mock the db call chain for joke_books collection
  mock_db = MagicMock()
  mock_collection = MagicMock()
  mock_doc_ref = MagicMock()
  mock_db.collection.return_value = mock_collection
  mock_collection.document.return_value = mock_doc_ref
  mock_firestore.db = lambda: mock_db

  return mock_firestore, mock_joke_ops, mock_auth, mock_utils, mock_doc_ref


@pytest.fixture(name="mock_get_user_id")
def mock_get_user_id_fixture(monkeypatch):
  """Fixture that mocks get_user_id function."""
  mock_get_user = Mock(return_value="test_user_id")
  monkeypatch.setattr(joke_book_fns, "get_user_id", mock_get_user)
  return mock_get_user


def test_create_book_success(mock_services, mock_get_user_id):
  """Test that create_book successfully creates a joke book."""
  # Arrange
  _, mock_joke_ops, mock_auth, mock_utils, mock_doc_ref = mock_services

  req = DummyReq(data={
    "joke_ids": ["joke1", "joke2"],
    "book_name": "My First Joke Book",
  })

  mock_user = Mock()
  mock_user.custom_claims = {'admin': True}
  mock_auth.get_user.return_value = mock_user

  mock_utils.return_value = "timestamped_id"

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  mock_get_user_id.assert_called_once()
  mock_auth.get_user.assert_called_once_with("test_user_id")
  assert mock_joke_ops.upscale_joke.call_count == 2
  mock_utils.assert_called_once_with("test_user_id")
  mock_doc_ref.set.assert_called_once_with({
    'book_name': 'My First Joke Book',
    'jokes': ['joke1', 'joke2'],
  })
  assert resp["data"]["book_id"] == "timestamped_id"


def test_create_book_not_admin(mock_services, mock_get_user_id):
  """Test that create_book returns an error if the user is not an admin."""
  # Arrange
  _, _, mock_auth, _, _ = mock_services

  req = DummyReq(data={
    "joke_ids": ["joke1", "joke2"],
    "book_name": "My First Joke Book",
  })

  mock_user = Mock()
  mock_user.custom_claims = {}
  mock_auth.get_user.return_value = mock_user

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  assert "error" in resp["data"]
  assert "User is not an admin" in resp["data"]["error"]


def test_create_book_missing_joke_ids(mock_services, mock_get_user_id):
  """Test that create_book returns an error if joke_ids are missing."""
  # Arrange
  _, _, mock_auth, _, _ = mock_services

  req = DummyReq(data={"book_name": "My First Joke Book"})

  mock_user = Mock()
  mock_user.custom_claims = {'admin': True}
  mock_auth.get_user.return_value = mock_user

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  assert "error" in resp["data"]
  assert "joke_ids is required" in resp["data"]["error"]


def test_create_book_missing_book_name(mock_services, mock_get_user_id):
  """Test that create_book returns an error if book_name is missing."""
  # Arrange
  _, _, mock_auth, _, _ = mock_services

  req = DummyReq(data={"joke_ids": ["joke1", "joke2"]})

  mock_user = Mock()
  mock_user.custom_claims = {'admin': True}
  mock_auth.get_user.return_value = mock_user

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  assert "error" in resp["data"]
  assert "book_name is required" in resp["data"]["error"]


def test_create_book_not_authenticated(mock_services, monkeypatch):
  """Test that create_book returns an error if the user is not authenticated."""
  # Arrange
  mock_get_user = Mock(return_value=None)
  monkeypatch.setattr(joke_book_fns, "get_user_id", mock_get_user)

  req = DummyReq(data={
    "joke_ids": ["joke1", "joke2"],
    "book_name": "My First Joke Book",
  })

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  assert "error" in resp["data"]
  assert "User not authenticated" in resp["data"]["error"]


def test_create_book_empty_joke_ids(mock_services, mock_get_user_id):
  """Test that create_book handles an empty list of joke_ids gracefully."""
  # Arrange
  _, mock_joke_ops, mock_auth, mock_utils, mock_doc_ref = mock_services

  req = DummyReq(data={
    "joke_ids": [],
    "book_name": "Empty Joke Book",
  })

  mock_user = Mock()
  mock_user.custom_claims = {'admin': True}
  mock_auth.get_user.return_value = mock_user
  mock_utils.return_value = "timestamped_id_empty"

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  mock_get_user_id.assert_called_once()
  mock_auth.get_user.assert_called_once_with("test_user_id")
  mock_joke_ops.upscale_joke.assert_not_called()
  mock_utils.assert_called_once_with("test_user_id")
  mock_doc_ref.set.assert_called_once_with({
    'book_name': 'Empty Joke Book',
    'jokes': [],
  })
  assert resp["data"]["book_id"] == "timestamped_id_empty"


def test_create_book_invalid_method(mock_services, mock_get_user_id):
  """Test that create_book returns an error for invalid HTTP methods."""
  # Arrange
  req = DummyReq(data={
    "joke_ids": ["joke1"],
    "book_name": "A Book",
  },
                 method='GET')

  # Act
  resp = joke_book_fns.create_book(req)

  # Assert
  assert "error" in resp["data"]
  assert "Method not allowed" in resp["data"]["error"]
