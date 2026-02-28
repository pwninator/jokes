"""Tests for joke_books_firestore storage helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from google.cloud.firestore import ArrayUnion

from common import models
from storage import joke_books_firestore


class _DummyDoc:

  def __init__(self,
               doc_id: str,
               data: dict[str, object],
               exists: bool = True):
    self.id = doc_id
    self._data = data
    self.exists = exists

  def to_dict(self):
    return self._data


def test_list_joke_books_returns_models_sorted(monkeypatch):
  docs = [
    _DummyDoc('b', {
      'book_name': 'Zoo',
      'jokes': ['j2'],
    }),
    _DummyDoc(
      'a', {
        'book_name': 'Alpha',
        'jokes': ['j1', 'j3'],
        'zip_url': 'https://cdn/book.zip',
      }),
  ]
  collection = MagicMock()
  collection.stream.return_value = docs
  monkeypatch.setattr(joke_books_firestore, '_book_collection',
                      lambda: collection)

  books = joke_books_firestore.list_joke_books()

  assert [book.id for book in books] == ['a', 'b']
  assert books[0].book_name == 'Alpha'
  assert books[0].joke_count == 2
  assert books[0].zip_url == 'https://cdn/book.zip'


def test_create_and_update_export_files_use_joke_book_model(monkeypatch):
  book_ref = MagicMock()
  monkeypatch.setattr(joke_books_firestore, '_book_ref',
                      lambda _book_id: book_ref)
  monkeypatch.setattr(
    joke_books_firestore,
    'get_joke_book',
    lambda book_id: models.JokeBook(
      id=book_id, book_name='My Book', jokes=['j1']),
  )

  created = joke_books_firestore.create_joke_book(
    models.JokeBook(
      id='book-1',
      book_name='My Book',
      jokes=['j1'],
      zip_url='https://cdn/old.zip',
    ))
  updated = joke_books_firestore.update_joke_book_export_files(
    'book-1',
    zip_url='https://cdn/new.zip',
    paperback_pdf_url='https://cdn/new.pdf',
  )

  book_ref.set.assert_called_once_with({
    'book_name': 'My Book',
    'jokes': ['j1'],
    'belongs_to_page_gcs_uri': None,
    'zip_url': 'https://cdn/old.zip',
    'paperback_pdf_url': None,
  })
  book_ref.update.assert_called_once_with({
    'zip_url':
    'https://cdn/new.zip',
    'paperback_pdf_url':
    'https://cdn/new.pdf',
  })
  assert created.id == 'book-1'
  assert updated.paperback_pdf_url == 'https://cdn/new.pdf'


def test_update_joke_book_belongs_to_page_updates_model(monkeypatch):
  book_ref = MagicMock()
  monkeypatch.setattr(joke_books_firestore, '_book_ref',
                      lambda _book_id: book_ref)
  monkeypatch.setattr(
    joke_books_firestore,
    'get_joke_book',
    lambda book_id: models.JokeBook(id=book_id, book_name='My Book'),
  )

  updated = joke_books_firestore.update_joke_book_belongs_to_page(
    'book-1',
    belongs_to_page_gcs_uri='gs://images/_joke_assets/book/belongs.png',
  )

  book_ref.update.assert_called_once_with({
    'belongs_to_page_gcs_uri': 'gs://images/_joke_assets/book/belongs.png',
  })
  assert updated.belongs_to_page_gcs_uri == (
    'gs://images/_joke_assets/book/belongs.png')


def test_update_book_page_selection_updates_metadata(monkeypatch):
  metadata_ref = MagicMock()
  monkeypatch.setattr(joke_books_firestore, '_metadata_ref',
                      lambda _joke_id: metadata_ref)
  monkeypatch.setattr(
    joke_books_firestore,
    'get_joke_book',
    lambda _book_id: models.JokeBook(id='book-1', jokes=['joke-1']),
  )
  monkeypatch.setattr(
    joke_books_firestore,
    'get_joke_metadata',
    lambda _joke_id: {
      'book_page_setup_image_url': 'https://old/setup.png',
      'book_page_punchline_image_url': 'https://old/punch.png',
    },
  )
  expected_updates = {
    'book_page_setup_image_url': 'https://new/setup.png',
    'book_page_punchline_image_url': 'https://old/punch.png',
  }
  prepare_mock = MagicMock(return_value=expected_updates)
  monkeypatch.setattr(models.PunnyJoke, 'prepare_book_page_metadata_updates',
                      prepare_mock)

  setup_url, punchline_url = joke_books_firestore.update_book_page_selection(
    book_id='book-1',
    joke_id='joke-1',
    new_setup_url='https://new/setup.png',
  )

  prepare_mock.assert_called_once_with(
    {
      'book_page_setup_image_url': 'https://old/setup.png',
      'book_page_punchline_image_url': 'https://old/punch.png',
    },
    'https://new/setup.png',
    'https://old/punch.png',
  )
  metadata_ref.set.assert_called_once_with(expected_updates, merge=True)
  assert setup_url == 'https://new/setup.png'
  assert punchline_url == 'https://old/punch.png'


def test_promote_and_persist_uploaded_images_update_joke_docs(monkeypatch):
  joke_ref = MagicMock()
  metadata_ref = MagicMock()
  metadata_ref.get.return_value = MagicMock(exists=True)
  monkeypatch.setattr(joke_books_firestore, '_joke_ref',
                      lambda _joke_id: joke_ref)
  monkeypatch.setattr(joke_books_firestore, '_metadata_ref',
                      lambda _joke_id: metadata_ref)
  monkeypatch.setattr(
    joke_books_firestore,
    'get_joke_book',
    lambda _book_id: models.JokeBook(id='book-1', jokes=['joke-1']),
  )
  monkeypatch.setattr(
    joke_books_firestore,
    'get_joke_metadata',
    lambda _joke_id: {
      'book_page_setup_image_url': 'https://cdn/book-setup.png',
    },
  )

  promoted_url = joke_books_firestore.promote_book_page_image_to_main(
    book_id='book-1',
    joke_id='joke-1',
    target='setup',
  )
  joke_books_firestore.persist_uploaded_joke_image(
    joke_id='joke-1',
    book_id='book-1',
    target_field='book_page_setup_image_url',
    public_url='https://cdn/custom.png',
  )
  joke_books_firestore.persist_uploaded_joke_image(
    joke_id='joke-1',
    book_id='manual',
    target_field='punchline_image_url',
    public_url='https://cdn/main.png',
  )

  promote_update = joke_ref.update.call_args_list[0].args[0]
  assert promote_update['setup_image_url'] == 'https://cdn/book-setup.png'
  assert isinstance(promote_update['all_setup_image_urls'], ArrayUnion)
  assert promote_update['setup_image_url_upscaled'] is None
  metadata_ref.update.assert_called_once_with({
    'book_page_setup_image_url':
    'https://cdn/custom.png',
    'all_book_page_setup_image_urls':
    ArrayUnion(['https://cdn/custom.png']),
  })
  assert joke_ref.update.call_args_list[1].args[0] == {
    'punchline_image_url': 'https://cdn/main.png'
  }
  assert promoted_url == 'https://cdn/book-setup.png'
