"""Tests for the joke_fns module."""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from common import models
from functions import joke_fns


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


def _manual_tag_joke(
  joke_id: str,
  setup_text: str,
  punchline_text: str,
  seasonal: str | None,
) -> models.PunnyJoke:
  """Create a PunnyJoke tailored for manual tagging tests."""
  return models.PunnyJoke(
    key=joke_id,
    setup_text=setup_text,
    punchline_text=punchline_text,
    seasonal=seasonal,
  )


def _manual_tag_result(
  joke: models.PunnyJoke,
  distance: float = 0.1,
) -> SimpleNamespace:
  """Wrap a joke in a fake search result."""
  return SimpleNamespace(joke_id=joke.key, vector_distance=distance)


def test_run_manual_season_tag_updates_joke(monkeypatch):
  """Manual seasonal tagging should update jokes that are not Halloween yet."""
  captured_kwargs = {}

  def fake_search(**kwargs):
    captured_kwargs.update(kwargs)
    return [_manual_tag_result(_manual_tag_joke("j1", "S", "P", None), 0.2345)]

  monkeypatch.setattr(joke_fns.search, "search_jokes", fake_search)

  fetched_joke = _manual_tag_joke(
    "j1",
    "Why did the scarecrow win an award?",
    "Because he was outstanding in his field.",
    None,
  )
  monkeypatch.setattr(
    joke_fns.firestore, "get_punny_joke", lambda joke_id: fetched_joke
    if joke_id == "j1" else None)

  updates = []
  monkeypatch.setattr(
    joke_fns.firestore, "update_punny_joke",
    lambda joke_id, payload: updates.append((joke_id, payload)))

  html_response = joke_fns._run_manual_season_tag(
    query="scarecrow",
    threshold=0.5,
    dry_run=False,
    max_jokes=0,
  )

  assert captured_kwargs == {
    "query": "scarecrow",
    "label": "manual_season_tag",
    "limit": 1000,
    "field_filters": [],
    "distance_threshold": 0.5,
  }
  assert updates == [("j1", {"seasonal": "Halloween"})]
  assert "Updated Jokes (1)" in html_response
  assert "Dry Run: False" in html_response


def test_run_manual_season_tag_respects_dry_run(monkeypatch):
  """Dry run should list changes without performing updates."""

  def fake_search(**kwargs):  # pylint: disable=unused-argument
    return [_manual_tag_result(_manual_tag_joke("j1", "Setup", "Punch", None))]

  monkeypatch.setattr(joke_fns.search, "search_jokes", fake_search)
  monkeypatch.setattr(
    joke_fns.firestore, "get_punny_joke",
    lambda joke_id: _manual_tag_joke(joke_id, "Setup", "Punch", None))

  updates = []
  monkeypatch.setattr(
    joke_fns.firestore, "update_punny_joke",
    lambda joke_id, payload: updates.append((joke_id, payload)))

  html_response = joke_fns._run_manual_season_tag(
    query="pumpkin",
    threshold=0.4,
    dry_run=True,
    max_jokes=0,
  )

  assert not updates
  assert "Dry Run: True" in html_response
  assert "Updated Jokes (1)" in html_response


def test_run_manual_season_tag_skips_already_halloween(monkeypatch):
  """Jokes that already have seasonal Halloween should be skipped."""

  def fake_search(**kwargs):  # pylint: disable=unused-argument
    return [
      _manual_tag_result(
        _manual_tag_joke("j1", "Ghost joke", "Boo!", "Halloween"))
    ]

  monkeypatch.setattr(joke_fns.search, "search_jokes", fake_search)
  monkeypatch.setattr(
    joke_fns.firestore, "get_punny_joke", lambda joke_id: _manual_tag_joke(
      joke_id, "Ghost joke", "Boo!", "Halloween"))

  updates = []
  monkeypatch.setattr(
    joke_fns.firestore, "update_punny_joke",
    lambda joke_id, payload: updates.append((joke_id, payload)))

  html_response = joke_fns._run_manual_season_tag(
    query="ghost",
    threshold=0.5,
    dry_run=False,
    max_jokes=0,
  )

  assert not updates
  assert "Skipped Jokes (already Halloween) (1)" in html_response
  assert "Updated Jokes (0)" in html_response


def test_run_manual_season_tag_respects_max_jokes(monkeypatch):
  """The manual tagging operation should stop after reaching max_jokes."""
  jokes = [
    _manual_tag_joke("j1", "Setup 1", "Punch 1", None),
    _manual_tag_joke("j2", "Setup 2", "Punch 2", "Fall"),
  ]
  results = [
    _manual_tag_result(jokes[0], 0.12),
    _manual_tag_result(jokes[1], 0.34),
  ]

  monkeypatch.setattr(joke_fns.search, "search_jokes",
                      lambda **kwargs: results)  # pylint: disable=unused-argument

  joke_lookup = {j.key: j for j in jokes}
  monkeypatch.setattr(joke_fns.firestore, "get_punny_joke",
                      lambda joke_id: joke_lookup.get(joke_id))

  updates = []
  monkeypatch.setattr(
    joke_fns.firestore, "update_punny_joke",
    lambda joke_id, payload: updates.append((joke_id, payload)))

  html_response = joke_fns._run_manual_season_tag(
    query="any",
    threshold=0.5,
    dry_run=False,
    max_jokes=1,
  )

  assert updates == [("j1", {"seasonal": "Halloween"})]
  assert "Updated Jokes (1)" in html_response


def test_run_manual_season_tag_handles_no_results(monkeypatch):
  """Manual tagging should handle empty search results gracefully."""
  monkeypatch.setattr(joke_fns.search, "search_jokes", lambda **kwargs: [])  # pylint: disable=unused-argument

  updates = []
  monkeypatch.setattr(
    joke_fns.firestore, "update_punny_joke",
    lambda joke_id, payload: updates.append((joke_id, payload)))

  html_response = joke_fns._run_manual_season_tag(
    query="nonexistent",
    threshold=0.5,
    dry_run=False,
    max_jokes=0,
  )

  assert not updates
  assert "No jokes were updated." in html_response
  assert "No jokes were skipped." in html_response


def test_create_joke_sets_admin_owner_and_draft(monkeypatch):
  """Test that the create_joke function sets the admin owner and draft state."""
  # Arrange
  # Force unauthenticated
  monkeypatch.setattr(joke_fns,
                      "get_user_id",
                      lambda req, allow_unauthenticated=True: None)

  saved = None

  def fake_upsert(joke):
    nonlocal saved
    saved = joke
    joke.key = "key123"
    return joke

  monkeypatch.setattr(joke_fns.firestore, "upsert_punny_joke", fake_upsert)

  req = DummyReq(data={
    "setup_text": "s",
    "punchline_text": "p",
    "admin_owned": True,
  })

  # Act
  resp = joke_fns.create_joke(req)

  # Assert
  assert saved is not None
  assert saved.owner_user_id == "ADMIN"
  assert saved.state == models.JokeState.DRAFT
  assert resp["data"]["joke_data"]["state"] == "DRAFT"
  assert resp["data"]["joke_data"]["key"] == "key123"


def test_create_joke_sets_user_owner_when_not_admin(monkeypatch):
  """Test that the create_joke function sets the user owner when not admin."""
  # Arrange
  monkeypatch.setattr(joke_fns,
                      "get_user_id",
                      lambda req, allow_unauthenticated=True: "user1")

  saved = None

  def fake_upsert(joke):
    nonlocal saved
    saved = joke
    joke.key = "key123"
    return joke

  monkeypatch.setattr(joke_fns.firestore, "upsert_punny_joke", fake_upsert)

  req = DummyReq(data={
    "setup_text": "s",
    "punchline_text": "p",
    "admin_owned": False,
  })

  # Act
  joke_fns.create_joke(req)

  # Assert
  assert saved is not None
  assert saved.owner_user_id == "user1"
  assert saved.state == models.JokeState.DRAFT


def test_populate_joke_sets_state_unreviewed_and_persists(monkeypatch):
  """Test that populate_joke sets state to UNREVIEWED and saves it."""
  # Arrange
  monkeypatch.setattr(joke_fns,
                      "get_user_id",
                      lambda req, allow_unauthenticated=True: "user1")

  # Return a basic joke from internal populate and simulate internal save to UNREVIEWED
  def fake_populate_internal(**kwargs):
    joke_id = kwargs.get("joke_id", "jk123")
    j = models.PunnyJoke(key=joke_id, setup_text="s", punchline_text="p")
    # Simulate internal logic that sets to UNREVIEWED and persists
    j.state = models.JokeState.UNREVIEWED
    joke_fns.firestore.upsert_punny_joke(j)
    return j

  monkeypatch.setattr(joke_fns, "_populate_joke_internal",
                      fake_populate_internal)

  captured = {"saved": None}

  def fake_upsert(joke):
    captured["saved"] = joke
    return joke

  monkeypatch.setattr(joke_fns.firestore, "upsert_punny_joke", fake_upsert)

  req = DummyReq(
    data={
      "joke_id": "jk123",
      "image_quality": "medium",
      "images_only": False,
      "overwrite": True,
    })

  # Act
  resp = joke_fns.populate_joke(req)

  # Assert - state should be UNREVIEWED and persisted
  assert captured["saved"] is not None
  assert captured["saved"].state == models.JokeState.UNREVIEWED
  assert resp["data"]["joke_data"]["state"] == "UNREVIEWED"
  assert resp["data"]["joke_data"]["key"] == "jk123"


def test_search_jokes_applies_public_only_filter_by_default(monkeypatch):
  """Test that search_jokes applies the public_only filter by default."""
  captured = {}

  def fake_search_jokes(query=None,
                        field_filters=None,
                        limit=None,
                        distance_measure=None,
                        distance_threshold=None,
                        label=None,
                        **kwargs):  # pylint: disable=unused-argument
    captured['filters'] = list(field_filters or [])
    captured['label'] = label
    return []

  monkeypatch.setattr(joke_fns.search, 'search_jokes', fake_search_jokes)

  req = DummyReq(is_json=True,
                 data={
                   'search_query': 'cats',
                   'label': 'test_label'
                 })

  _ = joke_fns.search_jokes(req)

  assert 'filters' in captured
  filters = captured['filters']
  assert len(filters) == 2

  # Check state filter
  state_filter = filters[0]
  field, op, value = state_filter
  assert field == 'state'
  assert op == 'in'
  assert value == ['PUBLISHED', 'DAILY']

  # Check is_public filter
  public_filter = filters[1]
  field, op, value = public_filter
  assert field == 'is_public'
  assert op == '=='
  assert value == True

  assert captured['label'] == 'test_label'


def test_search_jokes_omits_filter_when_public_only_false(monkeypatch):
  """Test that search_jokes omits the public_only filter when public_only is False."""
  captured = {}

  def fake_search_jokes(query=None,
                        field_filters=None,
                        limit=None,
                        distance_measure=None,
                        distance_threshold=None,
                        label=None,
                        **kwargs):  # pylint: disable=unused-argument
    captured['filters'] = list(field_filters or [])
    captured['label'] = label
    return []

  monkeypatch.setattr(joke_fns.search, 'search_jokes', fake_search_jokes)

  req = DummyReq(is_json=True,
                 data={
                   'search_query': 'dogs',
                   'public_only': False
                 })

  _ = joke_fns.search_jokes(req)

  assert 'filters' in captured
  assert captured['filters'] == []
  assert captured['label'] == 'unknown'


@pytest.fixture(name='mock_services')
def mock_services_fixture(monkeypatch):
  """Fixture that mocks external services using monkeypatch."""
  mock_firestore = Mock()
  mock_fcm = Mock()

  monkeypatch.setattr('functions.joke_fns.firestore', mock_firestore)
  monkeypatch.setattr('functions.joke_fns.firebase_cloud_messaging', mock_fcm)

  return mock_firestore, mock_fcm


class TestSearchJokes:
  """Tests for search_jokes function."""

  @pytest.fixture(name='mock_search')
  def mock_search_fixture(self, monkeypatch):
    """Fixture that mocks the search.search_jokes function."""
    mock_search_jokes = Mock()
    monkeypatch.setattr('functions.joke_fns.search.search_jokes',
                        mock_search_jokes)
    return mock_search_jokes

  def test_valid_request_returns_jokes_with_distance(self, mock_search):
    """Test that a valid request returns jokes with id and vector distance."""

    # Arrange
    from services.search import JokeSearchResult
    j1 = JokeSearchResult(joke_id='joke1', vector_distance=0.1)
    j2 = JokeSearchResult(joke_id='joke2', vector_distance=0.2)
    mock_search.return_value = [j1, j2]

    req = MagicMock()
    req.path = "/"
    req.method = 'POST'
    req.is_json = True
    req.get_json.return_value = {
      "data": {
        "search_query": "test query",
        "max_results": 5,
        "label": "test_label"
      }
    }

    # Act
    resp = joke_fns.search_jokes(req)

    # Assert
    # match_mode default is TIGHT which passes distance_threshold
    mock_search.assert_called_once()
    called_kwargs = mock_search.call_args.kwargs
    assert called_kwargs['query'] == 'test query'
    assert called_kwargs['label'] == 'test_label'
    assert called_kwargs['limit'] == 5
    assert called_kwargs['distance_threshold'] == 0.32
    filters = called_kwargs['field_filters']
    assert isinstance(filters, list)
    assert len(filters) == 2

    # Check state filter
    state_filter = filters[0]
    field, op, value = state_filter
    assert field == 'state'
    assert op == 'in'
    assert value == ['PUBLISHED', 'DAILY']

    # Check is_public filter
    public_filter = filters[1]
    field, op, value = public_filter
    assert field == 'is_public'
    assert op == '=='
    assert value == True

    assert resp["data"]["jokes"] == [
      {
        "joke_id": "joke1",
        "vector_distance": 0.1
      },
      {
        "joke_id": "joke2",
        "vector_distance": 0.2
      },
    ]

  def test_missing_query_returns_error(self, mock_search):
    """Test that a request with a missing search query returns an error."""
    # Arrange
    req = MagicMock()
    req.path = "/"
    req.method = 'POST'
    req.is_json = True
    req.get_json.return_value = {"data": {"max_results": 5}}

    # Act
    resp = joke_fns.search_jokes(req)

    # Assert
    mock_search.assert_not_called()
    assert "Search query is required" in resp["data"]["error"]


class TestModifyJokeImage:
  """Tests for the modify_joke_image cloud function."""

  @pytest.fixture(name='mock_image_generation')
  def mock_image_generation_fixture(self, monkeypatch):
    """Fixture that mocks the image_generation service."""
    mock_image_gen = Mock()
    monkeypatch.setattr(joke_fns, "image_generation", mock_image_gen)
    return mock_image_gen

  @pytest.fixture(name='mock_firestore_service')
  def mock_firestore_service_fixture(self, monkeypatch):
    """Fixture that mocks the firestore service."""
    mock_firestore = Mock()
    monkeypatch.setattr(joke_fns, "firestore", mock_firestore)
    return mock_firestore

  def test_modify_joke_image_success(self, mock_image_generation,
                                     mock_firestore_service):
    """Test that modify_joke_image successfully modifies an image."""
    # Arrange
    req = DummyReq(data={
      "joke_id": "joke1",
      "setup_instruction": "make it funnier",
    })

    mock_joke = models.PunnyJoke(
      key="joke1",
      setup_text="test",
      punchline_text="test",
      setup_image_url="https://storage.googleapis.com/example/setup.png")
    mock_firestore_service.get_punny_joke.return_value = mock_joke

    mock_new_image = models.Image(url="http://example.com/new.png",
                                  gcs_uri="gs://example/new.png")
    mock_image_generation.modify_image.return_value = mock_new_image
    mock_firestore_service.upsert_punny_joke.return_value = mock_joke

    # Act
    resp = joke_fns.modify_joke_image(req)

    # Assert
    mock_firestore_service.get_punny_joke.assert_called_once_with("joke1")
    mock_image_generation.modify_image.assert_called_once()
    mock_firestore_service.upsert_punny_joke.assert_called_once()
    assert "data" in resp

  def test_modify_joke_image_no_instruction_error(self, mock_image_generation,
                                                  mock_firestore_service):
    """Test that modify_joke_image returns an error if no instruction is provided."""
    # Arrange
    req = DummyReq(data={"joke_id": "joke1"})

    # Act
    resp = joke_fns.modify_joke_image(req)

    # Assert
    assert "error" in resp["data"]
    assert "At least one instruction" in resp["data"]["error"]
    mock_image_generation.modify_image.assert_not_called()
    mock_firestore_service.upsert_punny_joke.assert_not_called()


class TestUpscaleJoke:
  """Tests for the upscale_joke cloud function."""

  @pytest.fixture(name='mock_joke_operations')
  def mock_joke_operations_fixture(self, monkeypatch):
    """Fixture that mocks the joke_operations module."""
    mock_operations = Mock()
    mock_operations.to_response_joke.side_effect = lambda joke: joke.to_dict(
      include_key=True)
    monkeypatch.setattr('functions.joke_fns.joke_operations', mock_operations)
    return mock_operations

  def test_upscale_joke_success(self, mock_joke_operations):
    """Test that upscale_joke successfully calls joke_operations.upscale_joke."""
    # Arrange
    req = DummyReq(data={"joke_id": "joke1"})

    mock_joke = models.PunnyJoke(
      key="joke1",
      setup_text="test",
      punchline_text="test",
      setup_image_url_upscaled="http://example.com/new_setup.png",
      punchline_image_url_upscaled="http://example.com/new_punchline.png",
    )
    mock_joke_operations.upscale_joke.return_value = mock_joke

    # Act
    resp = joke_fns.upscale_joke(req)

    # Assert
    mock_joke_operations.upscale_joke.assert_called_once_with(
      "joke1",
      mime_type="image/png",
      compression_quality=None,
    )
    assert "data" in resp
    assert resp["data"]["joke_data"]["key"] == "joke1"
    assert resp["data"]["joke_data"][
      "setup_image_url_upscaled"] == "http://example.com/new_setup.png"
    assert resp["data"]["joke_data"][
      "punchline_image_url_upscaled"] == "http://example.com/new_punchline.png"

  def test_upscale_joke_missing_joke_id(self, mock_joke_operations):
    """Test that upscale_joke returns error when joke_id is missing."""
    # Arrange
    req = DummyReq(data={})

    # Act
    resp = joke_fns.upscale_joke(req)

    # Assert
    mock_joke_operations.upscale_joke.assert_not_called()
    assert "error" in resp["data"]
    assert "joke_id is required" in resp["data"]["error"]

  def test_upscale_joke_operation_fails(self, mock_joke_operations):
    """Test that upscale_joke returns error when joke_operations.upscale_joke fails."""
    # Arrange
    req = DummyReq(data={"joke_id": "joke1"})
    mock_joke_operations.upscale_joke.side_effect = Exception("Joke not found")

    # Act
    resp = joke_fns.upscale_joke(req)

    # Assert
    mock_joke_operations.upscale_joke.assert_called_once_with(
      "joke1",
      mime_type="image/png",
      compression_quality=None,
    )
    assert "error" in resp["data"]
    assert "Failed to upscale joke: Joke not found" in resp["data"]["error"]
