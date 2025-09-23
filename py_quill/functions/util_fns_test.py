"""Tests for jokes fields migration in util_fns.py."""

import pytest
from functions import util_fns


class FakeDoc:
  """A fake Firestore document."""

  def __init__(self,
               doc_id: str,
               data: dict | None,
               collection: 'FakeCollection' = None):
    self.id = doc_id
    self._data = data
    self.reference = self
    self.set_calls: list[dict] = []
    self._collection = collection

  def to_dict(self) -> dict | None:
    return self._data

  def get(self):
    return self

  @property
  def exists(self):
    return self._data is not None

  def set(self, data: dict) -> None:
    self.set_calls.append(dict(data))
    self._data = data
    if self._collection:
      self._collection._add_doc(self)


class FakeCollection:
  """A fake Firestore collection."""

  def __init__(self, docs: list[FakeDoc]):
    self._docs = {}
    for doc in docs:
      doc._collection = self
      self._docs[doc.id] = doc

  def stream(self) -> list[FakeDoc]:
    return list(self._docs.values())

  def document(self, doc_id: str) -> FakeDoc:
    return self._docs.get(doc_id, FakeDoc(doc_id, None, collection=self))

  def _add_doc(self, doc: FakeDoc):  # pylint: disable=protected-access
    self._docs[doc.id] = doc


class FakeFirestoreClient:
  """A fake Firestore client."""

  def __init__(self,
               jokes_docs: list[FakeDoc] | None = None,
               jokes_test_docs: list[FakeDoc] | None = None):
    self._collections = {
      'jokes': FakeCollection(jokes_docs or []),
      'jokes_test': FakeCollection(jokes_test_docs or []),
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


def test_migration_copies_joke(monkeypatch):
  """Test that a joke is copied from 'jokes' to 'jokes_test'."""
  joke1 = _make_joke_doc('j1', {'text': 'Why did the chicken cross the road?'})
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_jokes_test_migration(dry_run=False, max_jokes=0)

  assert results['migrated_jokes'] == 1
  assert results['skipped_jokes'] == 0
  new_joke = client.collection('jokes_test').document('j1').get()
  assert new_joke.exists
  assert new_joke.to_dict() == {'text': 'Why did the chicken cross the road?'}


def test_migration_removes_embedding_and_metadata(monkeypatch):
  """Test that the 'zzz_joke_text_embedding' and 'generation_metadata' fields are removed during migration."""
  joke1 = _make_joke_doc(
    'j1', {
      'text': 'A funny joke',
      'zzz_joke_text_embedding': [0.1, 0.2],
      'generation_metadata': {
        'model': 'test_model',
        'cost': 0.01
      }
    })
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  util_fns.run_jokes_test_migration(dry_run=False, max_jokes=0)

  new_joke = client.collection('jokes_test').document('j1').get()
  assert new_joke.exists
  assert 'zzz_joke_text_embedding' not in new_joke.to_dict()
  assert 'generation_metadata' not in new_joke.to_dict()
  assert new_joke.to_dict() == {'text': 'A funny joke'}


def test_migration_removes_generation_metadata_only(monkeypatch):
  """Test that only the 'generation_metadata' field is removed when present."""
  joke1 = _make_joke_doc(
    'j1', {
      'text': 'A funny joke',
      'generation_metadata': {
        'model': 'test_model',
        'cost': 0.01,
        'tokens': 100
      },
      'other_field': 'should_be_preserved'
    })
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  util_fns.run_jokes_test_migration(dry_run=False, max_jokes=0)

  new_joke = client.collection('jokes_test').document('j1').get()
  assert new_joke.exists
  assert 'generation_metadata' not in new_joke.to_dict()
  assert new_joke.to_dict() == {
    'text': 'A funny joke',
    'other_field': 'should_be_preserved'
  }


def test_migration_skips_existing_joke(monkeypatch):
  """Test that a joke is skipped if it already exists in 'jokes_test'."""
  joke1 = _make_joke_doc('j1', {'text': 'This is a joke'})
  existing_joke = _make_joke_doc('j1', {'text': 'I already exist'})
  client = FakeFirestoreClient(jokes_docs=[joke1],
                               jokes_test_docs=[existing_joke])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_jokes_test_migration(dry_run=False, max_jokes=0)

  assert results['migrated_jokes'] == 0
  assert results['skipped_jokes'] == 1
  joke_in_test = client.collection('jokes_test').document('j1').get()
  assert len(joke_in_test.set_calls) == 0  # No set call should be made
  assert joke_in_test.to_dict() == {'text': 'I already exist'}


def test_migration_dry_run_does_not_write(monkeypatch):
  """Test that dry_run=True prevents any writes to the 'jokes_test' collection."""
  joke1 = _make_joke_doc('j1', {'text': 'A test joke'})
  client = FakeFirestoreClient(jokes_docs=[joke1])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_jokes_test_migration(dry_run=True, max_jokes=0)

  assert results['migrated_jokes'] == 0
  # In dry run, un-migrated jokes are considered skipped
  assert results['skipped_jokes'] == 1
  new_joke = client.collection('jokes_test').document('j1').get()
  assert not new_joke.exists


def test_migration_respects_max_jokes_limit(monkeypatch):
  """Test that the migration processes no more than max_jokes."""
  joke1 = _make_joke_doc('j1', {'text': 'joke 1'})
  joke2 = _make_joke_doc('j2', {'text': 'joke 2'})
  client = FakeFirestoreClient(jokes_docs=[joke1, joke2])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_jokes_test_migration(dry_run=False, max_jokes=1)

  assert results['total_jokes_processed'] == 1
  assert results['migrated_jokes'] == 1
  assert results['skipped_jokes'] == 0
  # Check that only one joke was migrated
  j1_in_test = client.collection('jokes_test').document('j1').get()
  j2_in_test = client.collection('jokes_test').document('j2').get()
  assert j1_in_test.exists != j2_in_test.exists  # XOR


def test_migration_handles_multiple_jokes_and_skips(monkeypatch):
  """Test a mixed scenario with jokes to migrate and jokes to skip."""
  # Joke to be migrated
  joke1 = _make_joke_doc('j1', {'text': 'new joke 1'})
  # Joke to be skipped
  joke2 = _make_joke_doc('j2', {'text': 'new joke 2'})
  existing_joke2 = _make_joke_doc('j2', {'text': 'old joke 2'})
  # Joke to be migrated with embedding and metadata
  joke3 = _make_joke_doc(
    'j3', {
      'text': 'new joke 3',
      'zzz_joke_text_embedding': [0.3, 0.4],
      'generation_metadata': {
        'model': 'test_model',
        'cost': 0.02
      }
    })

  client = FakeFirestoreClient(jokes_docs=[joke1, joke2, joke3],
                               jokes_test_docs=[existing_joke2])
  monkeypatch.setattr(util_fns, 'db', lambda: client)

  results = util_fns.run_jokes_test_migration(dry_run=False, max_jokes=0)

  assert results['total_jokes_processed'] == 3
  assert results['migrated_jokes'] == 2
  assert results['skipped_jokes'] == 1

  # Check j1
  j1_migrated = client.collection('jokes_test').document('j1').get()
  assert j1_migrated.exists
  assert j1_migrated.to_dict() == {'text': 'new joke 1'}

  # Check j2 (was skipped, not overwritten)
  j2_skipped = client.collection('jokes_test').document('j2').get()
  assert j2_skipped.exists
  assert j2_skipped.to_dict() == {'text': 'old joke 2'}
  assert len(j2_skipped.set_calls) == 0

  # Check j3
  j3_migrated = client.collection('jokes_test').document('j3').get()
  assert j3_migrated.exists
  assert j3_migrated.to_dict() == {'text': 'new joke 3'}
  assert 'zzz_joke_text_embedding' not in j3_migrated.to_dict()
  assert 'generation_metadata' not in j3_migrated.to_dict()
