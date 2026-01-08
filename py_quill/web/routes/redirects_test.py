"""Tests for Amazon redirect routes."""

from __future__ import annotations

from web.app import app
from web.routes import redirects as redirect_routes
from web.utils import analytics as analytics_utils


def _patch_book_tags(monkeypatch, tags_by_format):
  amazon_redirect = redirect_routes.amazon_redirect
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


def test_amazon_redirect_renders_intermediate_page(monkeypatch):
  """Amazon redirects should render an intermediate redirect page (not a 302)."""
  calls: list[dict] = []

  def _mock_submit(**kwargs):
    calls.append(kwargs)

  monkeypatch.setattr(analytics_utils, "submit_ga4_event_fire_and_forget",
                      _mock_submit)
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")

  with app.test_client() as client:
    client.set_cookie("_ga", "GA1.1.1111111111.2222222222")
    resp = client.get('/book-animal-jokes?country_override=DE')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<meta name="robots" content="noindex,nofollow">' in html
  assert "amazon_redirect" in html
  assert "location.replace" in html
  assert "www.amazon.de" in html
  assert "B0G7F82P65" in html
  assert len(calls) == 1
  assert calls[0]["measurement_id"] == "G-D2B7E8PXJJ"
  assert calls[0]["client_id"] == "1111111111.2222222222"
  assert calls[0]["event_name"] == "amazon_redirect_server"
  assert calls[0]["event_params"]["redirect_key"] == "book-animal-jokes"


def test_amazon_redirect_falls_back_to_ebook_for_unsupported_country(monkeypatch):
  """Product redirects should fall back to ebook ASIN for unsupported countries."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  with app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=BR')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "www.amazon.com.br" in html
  assert "B0G9765J19" in html


def test_amazon_redirect_adds_attribution_tag_for_source(monkeypatch):
  """Product redirects should include affiliate tags when configured."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  _patch_book_tags(
    monkeypatch, {
      redirect_routes.amazon_redirect.BookFormat.PAPERBACK: {
        redirect_routes.amazon_redirect.AttributionSource.LUNCHBOX_THANK_YOU:
        "ref_=aa&tag=tag-20",
      },
    })

  with app.test_client() as client:
    resp = client.get(
      '/book-animal-jokes?country_override=US&source=lunchbox_thank_you')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" in html
  assert "ref_=aa" in html


def test_amazon_redirect_defaults_source_to_aa(monkeypatch):
  """Product redirects should default source=aa when missing."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  _patch_book_tags(
    monkeypatch, {
      redirect_routes.amazon_redirect.BookFormat.PAPERBACK: {
        redirect_routes.amazon_redirect.AttributionSource.AA:
        "ref_=aa&tag=tag-20",
      },
    })

  with app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=US')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" in html
  assert "ref_=aa" in html


def test_amazon_redirect_uses_resolved_asin_for_attribution(monkeypatch):
  """Attribution tags should use the resolved ASIN (fallback included)."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  _patch_book_tags(
    monkeypatch, {
      redirect_routes.amazon_redirect.BookFormat.EBOOK: {
        redirect_routes.amazon_redirect.AttributionSource.AA:
        "ref_=aa&tag=tag-ebook",
      },
    })

  with app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=BR&source=aa')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "B0G9765J19" in html
  assert "tag=tag-ebook" in html
  assert "ref_=aa" in html


def test_amazon_review_redirect_ignores_attribution_tags(monkeypatch):
  """Review redirects should never apply affiliate tags."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  _patch_book_tags(
    monkeypatch, {
      redirect_routes.amazon_redirect.BookFormat.PAPERBACK: {
        redirect_routes.amazon_redirect.AttributionSource.AA:
        "ref_=aa&tag=tag-20",
      },
    })

  with app.test_client() as client:
    resp = client.get('/review-animal-jokes?country_override=US&source=aa')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" not in html


def test_amazon_redirect_logs_warning_for_unknown_source(monkeypatch):
  """Unknown source codes should log a warning and skip tagging."""
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")

  with app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=US&source=unknown')

  assert resp.status_code == 200


