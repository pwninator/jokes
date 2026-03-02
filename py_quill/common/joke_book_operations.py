"""Operations for managing joke books (add, remove, reorder, search)."""

from typing import cast

from google.cloud import firestore as google_firestore
from services import firestore


def _get_book_ref(book_id: str) -> google_firestore.DocumentReference:
  return firestore.db().collection('joke_books').document(book_id)


def add_jokes_to_book(book_id: str, joke_ids: list[str]) -> None:
  """Adds multiple jokes to the end of the book if not already present.

    Verifies that jokes do not already belong to another book.
    Updates each joke's book_id field.
    """
  if not joke_ids:
    return

  client = firestore.db()

  # 1. Verify all jokes
  # We can fetch them in a batch or one by one. Batch is better but has limits (usually 10-30 in this context is fine).
  # Since we need to read and then update, and we want to ensure consistency, we should ideally verify first.

  joke_refs = [client.collection('jokes').document(jid) for jid in joke_ids]
  snapshots = client.get_all(joke_refs)

  valid_joke_ids: list[str] = []

  for snap in snapshots:
    if not snap.exists:
      # Skip missing jokes or raise error?
      # Assuming we skip or fail. Let's just skip for now, but usually UI sends valid IDs.
      continue

    data = snap.to_dict() or {}
    current_book_id = data.get('book_id')

    if current_book_id and current_book_id != book_id:
      raise ValueError(
        f"Joke {snap.id} already belongs to book {current_book_id}")

    valid_joke_ids.append(cast(str, snap.id))

  if not valid_joke_ids:
    return

  # 2. Add to book doc
  book_ref = _get_book_ref(book_id)
  _ = book_ref.update({'jokes': google_firestore.ArrayUnion(valid_joke_ids)})

  # 3. Update individual joke docs
  batch = client.batch()
  for jid in valid_joke_ids:
    joke_ref = client.collection('jokes').document(jid)
    batch.update(joke_ref, {'book_id': book_id})

  batch.commit()  # pyright: ignore[reportUnusedCallResult]


def remove_joke_from_book(book_id: str, joke_id: str) -> None:
  """Removes a joke from the book.

    Verifies that the joke belongs to this book (or no book).
    Updates the joke's book_id field to delete it.
    """
  client = firestore.db()
  joke_ref = client.collection('jokes').document(joke_id)
  joke_snap = joke_ref.get()

  if joke_snap.exists:
    data = joke_snap.to_dict() or {}
    current_book_id = data.get('book_id')
    if current_book_id and current_book_id != book_id:
      raise ValueError(
        f"Joke {joke_id} belongs to book {current_book_id}, cannot remove from {book_id}"
      )

  # Remove from book doc
  book_ref = _get_book_ref(book_id)
  _ = book_ref.update({'jokes': google_firestore.ArrayRemove([joke_id])})

  # Update joke doc
  if joke_snap.exists:
    _ = joke_ref.update({'book_id': google_firestore.DELETE_FIELD})


def reorder_joke_in_book(book_id: str, joke_id: str, new_index: int) -> None:
  """Moves a joke to a new 0-based index."""
  # This requires a read-modify-write transaction to ensure consistency
  client = firestore.db()
  book_ref = client.collection('joke_books').document(book_id)

  @google_firestore.transactional
  def _reorder_tx(
    transaction: google_firestore.Transaction,
    ref: google_firestore.DocumentReference,
  ):
    snapshot = ref.get(transaction=transaction)
    if not snapshot.exists:
      raise ValueError(f"Joke book {book_id} not found")

    data = snapshot.to_dict() or {}
    jokes = data.get('jokes', [])

    if joke_id not in jokes:
      # If joke isn't in book, we can't reorder it.
      # Optionally raise error or ignore.
      raise ValueError(f"Joke {joke_id} not in book {book_id}")

    current_index = jokes.index(joke_id)
    if current_index == new_index:
      return

    # Remove from old position
    jokes.pop(current_index)

    # Insert at new position
    # Clamp index to bounds
    target_index = max(0, min(new_index, len(jokes)))
    jokes.insert(target_index, joke_id)

    transaction.update(ref, {'jokes': jokes})

  transaction = client.transaction()
  _reorder_tx(transaction, book_ref)
