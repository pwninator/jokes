"""Tests for jokes fields migration in util_fns.py."""

from unittest import mock
import pytest
from functions import util_fns


class FakeDoc:

  def __init__(self, doc_id: str, data: dict | None):
    self.id = doc_id
    self._data = data
    self.reference = self
    self.update_calls: list[dict] = []

  def to_dict(self) -> dict | None:
    return self._data

  def get(self):
    return self

  @property
  def exists(self):
    return self._data is not None

  def update(self, update_dict: dict) -> None:
    if self._data is None:
      self._data = {}
    self.update_calls.append(dict(update_dict))
    self._data.update(update_dict)


class FakeCollection:

  def __init__(self, docs: list[FakeDoc]):
    self._docs = {doc.id: doc for doc in docs}

  def stream(self) -> list[FakeDoc]:
    return list(self._docs.values())

  def document(self, doc_id: str) -> FakeDoc:
    return self._docs.get(doc_id, FakeDoc(doc_id, None))


class FakeFirestoreClient:

  def __init__(self, jokes_docs: list[FakeDoc] | None = None):
    self._collections = {
      'jokes': FakeCollection(jokes_docs or []),
    }

  def collection(self, name: str) -> FakeCollection:
    if name in self._collections:
      return self._collections[name]
    raise AssertionError(f"Unexpected collection requested: {name}")


@pytest.fixture
def cap_logs(monkeypatch):
  messages: list[str] = []

  def fake_info(msg: str) -> None:
    messages.append(str(msg))

  monkeypatch.setattr(util_fns.logger, 'info', fake_info)
  return messages


def _make_joke_doc(doc_id: str, data: dict) -> FakeDoc:
  return FakeDoc(doc_id, data)


def test_migration_calculates_popularity_score(monkeypatch):
  """Test that the migration correctly calculates and updates the popularity_score."""
  joke1 = _make_joke_doc('j1', {'num_saves': 10, 'num_shares': 5})
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_popularity_score_migration(dry_run=False, max_jokes=0)

  assert results['updated_jokes'] == 1
  assert results['unchanged_jokes'] == 0
  assert len(joke1.update_calls) == 1
  assert joke1.update_calls[0] == {'popularity_score': 35} # 10 + (5 * 5)


def test_migration_handles_missing_fields(monkeypatch):
  """Test that the migration handles jokes with missing num_saves or num_shares."""
  joke1 = _make_joke_doc('j1', {'num_saves': 10})
  joke2 = _make_joke_doc('j2', {'num_shares': 5})
  joke3 = _make_joke_doc('j3', {})
  client = FakeFirestoreClient(jokes_docs=[joke1, joke2, joke3])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  util_fns.run_popularity_score_migration(dry_run=False, max_jokes=0)

  assert joke1.update_calls[0] == {'popularity_score': 10}
  assert joke2.update_calls[0] == {'popularity_score': 25}
  assert joke3.update_calls[0] == {'popularity_score': 0}


def test_migration_does_not_update_correct_score(monkeypatch):
  """Test that the migration does not update a joke that already has the correct popularity_score."""
  joke1 = _make_joke_doc('j1', {'num_saves': 10, 'num_shares': 5, 'popularity_score': 35})
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_popularity_score_migration(dry_run=False, max_jokes=0)

  assert results['updated_jokes'] == 0
  assert results['unchanged_jokes'] == 1
  assert not joke1.update_calls


def test_migration_dry_run_does_not_write_updates(monkeypatch):
  """Test that dry_run mode prevents any updates from being written."""
  joke1 = _make_joke_doc('j1', {'num_saves': 10, 'num_shares': 5})
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_popularity_score_migration(dry_run=True, max_jokes=0)

  assert results['updated_jokes'] == 0
  assert results['unchanged_jokes'] == 1
  assert not joke1.update_calls


def test_migration_respects_max_jokes_limit(monkeypatch):
  """Test that the migration processes no more than max_jokes."""
  joke1 = _make_joke_doc('j1', {'num_saves': 10, 'num_shares': 5})
  joke2 = _make_joke_doc('j2', {'num_saves': 1, 'num_shares': 1})
  client = FakeFirestoreClient(jokes_docs=[joke1, joke2])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_popularity_score_migration(dry_run=False, max_jokes=1)

  assert results['total_jokes_processed'] == 1
  assert results['updated_jokes'] == 1
  assert len(joke1.update_calls) == 1 or len(joke2.update_calls) == 1
  if len(joke1.update_calls) == 1:
      assert not joke2.update_calls
  else:
      assert not joke1.update_calls


def test_migration_handles_multiple_jokes(monkeypatch):
  """Test that the migration correctly processes multiple jokes."""
  joke1 = _make_joke_doc('j1', {'num_saves': 10, 'num_shares': 5})
  joke2 = _make_joke_doc('j2', {'num_saves': 1, 'num_shares': 1, 'popularity_score': 6})
  joke3 = _make_joke_doc('j3', {'num_saves': 2, 'num_shares': 2})
  client = FakeFirestoreClient(jokes_docs=[joke1, joke2, joke3])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_popularity_score_migration(dry_run=False, max_jokes=0)

  assert results['total_jokes_processed'] == 3
  assert results['updated_jokes'] == 2
  assert results['unchanged_jokes'] == 1
  assert len(joke1.update_calls) == 1
  assert not joke2.update_calls
  assert len(joke3.update_calls) == 1
  assert joke1.update_calls[0] == {'popularity_score': 35}
  assert joke3.update_calls[0] == {'popularity_score': 12}
