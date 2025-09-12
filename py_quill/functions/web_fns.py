"""Web cloud functions."""

import flask
from firebase_functions import https_fn, options
from services import firestore, search

app = flask.Flask(__name__)


@app.route('/search')
def search_page_handler():
  """A web page that displays jokes based on a search query."""
  query = flask.request.args.get('query', '')
  if not query:
    return "Please provide a 'query' parameter in the URL."

  return _run_search(query)


@app.route('/search/dogs')
def search_page_handler_dog():
  """A web page that displays jokes based on a search query."""
  return _run_search("dogs")


def _run_search(query: str) -> str:
  """Run a search for jokes based on a query."""
  search_results = search.search_jokes(
    query=query,
    label="web_search",
    limit=10,
    field_filters=[],
  )

  jokes = []
  for result in search_results:
    joke = firestore.get_punny_joke(result.joke.key)
    if joke:
      jokes.append(joke)

  # Simple HTML rendering
  html = "<html><body>"
  html += f"<h1>Jokes for '{query}'</h1>"
  for joke in jokes:
    html += "<div>"
    if joke.setup_image_url:
      html += f"<img src='{joke.setup_image_url}' width='200'>"
    html += f"<p><b>Setup:</b> {joke.setup_text}</p>"
    if joke.punchline_image_url:
      html += f"<img src='{joke.punchline_image_url}' width='200'>"
    html += f"<p><b>Punchline:</b> {joke.punchline_text}</p>"
    html += "</div><hr>"
  html += "</body></html>"

  return html


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=30,
)
def web_search_page(req: https_fn.Request) -> https_fn.Response:
  """A web page that displays jokes based on a search query."""
  with app.request_context(req.environ):
    return app.full_dispatch_request()
