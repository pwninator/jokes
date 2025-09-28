"""Joke book cloud functions."""
import traceback

from common import joke_operations
from common.utils import create_timestamped_firestore_key
from firebase_functions import https_fn, options
from functions.function_utils import (error_response, get_param, get_user_id,
                                      success_response)
from services import firestore


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def create_book(req: https_fn.Request) -> https_fn.Response:
  """Create a new joke book from a list of jokes."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method != 'POST':
      return error_response(f'Method not allowed: {req.method}')

    user_id = get_user_id(req)
    if not user_id:
      return error_response('User not authenticated')

    joke_ids = get_param(req, 'joke_ids')
    book_name = get_param(req, 'book_name')

    if joke_ids is None:
      return error_response('joke_ids is required')
    if not book_name:
      return error_response('book_name is required')

    for joke_id in joke_ids:
      joke_operations.upscale_joke(joke_id)

    doc_id = create_timestamped_firestore_key(user_id)
    firestore.db().collection('joke_books').document(doc_id).set({
      'book_name':
      book_name,
      'jokes':
      joke_ids,
    })

    return success_response({'book_id': doc_id})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke book: {str(e)}')
