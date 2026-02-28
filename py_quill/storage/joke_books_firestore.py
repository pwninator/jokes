"""Firestore persistence helpers for joke books."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from common import models
from google.cloud.firestore import (ArrayUnion, Client, CollectionReference,
                                    DocumentReference, DocumentSnapshot)
from services import firestore as firestore_service

_JOKE_BOOKS_COLLECTION = 'joke_books'
_JOKES_COLLECTION = 'jokes'
_METADATA_SUBCOLLECTION = 'metadata'
_METADATA_DOCUMENT = 'metadata'


def _book_collection() -> CollectionReference:
  return firestore_service.db().collection(_JOKE_BOOKS_COLLECTION)


def _joke_collection() -> CollectionReference:
  return firestore_service.db().collection(_JOKES_COLLECTION)


def _book_ref(book_id: str) -> DocumentReference:
  return _book_collection().document(book_id)


def _joke_ref(joke_id: str) -> DocumentReference:
  return _joke_collection().document(joke_id)


def _metadata_ref(joke_id: str) -> DocumentReference:
  return cast(
    DocumentReference,
    _joke_ref(joke_id).collection(_METADATA_SUBCOLLECTION).document(
      _METADATA_DOCUMENT),
  )


def _doc_dict(snapshot: DocumentSnapshot) -> dict[str, Any]:
  """Return snapshot data as a plain dict."""
  data = snapshot.to_dict()
  if not isinstance(data, dict):
    return {}
  return data


def _string_list(value: object) -> list[str]:
  """Return a filtered list of strings."""
  if not isinstance(value, list):
    return []
  return [item for item in cast(list[object], value) if isinstance(item, str)]


def _get_required_book(book_id: str) -> models.JokeBook:
  book = get_joke_book(book_id)
  if not book:
    raise ValueError(f'Joke book {book_id} not found')
  return book


def _require_book_contains_joke(book: models.JokeBook, joke_id: str) -> None:
  if book.jokes and joke_id not in book.jokes:
    raise ValueError(f'Joke {joke_id} does not belong to book {book.id}')


def list_joke_books() -> list[models.JokeBook]:
  """Return all joke books sorted for admin display."""
  books: list[models.JokeBook] = []
  docs = cast(Iterable[DocumentSnapshot], _book_collection().stream())
  for doc in docs:
    if not doc.exists:
      continue
    doc_id = cast(str, doc.id)
    books.append(
      models.JokeBook.from_firestore_dict(
        _doc_dict(doc),
        key=doc_id,
      ))
  books.sort(key=lambda book: str(book.book_name or book.id or ''))
  return books


def get_joke_book(book_id: str) -> models.JokeBook | None:
  """Return one joke book, or None if missing."""
  book_id = (book_id or '').strip()
  if not book_id:
    return None
  doc = _book_ref(book_id).get()
  if not doc.exists:
    return None
  doc_id = cast(str, doc.id)
  return models.JokeBook.from_firestore_dict(
    _doc_dict(doc),
    key=doc_id,
  )


def create_joke_book(book: models.JokeBook) -> models.JokeBook:
  """Create or replace a joke book document."""
  if not book.id:
    raise ValueError('JokeBook.id is required')
  _ = _book_ref(book.id).set(book.to_dict())
  return book


def update_joke_book_export_files(
  book_id: str,
  *,
  zip_url: str,
  paperback_pdf_url: str,
) -> models.JokeBook:
  """Update stored export file URLs for a joke book."""
  book = _get_required_book(book_id)
  _ = _book_ref(book_id).update({
    'zip_url': zip_url,
    'paperback_pdf_url': paperback_pdf_url,
  })
  book.zip_url = zip_url
  book.paperback_pdf_url = paperback_pdf_url
  return book


def get_joke_book_detail_raw(
  book_id: str, ) -> tuple[models.JokeBook | None, list[dict[str, Any]]]:
  """Fetch a joke book plus ordered joke docs and metadata for admin rendering."""
  book = get_joke_book(book_id)
  if not book:
    return None, []

  if not book.jokes:
    return book, []

  client: Client = firestore_service.db()
  refs = [_joke_collection().document(joke_id) for joke_id in book.jokes]
  docs = cast(Iterable[DocumentSnapshot], client.get_all(refs))
  id_to_joke: dict[str, dict[str, Any]] = {}
  for doc in docs:
    if not doc.exists:
      continue
    id_to_joke[doc.id] = _doc_dict(doc)

  entries: list[dict[str, Any]] = []
  for joke_id in book.jokes:
    entries.append({
      'id': joke_id,
      'joke': id_to_joke.get(joke_id, {}),
      'metadata': get_joke_metadata(joke_id),
    })
  return book, entries


def get_joke_metadata(joke_id: str) -> dict[str, Any]:
  """Fetch the metadata doc for a joke, or {} if missing."""
  joke_id = (joke_id or '').strip()
  if not joke_id:
    return {}
  doc = _metadata_ref(joke_id).get()
  if not doc.exists:
    return {}
  return _doc_dict(doc)


def get_joke_with_metadata(
  joke_id: str, ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
  """Fetch a joke document and its metadata sub-document."""
  joke_id = (joke_id or '').strip()
  if not joke_id:
    return None, {}
  joke_doc = _joke_ref(joke_id).get()
  if not joke_doc.exists:
    return None, {}
  joke_data = _doc_dict(joke_doc)
  return joke_data, get_joke_metadata(joke_id)


def get_book_page_spread_urls(
  book_id: str, ) -> tuple[models.JokeBook | None, list[str], list[str]]:
  """Return ordered setup/punchline book-page URLs for the given book."""
  book = get_joke_book(book_id)
  if not book:
    return None, [], []

  setup_pages: list[str] = []
  punchline_pages: list[str] = []
  for joke_id in book.jokes:
    metadata = get_joke_metadata(joke_id)
    setup_img = metadata.get('book_page_setup_image_url')
    punchline_img = metadata.get('book_page_punchline_image_url')
    if not isinstance(setup_img, str) or not setup_img:
      raise ValueError(f'Joke {joke_id} does not have book page images')
    if not isinstance(punchline_img, str) or not punchline_img:
      raise ValueError(f'Joke {joke_id} does not have book page images')
    setup_pages.append(setup_img)
    punchline_pages.append(punchline_img)
  return book, setup_pages, punchline_pages


def update_book_page_selection(
  *,
  book_id: str,
  joke_id: str,
  new_setup_url: str | None = None,
  new_punchline_url: str | None = None,
  remove_setup_url: str | None = None,
  remove_punchline_url: str | None = None,
) -> tuple[str | None, str | None]:
  """Update selected book-page URLs for a joke within a joke book."""
  book = _get_required_book(book_id)
  _require_book_contains_joke(book, joke_id)

  metadata = get_joke_metadata(joke_id)
  current_setup = metadata.get('book_page_setup_image_url')
  current_punchline = metadata.get('book_page_punchline_image_url')

  if new_setup_url or new_punchline_url:
    resolved_setup = new_setup_url or (current_setup if isinstance(
      current_setup, str) else None)
    resolved_punchline = new_punchline_url or (current_punchline if isinstance(
      current_punchline, str) else None)
    if not resolved_setup or not resolved_punchline:
      raise ValueError('Both book page images must be set')
    updates = models.PunnyJoke.prepare_book_page_metadata_updates(
      metadata,
      resolved_setup,
      resolved_punchline,
    )
  else:
    updates: dict[str, object] = {}

    if remove_setup_url:
      setup_history = _string_list(
        metadata.get('all_book_page_setup_image_urls'))
      filtered_setup = [
        url for url in setup_history if url != remove_setup_url
      ]
      updates['all_book_page_setup_image_urls'] = filtered_setup
      if current_setup == remove_setup_url:
        updates['book_page_setup_image_url'] = (filtered_setup[0]
                                                if filtered_setup else None)

    if remove_punchline_url:
      punchline_history = _string_list(
        metadata.get('all_book_page_punchline_image_urls'))
      filtered_punchline = [
        url for url in punchline_history if url != remove_punchline_url
      ]
      updates['all_book_page_punchline_image_urls'] = filtered_punchline
      if current_punchline == remove_punchline_url:
        updates['book_page_punchline_image_url'] = (
          filtered_punchline[0] if filtered_punchline else None)

  _ = _metadata_ref(joke_id).set(updates, merge=True)
  return (
    cast(str | None, updates.get('book_page_setup_image_url', current_setup)),
    cast(str | None,
         updates.get('book_page_punchline_image_url', current_punchline)),
  )


def promote_book_page_image_to_main(
  *,
  book_id: str,
  joke_id: str,
  target: str,
) -> str:
  """Promote the selected book-page image to the main joke image."""
  if target not in {'setup', 'punchline'}:
    raise ValueError('target must be setup or punchline')

  book = _get_required_book(book_id)
  _require_book_contains_joke(book, joke_id)

  metadata = get_joke_metadata(joke_id)
  page_field = ('book_page_setup_image_url'
                if target == 'setup' else 'book_page_punchline_image_url')
  page_url = metadata.get(page_field)
  if not isinstance(page_url, str) or not page_url:
    raise ValueError('Book page image not found')

  main_field = 'setup_image_url' if target == 'setup' else 'punchline_image_url'
  history_field = ('all_setup_image_urls'
                   if target == 'setup' else 'all_punchline_image_urls')
  upscaled_field = ('setup_image_url_upscaled'
                    if target == 'setup' else 'punchline_image_url_upscaled')

  _ = _joke_ref(joke_id).update({
    main_field: page_url,
    history_field: ArrayUnion([page_url]),
    upscaled_field: None,
  })
  return page_url


def persist_uploaded_joke_image(
  *,
  joke_id: str,
  book_id: str | None,
  target_field: str,
  public_url: str,
) -> None:
  """Persist an uploaded custom image URL for a joke or its book-page metadata."""
  if target_field.startswith('book_page') and book_id and book_id != 'manual':
    book = _get_required_book(book_id)
    _require_book_contains_joke(book, joke_id)

  if target_field.startswith('book_page'):
    metadata_doc = _metadata_ref(joke_id)
    variant_field = f'all_{target_field}s'
    metadata_snapshot = metadata_doc.get()
    if not metadata_snapshot.exists:
      _ = metadata_doc.set({})
    _ = metadata_doc.update({
      target_field: public_url,
      variant_field: ArrayUnion([public_url]),
    })
    return

  _ = _joke_ref(joke_id).update({target_field: public_url})
