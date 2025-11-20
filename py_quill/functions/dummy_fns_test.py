"""Tests for the dummy_fns module."""

from types import SimpleNamespace

from firebase_functions import https_fn
from functions import dummy_fns


class DummyReq:
  """Simple request object for testing."""

  def __init__(self,
               *,
               path: str = "",
               args: dict | None = None,
               method: str = 'GET',
               is_json: bool = False):
    self.path = path
    self.args = args or {}
    self.method = method
    self.is_json = is_json
    self.headers = {}

  def get_json(self, silent: bool = False):
    if self.is_json:
      return {"data": {}}
    if silent:
      return None
    raise TypeError("Request is not JSON")


def test_dummy_endpoint_renders_book_page_comparison(monkeypatch):
  joke_id = "joke-123"
  original_setup_url = "https://cdn.example.com/original-setup.png"
  original_punchline_url = "https://cdn.example.com/original-punchline.png"

  monkeypatch.setattr(
    dummy_fns.firestore, "get_punny_joke",
    lambda requested_id: SimpleNamespace(
      setup_image_url=original_setup_url,
      punchline_image_url=original_punchline_url,
    ) if requested_id == joke_id else None)

  calls: list[tuple[str, bool]] = []

  def fake_create_book_pages(joke_id_param: str,
                             image_editor_instance=None,
                             overwrite: bool = False):
    del image_editor_instance
    calls.append((joke_id_param, overwrite))
    return [
      "https://cdn.example.com/book-page-setup.png",
      "https://cdn.example.com/book-page-punchline.png",
    ]

  monkeypatch.setattr(dummy_fns.image_operations, "create_book_pages",
                      fake_create_book_pages)

  req = DummyReq(path="/dummy", args={"joke_id": joke_id})

  response = dummy_fns.dummy_endpoint(req)

  assert isinstance(response, https_fn.Response)
  assert response.status_code == 200
  assert response.mimetype == 'text/html'
  assert calls == [(joke_id, True)]

  html = response.get_data(as_text=True)
  punchline_index = html.index(
    "https://cdn.example.com/original-punchline.png")
  setup_index = html.index("https://cdn.example.com/original-setup.png")
  assert punchline_index < setup_index

  book_punchline_index = html.index(
    "https://cdn.example.com/book-page-punchline.png")
  book_setup_index = html.index("https://cdn.example.com/book-page-setup.png")
  assert book_punchline_index < book_setup_index

  assert "Book Page Comparison - Joke" in html
