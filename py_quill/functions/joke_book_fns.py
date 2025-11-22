"""Joke book cloud functions."""
import html
import traceback
from urllib.parse import urlencode

from common import image_operations, utils
from firebase_functions import https_fn, logger, options
from functions.function_utils import (error_response, get_param, get_user_id,
                                      success_response)
from services import firestore

NUM_TOP_JOKES_FOR_BOOKS = 50


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def manage_joke_book(req: https_fn.Request) -> https_fn.Response:
  """Manage joke book operations."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['POST', 'GET']:
      return error_response(f'Method not allowed: {req.method}')

    joke_book_id = get_param(req, 'joke_book_id')
    if not joke_book_id and req.method == 'POST':
      joke_book_id = (req.form or {}).get('joke_book_id')
    if not joke_book_id:
      return error_response('joke_book_id is required')

    if req.method == 'POST':
      form_data = req.form or {}
      joke_id = form_data.get('joke_id')
      if not joke_id:
        return error_response('joke_id is required for regeneration')

      setup_instructions = (form_data.get('setup_instructions') or '').strip()
      punchline_instructions = (form_data.get('punchline_instructions')
                                or '').strip()

      logger.info(
        ('Regenerating book pages for joke %s in book %s with '
         'custom instructions.'),
        joke_id,
        joke_book_id,
      )

      image_operations.generate_and_populate_book_pages(
        joke_id,
        overwrite=True,
        additional_setup_instructions=setup_instructions,
        additional_punchline_instructions=punchline_instructions,
      )

      redirect_url = f"{req.base_url}?{urlencode({'joke_book_id': joke_book_id})}"
      return https_fn.Response('',
                               status=302,
                               headers={'Location': redirect_url})

    book_ref = firestore.db().collection('joke_books').document(joke_book_id)
    book_doc = book_ref.get()

    if not book_doc.exists:
      return error_response(f'Joke book {joke_book_id} not found')

    book_data = book_doc.to_dict()
    joke_ids = book_data.get('jokes', [])

    if not joke_ids:
      return error_response('Joke book has no jokes')

    book_title = book_data.get('book_name', f'Joke Book {joke_book_id}')
    zip_url = book_data.get('zip_url')

    logger.info(f'Rendering book {joke_book_id} with jokes: {joke_ids}')

    def _extract_url(image_or_url: object | None) -> str | None:
      if image_or_url is None:
        return None
      if hasattr(image_or_url, 'url'):
        return str(getattr(image_or_url, 'url'))
      return str(image_or_url)

    jokes_for_page: list[dict[str, str]] = []
    missing_jokes: list[str] = []

    for joke_id in joke_ids:
      joke_ref = firestore.db().collection('jokes').document(joke_id)
      joke_doc = joke_ref.get()
      if not joke_doc.exists:
        missing_jokes.append(joke_id)
        continue

      metadata_ref = joke_ref.collection('metadata').document('metadata')
      metadata_doc = metadata_ref.get()
      metadata = metadata_doc.to_dict() if metadata_doc.exists else {}

      setup_url = metadata.get(
        'book_page_setup_image_url') if metadata else None
      punchline_url = (metadata.get('book_page_punchline_image_url')
                       if metadata else None)

      if not setup_url or not punchline_url:
        generated_setup, generated_punchline = (
          image_operations.generate_and_populate_book_pages(
            joke_id,
            overwrite=False,
          ))
        setup_url = _extract_url(generated_setup)
        punchline_url = _extract_url(generated_punchline)

      setup_url = _extract_url(setup_url)
      punchline_url = _extract_url(punchline_url)

      if not setup_url or not punchline_url:
        missing_jokes.append(joke_id)
        continue

      jokes_for_page.append({
        'sequence':
        len(jokes_for_page) + 1,
        'joke_id':
        joke_id,
        'setup_image':
        utils.format_image_url(setup_url, image_format='png', quality=100),
        'punchline_image':
        utils.format_image_url(punchline_url, image_format='png', quality=100),
      })

    download_link_html = ""
    if zip_url:
      download_link_html = (
        f'<p><a href="{html.escape(str(zip_url))}" download>'
        'Download All Pages (ZIP)</a></p>')

    missing_html = ""
    if missing_jokes:
      missing_list = ', '.join(html.escape(str(jid)) for jid in missing_jokes)
      missing_html = f"""
        <section class="alert">
          <p>
            The following jokes could not be displayed. They may be missing data
            or generation failed:<br /><strong>{missing_list}</strong>
          </p>
        </section>
      """

    joke_sections: list[str] = []
    escaped_book_id = html.escape(str(joke_book_id))
    for joke_entry in jokes_for_page:
      seq = joke_entry['sequence']
      escaped_joke_id = html.escape(str(joke_entry['joke_id']))
      setup_img = html.escape(joke_entry['setup_image'])
      punchline_img = html.escape(joke_entry['punchline_image'])

      joke_sections.append(f"""
        <article class="joke-section">
          <header class="joke-header">
            <h2>Joke {seq}</h2>
            <p class="joke-id">ID: {escaped_joke_id}</p>
          </header>
          <div class="joke-content">
            <div class="joke-images">
              <figure>
                <img src="{setup_img}" alt="Joke {seq} setup page" width="600" height="600" loading="lazy" />
                <figcaption>Setup Page</figcaption>
              </figure>
              <figure>
                <img src="{punchline_img}" alt="Joke {seq} punchline page" width="600" height="600" loading="lazy" />
                <figcaption>Punchline Page</figcaption>
              </figure>
            </div>
            <form method="POST" class="regenerate-form">
              <input type="hidden" name="joke_book_id" value="{escaped_book_id}" />
              <input type="hidden" name="joke_id" value="{escaped_joke_id}" />
              <label>
                <span>Setup instructions</span>
                <textarea name="setup_instructions" rows="3" placeholder="Optional additional art direction for the setup page"></textarea>
              </label>
              <label>
                <span>Punchline instructions</span>
                <textarea name="punchline_instructions" rows="3" placeholder="Optional additional art direction for the punchline page"></textarea>
              </label>
              <button type="submit">Regenerate</button>
            </form>
          </div>
        </article>
      """)

    jokes_html = "\n".join(joke_sections) if joke_sections else """
      <p class="empty-state">
        No jokes are currently available in this book. Add jokes to the book to see them here.
      </p>
    """

    escaped_book_title = html.escape(str(book_title))
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Manage Joke Book - {escaped_book_title}</title>
      <style>
        body {{
          font-family: Arial, Helvetica, sans-serif;
          margin: 24px;
          background-color: #111;
          color: #f0f0f0;
        }}
        h1 {{
          margin-bottom: 8px;
        }}
        a {{
          color: #f5a623;
        }}
        .book-meta {{
          margin-bottom: 24px;
        }}
        .alert {{
          border: 1px solid #b28700;
          background: rgba(178, 135, 0, 0.1);
          padding: 12px 16px;
          border-radius: 8px;
          margin-bottom: 24px;
        }}
        .joke-section {{
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 24px;
          background: rgba(255, 255, 255, 0.04);
        }}
        .joke-header {{
          margin-bottom: 12px;
        }}
        .joke-id {{
          font-size: 0.9rem;
          color: rgba(255, 255, 255, 0.7);
          margin: 4px 0 0;
        }}
        .joke-content {{
          display: flex;
          flex-wrap: wrap;
          gap: 20px;
        }}
        .joke-images {{
          display: flex;
          flex-direction: row;
          gap: 16px;
          flex: 1 1 60%;
          min-width: 280px;
        }}
        figure {{
          margin: 0;
          flex: 1 1 50%;
          text-align: center;
        }}
        figure img {{
          width: 100%;
          height: auto;
          border-radius: 8px;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
        }}
        figcaption {{
          margin-top: 8px;
          font-size: 0.95rem;
          color: rgba(255, 255, 255, 0.8);
        }}
        .regenerate-form {{
          flex: 1 1 35%;
          min-width: 260px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }}
        .regenerate-form label {{
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-weight: 600;
        }}
        .regenerate-form textarea {{
          resize: vertical;
          min-height: 72px;
          padding: 8px;
          border-radius: 6px;
          border: 1px solid rgba(255, 255, 255, 0.2);
          background: rgba(0, 0, 0, 0.25);
          color: #f0f0f0;
        }}
        .regenerate-form button {{
          align-self: flex-start;
          padding: 10px 20px;
          border-radius: 24px;
          border: none;
          background: #f5a623;
          color: #111;
          font-weight: 700;
          cursor: pointer;
          transition: transform 120ms ease, box-shadow 120ms ease;
        }}
        .regenerate-form button:hover {{
          transform: translateY(-1px);
          box-shadow: 0 8px 16px rgba(0, 0, 0, 0.35);
        }}
        .empty-state {{
          font-size: 1rem;
          color: rgba(255, 255, 255, 0.8);
        }}
      </style>
    </head>
    <body>
      <h1>Manage Joke Book</h1>
      <div class="book-meta">
        <p><strong>Book title:</strong> {escaped_book_title}</p>
        <p><strong>Book ID:</strong> {escaped_book_id}</p>
        {download_link_html}
      </div>
      {missing_html}
      <section class="jokes">
        {jokes_html}
      </section>
    </body>
    </html>
    """

    return https_fn.Response(html_content,
                             status=200,
                             headers={'Content-Type': 'text/html'})

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error managing joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to manage joke book: {str(e)}')


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def generate_joke_book_page(req: https_fn.Request) -> https_fn.Response:
  """Generate book page images for a joke."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

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
    return return_val
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke book: {str(e)}')


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
def update_joke_book(req: https_fn.Request) -> https_fn.Response:
  """Update an existing joke book by regenerating pages and zip."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['POST', 'GET']:
      return error_response(f'Method not allowed: {req.method}')

    joke_book_id = get_param(req, 'joke_book_id')
    if not joke_book_id:
      return error_response('joke_book_id is required')

    book_ref = firestore.db().collection('joke_books').document(joke_book_id)
    book_doc = book_ref.get()

    if not book_doc.exists:
      return error_response(f'Joke book {joke_book_id} not found')

    book_data = book_doc.to_dict()
    joke_ids = book_data.get('jokes', [])

    if not joke_ids:
      return error_response('Joke book has no jokes')

    logger.info(f'Updating book {joke_book_id} with jokes: {joke_ids}')

    for joke_id in joke_ids:
      image_operations.generate_and_populate_book_pages(joke_id,
                                                        overwrite=False)

    # Generate ZIP of all book pages and store in temp files bucket
    zip_url = image_operations.zip_joke_page_images_for_kdp(joke_ids)

    book_ref.update({
      'zip_url': zip_url,
    })

    return success_response({'book_id': joke_book_id, 'zip_url': zip_url})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error updating joke book: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to update joke book: {str(e)}')


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
