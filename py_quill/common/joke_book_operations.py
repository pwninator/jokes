"""Operations for managing joke books (add, remove, reorder, search)."""

from common import models
from services import firestore, search
from google.cloud import firestore as google_firestore

def _get_book_ref(book_id: str) -> google_firestore.DocumentReference:
    return firestore.db().collection('joke_books').document(book_id)

def _get_book_data(book_id: str) -> dict:
    doc = _get_book_ref(book_id).get()
    if not doc.exists:
        raise ValueError(f"Joke book {book_id} not found")
    return doc.to_dict() or {}

def add_jokes_to_book(book_id: str, joke_ids: list[str]) -> None:
    """Adds multiple jokes to the end of the book if not already present."""
    if not joke_ids:
        return
    book_ref = _get_book_ref(book_id)
    # Firestore array_union adds only if unique.
    book_ref.update({'jokes': google_firestore.ArrayUnion(joke_ids)})

def remove_joke_from_book(book_id: str, joke_id: str) -> None:
    """Removes a joke from the book."""
    book_ref = _get_book_ref(book_id)
    book_ref.update({'jokes': google_firestore.ArrayRemove([joke_id])})

def reorder_joke_in_book(book_id: str, joke_id: str, new_index: int) -> None:
    """Moves a joke to a new 0-based index."""
    # This requires a read-modify-write transaction to ensure consistency
    client = firestore.db()
    book_ref = client.collection('joke_books').document(book_id)

    @google_firestore.transactional
    def _reorder_tx(transaction, ref):
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
