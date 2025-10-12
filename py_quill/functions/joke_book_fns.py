"""Joke book cloud functions."""
import traceback

from common import joke_operations, models, utils
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

    doc_id = utils.create_timestamped_firestore_key(user_id)
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


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=60,
)
def get_joke_book(req: https_fn.Request) -> https_fn.Response:
  """Gets a joke book and returns it as an HTML page."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    joke_book_id = get_param(req, 'joke_book_id')
    if not joke_book_id:
      # Also support path-based IDs for simpler URLs
      path_parts = req.path.split('/')
      if len(path_parts) > 1 and path_parts[-1]:
        joke_book_id = path_parts[-1]

    if not joke_book_id:
      return error_response('joke_book_id is required')

    book_ref = firestore.db().collection('joke_books').document(joke_book_id)
    book_doc = book_ref.get()

    if not book_doc.exists:
      return https_fn.Response("Book not found", status=404)

    book_data = book_doc.to_dict()
    book_title = book_data.get('book_name', 'My Joke Book')
    joke_ids = book_data.get('jokes', [])

    jokes: list[models.PunnyJoke] = []
    for joke_id in joke_ids:
      joke_ref = firestore.db().collection('jokes').document(joke_id)
      joke_doc = joke_ref.get()
      if joke_doc.exists:
        jokes.append(
          models.PunnyJoke.from_firestore_dict(joke_doc.to_dict(), joke_id))

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{book_title}</title>
        <style>
            body {{ font-family: sans-serif; margin: 2em; }}
            img {{ max-width: 400px; display: block; margin-bottom: 1em; }}
            hr {{ margin: 2em 0; }}
        </style>
    </head>
    <body>
        <h1>{book_title}</h1>
    """

    for joke in jokes:
      setup_img = joke.setup_image_url_upscaled
      punchline_img = joke.punchline_image_url_upscaled
      if setup_img:
        setup_img = utils.format_image_url(
          setup_img,
          image_format='png',
          quality=100,
        )
        html_content += f'<img src="{setup_img}" alt="Joke Setup"><br>'
      if punchline_img:
        punchline_img = utils.format_image_url(
          punchline_img,
          image_format='png',
          quality=100,
        )
        html_content += f'<img src="{punchline_img}" alt="Joke Punchline"><br>'
      html_content += "<hr>"

    html_content += """
    </body>
    </html>
    """

    return https_fn.Response(html_content,
                             status=200,
                             headers={'Content-Type': 'text/html'})

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error getting joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to get joke book: {str(e)}')
