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

def add_joke_to_book(book_id: str, joke_id: str) -> None:
    """Adds a joke to the end of the book if not already present."""
    book_ref = _get_book_ref(book_id)

    # Use a transaction or simpler array_union if we don't care about strict ordering races
    # but for consistent lists, array_union is fine for appending.
    # However, to be safe about duplicates and potential future ordering logic,
    # let's read-modify-write or use array_union.
    # Firestore array_union adds only if unique.
    book_ref.update({'jokes': google_firestore.ArrayUnion([joke_id])})

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

def search_candidate_jokes(book_id: str, query: str, limit: int = 10) -> list[models.PunnyJoke]:
    """Search for jokes excluding ones already in the book."""
    # 1. Get current book jokes to exclude
    book_data = _get_book_data(book_id)
    existing_ids = set(book_data.get('jokes', []))

    # 2. Perform search
    # We fetch a bit more than limit in case top results are already in the book
    search_buffer = limit + len(existing_ids) + 5
    # Cap buffer to avoid fetching too many
    search_buffer = min(search_buffer, 50)

    results = search.search_jokes(
        query=query,
        limit=search_buffer,
        # minimal threshold, rely on ranking
        distance_threshold=1.0,
    )

    # 3. Filter and fetch full objects
    candidate_ids = []
    for res in results:
        if res.joke_id not in existing_ids:
            candidate_ids.append(res.joke_id)
            if len(candidate_ids) >= limit:
                break

    if not candidate_ids:
        return []

    jokes = firestore.get_punny_jokes(candidate_ids)

    # Maintain search order
    jokes_map = {j.key: j for j in jokes if j.key}
    ordered_jokes = []
    for jid in candidate_ids:
        if jid in jokes_map:
            ordered_jokes.append(jokes_map[jid])

    return ordered_jokes
