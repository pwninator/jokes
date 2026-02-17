"""Tests for Amazon redirect routes."""

from __future__ import annotations

from web.app import app
from web.utils import analytics as analytics_utils
from common import amazon_redirect


def _patch_book_tags(monkeypatch, tags_by_format):
  base_book = amazon_redirect.BOOKS[amazon_redirect.BookKey.ANIMAL_JOKES]
  variants = {}
  for book_format, variant in base_book.variants.items():
    tags = tags_by_format.get(book_format, variant.attribution_tags)
    variants[book_format] = amazon_redirect.BookVariant(
      asin=variant.asin,
      supported_countries=variant.supported_countries,
      attribution_tags=tags,
    )
  patched_book = amazon_redirect.Book(
    title=base_book.title,
    variants=variants,
  )
  monkeypatch.setattr(amazon_redirect, "BOOKS",
                      {amazon_redirect.BookKey.ANIMAL_JOKES: patched_book})


def test_book_redirect_redirects_to_books_page():
  """Book redirects should 302 to the /books page."""
  with app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=DE')

  assert resp.status_code == 302
  assert resp.headers["Location"] == "/books"









def test_amazon_review_redirect_ignores_attribution_tags(monkeypatch):
  """Review redirects should never apply affiliate tags."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  _patch_book_tags(
    monkeypatch, {
      amazon_redirect.BookFormat.PAPERBACK: {
        amazon_redirect.AttributionSource.AA: "ref_=aa&tag=tag-20",
      },
    })

  with app.test_client() as client:
    resp = client.get('/review-animal-jokes?country_override=US&source=aa')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" not in html



def test_valentine_book_redirect_redirects_to_books_page():
  """Valentine book redirects should 302 to the /books page."""
  with app.test_client() as client:
    resp = client.get('/book-valentine-jokes?country_override=DE')

  assert resp.status_code == 302
  assert resp.headers["Location"] == "/books"


def test_valentine_review_redirect_ignores_attribution_tags(monkeypatch):
  """Valentine review redirects should never apply affiliate tags."""
  monkeypatch.setattr(analytics_utils, "submit_ga4_event_fire_and_forget",
                      lambda **_: None)
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")

  with app.test_client() as client:
    resp = client.get('/review-valentine-jokes?country_override=US&source=aa')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  expected_asin = amazon_redirect.BOOKS[
    amazon_redirect.BookKey.VALENTINE_JOKES].variant_for(
      amazon_redirect.BookFormat.PAPERBACK).asin
  assert "/review/create-review/" in html
  assert f"asin={expected_asin}" in html
  assert "tag=" not in html
