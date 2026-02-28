"""Joke book cloud functions."""
import traceback
from typing import cast

import flask
from common import image_operations, models, utils
from firebase_functions import https_fn, logger, options
from functions.function_utils import (AuthError, error_response,
                                      get_bool_param, get_list_param,
                                      get_param, get_str_param, get_user_id,
                                      handle_cors_preflight,
                                      handle_health_check, html_response,
                                      success_response)
from services import firestore
from storage import joke_books_firestore

NUM_TOP_JOKES_FOR_BOOKS = 50


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def generate_joke_book_page(req: flask.Request) -> flask.Response:
  """Generate book page images for a joke."""
  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    joke_id = cast(str, get_str_param(req, 'joke_id', required=True))
    setup_instructions = get_str_param(req, 'setup_instructions',
                                       default='') or ''
    punchline_instructions = get_str_param(
      req, 'punchline_instructions', default='') or ''
    style_update = get_bool_param(req, 'style_update', required=False)
    include_text = get_bool_param(req,
                                  'include_text',
                                  required=False,
                                  default=True)

    base_image_source = get_str_param(
      req,
      'base_image_source',
      default='original',
    ) or 'original'
    if base_image_source not in ('original', 'book_page'):
      return error_response(f'Invalid base_image_source: {base_image_source}',
                            req=req,
                            status=400)

    logger.info(f'Generating book page images for joke {joke_id}')

    (
      setup_image,
      punchline_image,
    ) = image_operations.generate_and_populate_book_pages(
      joke_id,
      overwrite=True,
      additional_setup_instructions=setup_instructions,
      additional_punchline_instructions=punchline_instructions,
      base_image_source=base_image_source,
      style_update=style_update,
      include_image_description=include_text,
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
    return html_response(return_val, req=req, status=200)
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke book: {str(e)}',
                          req=req,
                          status=500)


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def create_joke_book(req: flask.Request) -> flask.Response:
  """Create a new joke book from a list of jokes."""
  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    try:
      user_id = get_user_id(req)
    except AuthError:
      return error_response('User not authenticated', req=req, status=401)

    raw_joke_ids = get_param(req, 'joke_ids')
    book_name = get_str_param(req, 'book_name')

    if not book_name:
      return error_response('book_name is required', req=req, status=400)
    if not user_id:
      return error_response('User not authenticated', req=req, status=401)

    if raw_joke_ids is None:
      top_jokes = firestore.get_top_jokes(
        'popularity_score_recent',
        NUM_TOP_JOKES_FOR_BOOKS,
      )
      joke_ids = [
        cast(str, joke.key) for joke in top_jokes
        if getattr(joke, 'key', None)
      ]
      if not joke_ids:
        return error_response('No jokes available to create joke book',
                              req=req,
                              status=400)
    else:
      joke_ids = get_list_param(req, 'joke_ids')

    logger.info(f'Creating book {book_name} with jokes: {joke_ids}')

    for joke_id in joke_ids:
      _ = image_operations.generate_and_populate_book_pages(joke_id,
                                                            overwrite=True)

    # Generate ZIP + paperback PDF of all book pages and store in temp files bucket
    export_files = image_operations.export_joke_page_files_for_kdp(joke_ids)

    doc_id = utils.create_timestamped_firestore_key(user_id)
    _ = joke_books_firestore.create_joke_book(
      models.JokeBook(
        id=doc_id,
        book_name=book_name,
        jokes=joke_ids,
        zip_url=export_files.zip_url,
        paperback_pdf_url=export_files.paperback_pdf_url,
      ))

    return success_response({'book_id': doc_id}, req=req)
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke book: {str(e)}',
                          req=req,
                          status=500)


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def update_joke_book_files(req: flask.Request) -> flask.Response:
  """Regenerate the ZIP and paperback PDF for a joke book."""
  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    joke_book_id = _get_joke_book_id_from_request(req)
    if not joke_book_id:
      return error_response('joke_book_id is required', req=req, status=400)

    book = joke_books_firestore.get_joke_book(joke_book_id)
    if not book:
      return error_response('Joke book not found', req=req, status=404)

    joke_ids = book.jokes
    if not joke_ids:
      return error_response('Joke book has no jokes to export',
                            req=req,
                            status=400)

    export_files = image_operations.export_joke_page_files_for_kdp(joke_ids)
    _ = joke_books_firestore.update_joke_book_export_files(
      joke_book_id,
      zip_url=export_files.zip_url,
      paperback_pdf_url=export_files.paperback_pdf_url,
    )

    return success_response(
      {
        'book_id': joke_book_id,
        'zip_url': export_files.zip_url,
        'paperback_pdf_url': export_files.paperback_pdf_url,
      },
      req=req)

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error updating joke book files: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to update joke book files: {str(e)}',
                          req=req,
                          status=500)


def _get_joke_book_id_from_request(req: flask.Request) -> str | None:
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
def get_joke_book(req: flask.Request) -> flask.Response:
  """Gets a joke book and returns it as an HTML page."""
  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    joke_book_id = _get_joke_book_id_from_request(req)

    if not joke_book_id:
      return error_response('joke_book_id is required', req=req, status=400)

    try:
      book, setup_pages, punchline_pages = (
        joke_books_firestore.get_book_page_spread_urls(joke_book_id))
    except ValueError as exc:
      return error_response(str(exc), req=req, status=400)

    if not book:
      return html_response("Book not found", req=req, status=404)

    book_title = book.book_name or 'My Joke Book'
    zip_url = book.zip_url
    paperback_pdf_url = book.paperback_pdf_url

    download_link_html = ""
    if zip_url:
      download_link_html += (
        f'<p><a href="{zip_url}" download>Download All Pages (ZIP)</a></p>')
    if paperback_pdf_url:
      download_link_html += (
        f'<p><a href="{paperback_pdf_url}" download>Download Paperback PDF</a></p>'
      )

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

    return html_response(html_content, req=req, status=200)

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error getting joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to get joke book: {str(e)}',
                          req=req,
                          status=500)
