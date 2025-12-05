"""Joke book cloud functions."""
import json
import traceback

from common import image_operations, utils
from firebase_functions import https_fn, logger, options
from functions.function_utils import (error_response, get_param, get_user_id,
                                      success_response)
from services import firestore

NUM_TOP_JOKES_FOR_BOOKS = 50
_CORS_HEADERS = {
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
}


def _allowed_origins() -> set[str]:
  """Return allowed origins based on environment (emulator vs prod)."""
  if utils.is_emulator():
    return {
      "http://127.0.0.1:5000",
      "http://localhost:5000",
      "http://127.0.0.1",
      "http://localhost",
    }
  else:
    return {
      "https://snickerdoodlejokes.com",
    }


def _cors_headers_for_origin(request_origin: str | None) -> dict[str, str]:
  """Return CORS headers only for allowed origins."""
  if request_origin and request_origin.rstrip("/") in _allowed_origins():
    return {**_CORS_HEADERS, "Access-Control-Allow-Origin": request_origin}
  return {}


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def generate_joke_book_page(req: https_fn.Request) -> https_fn.Response:
  """Generate book page images for a joke."""
  try:
    cors_headers = _cors_headers_for_origin(req.headers.get("Origin"))

    if req.method == "OPTIONS":
      return https_fn.Response("", status=204, headers=cors_headers)

    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200, headers=cors_headers)

    if req.method not in ['GET', 'POST']:
      return https_fn.Response(
        json.dumps(error_response(f'Method not allowed: {req.method}')),
        status=405,
        headers=cors_headers,
      )

    joke_id = get_param(req, 'joke_id', required=True)
    setup_instructions = get_param(req, 'setup_instructions', required=False)
    punchline_instructions = get_param(req,
                                       'punchline_instructions',
                                       required=False)

    logger.info(f'Generating book page images for joke {joke_id}')

    (
      setup_image,
      punchline_image,
    ) = image_operations.generate_and_populate_book_pages(
      joke_id,
      overwrite=True,
      additional_setup_instructions=setup_instructions,
      additional_punchline_instructions=punchline_instructions,
    )

    return_val = f"""
  <html>
  <head>
    <title>Joke Book Page - {joke_id}</title>
  </head>
  <body>
    <h1>Joke Book Page - {joke_id}</h1>
    <img src="{setup_image.url}" alt="Book Page Setup Image" width="600" height="600" />
    <img src="{punchline_image.url}" alt="Book Page Punchline Image" width="600" height="600" />
  </body>
  </html>
  """
    return https_fn.Response(return_val, status=200, headers=cors_headers)
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke book: {e}\nStacktrace:\n{stacktrace}")
    return https_fn.Response(
      json.dumps(error_response(f'Failed to create joke book: {str(e)}')),
      status=500,
      headers=cors_headers,
    )


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def create_joke_book(req: https_fn.Request) -> https_fn.Response:
  """Create a new joke book from a list of jokes."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    user_id = get_user_id(req)
    if not user_id:
      return error_response('User not authenticated')

    raw_joke_ids = get_param(req, 'joke_ids')
    book_name = get_param(req, 'book_name')

    if not book_name:
      return error_response('book_name is required')

    if raw_joke_ids is None:
      top_jokes = firestore.get_top_jokes(
        'popularity_score_recent',
        NUM_TOP_JOKES_FOR_BOOKS,
      )
      joke_ids = [joke.key for joke in top_jokes if getattr(joke, 'key', None)]
      if not joke_ids:
        return error_response('No jokes available to create joke book')
    else:
      joke_ids = raw_joke_ids

    logger.info(f'Creating book {book_name} with jokes: {joke_ids}')

    for joke_id in joke_ids:
      image_operations.generate_and_populate_book_pages(joke_id,
                                                        overwrite=True)

    # Generate ZIP of all book pages and store in temp files bucket
    zip_url = image_operations.zip_joke_page_images_for_kdp(joke_ids)

    doc_id = utils.create_timestamped_firestore_key(user_id)
    firestore.db().collection('joke_books').document(doc_id).set({
      'book_name':
      book_name,
      'jokes':
      joke_ids,
      'zip_url':
      zip_url,
    })

    return success_response({'book_id': doc_id})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke book: {str(e)}')


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def update_joke_book_zip(req: https_fn.Request) -> https_fn.Response:
  """Regenerate the ZIP of KDP-ready pages for a joke book."""
  try:
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['POST']:
      return error_response(f'Method not allowed: {req.method}')

    joke_book_id = _get_joke_book_id_from_request(req)
    if not joke_book_id:
      return error_response('joke_book_id is required')

    client = firestore.db()
    book_ref = client.collection('joke_books').document(joke_book_id)
    book_doc = book_ref.get()
    if not getattr(book_doc, 'exists', False):
      return error_response('Joke book not found')

    book_data = book_doc.to_dict() or {}
    joke_ids = book_data.get('jokes') or []
    if not isinstance(joke_ids, list) or not joke_ids:
      return error_response('Joke book has no jokes to zip')

    zip_url = image_operations.zip_joke_page_images_for_kdp(joke_ids)
    book_ref.update({'zip_url': zip_url})

    return success_response({
      'book_id': joke_book_id,
      'zip_url': zip_url,
    })
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error updating joke book ZIP: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to update joke book ZIP: {str(e)}')


def _get_joke_book_id_from_request(req: https_fn.Request) -> str | None:
  """Extract the joke_book_id from query params or path."""
  joke_book_id = get_param(req, 'joke_book_id')
  if not joke_book_id:
    # Also support path-based IDs for simpler URLs
    path_parts = req.path.split('/')
    if len(path_parts) > 1 and path_parts[-1]:
      joke_book_id = path_parts[-1]
  return joke_book_id


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

    joke_book_id = _get_joke_book_id_from_request(req)

    if not joke_book_id:
      return error_response('joke_book_id is required')

    book_ref = firestore.db().collection('joke_books').document(joke_book_id)
    book_doc = book_ref.get()

    if not book_doc.exists:
      return https_fn.Response("Book not found", status=404)

    book_data = book_doc.to_dict()
    book_title = book_data.get('book_name', 'My Joke Book')
    joke_ids = book_data.get('jokes', [])
    zip_url = book_data.get('zip_url')

    # Collect ordered page image URLs for spreads
    setup_pages: list[str] = []
    punchline_pages: list[str] = []

    for joke_id in joke_ids:
      joke_ref = firestore.db().collection('jokes').document(joke_id)
      joke_doc = joke_ref.get()
      if not joke_doc.exists:
        continue

      metadata_ref = joke_ref.collection('metadata').document('metadata')
      metadata_doc = metadata_ref.get()
      setup_img = None
      punchline_img = None
      if metadata_doc.exists:
        metadata = metadata_doc.to_dict() or {}
        setup_img = metadata.get('book_page_setup_image_url')
        punchline_img = metadata.get('book_page_punchline_image_url')

      if not setup_img or not punchline_img:
        return error_response(f'Joke {joke_id} does not have book page images')

      setup_pages.append(str(setup_img))
      punchline_pages.append(str(punchline_img))

    download_link_html = ""
    if zip_url:
      download_link_html = (
        f'<p><a href="{zip_url}" download>Download All Pages (ZIP)</a></p>')

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{book_title}</title>
        <style>
            body {{ font-family: sans-serif; margin: 2em; }}
            .spreads {{
              display: flex;
              flex-direction: column;
              gap: 16px;
            }}
            .spread-row {{
              display: flex;
              width: 100%;
            }}
            .page {{
              flex: 1 1 50%;
              margin: 0;
              padding: 0;
            }}
            .page-image {{
              display: block;
              width: 100%;
              height: auto;
              margin: 0;
              padding: 0;
            }}
            .page-empty {{
              background: #f4f4f4;
            }}
        </style>
    </head>
    <body>
        <h1>{book_title}</h1>
        {download_link_html}
        <section class="spreads">
    """

    num_jokes = len(setup_pages)
    if num_jokes:
      # First spread: only right page (setup of first joke)
      first_setup = utils.format_image_url(
        setup_pages[0],
        image_format='png',
        quality=100,
      )
      html_content += f"""
          <div class="spread-row">
            <div class="page page-left page-empty"></div>
            <div class="page page-right">
              <img src="{first_setup}" alt="Joke 1 Setup" class="page-image" />
            </div>
          </div>
      """

      # Middle spreads: left = punchline of previous, right = setup of current
      for index in range(1, num_jokes):
        left_src = utils.format_image_url(
          punchline_pages[index - 1],
          image_format='png',
          quality=100,
        )
        right_src = utils.format_image_url(
          setup_pages[index],
          image_format='png',
          quality=100,
        )
        html_content += f"""
          <div class="spread-row">
            <div class="page page-left">
              <img src="{left_src}" alt="Joke {index} Punchline" class="page-image" />
            </div>
            <div class="page page-right">
              <img src="{right_src}" alt="Joke {index + 1} Setup" class="page-image" />
            </div>
          </div>
      """

      # Final spread: only left page (punchline of last joke)
      last_punchline = utils.format_image_url(
        punchline_pages[-1],
        image_format='png',
        quality=100,
      )
      html_content += f"""
          <div class="spread-row">
            <div class="page page-left">
              <img src="{last_punchline}" alt="Joke {num_jokes} Punchline" class="page-image" />
            </div>
            <div class="page page-right page-empty"></div>
          </div>
      """

    html_content += f"""
        </section>
        {download_link_html}
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
