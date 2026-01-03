"""Tests for lunchbox routes."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

from web.app import app
from web.routes import lunchbox as lunchbox_routes
from web.utils import analytics as analytics_utils


def test_lunchbox_get_renders_form():
  with app.test_client() as client:
    resp = client.get('/lunchbox')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Header brand should be clickable.
  assert '<a class="brand"' in html
  # Nav should mark lunchbox link active.
  assert 'href="/lunchbox"' in html
  assert 'Printable Joke Notes' in html
  assert 'nav-link--active' in html
  # Copy may change; assert key hero heading scaffold exists.
  assert 'id="lunchbox-hero-title"' in html
  assert 'name="email"' in html
  # Submit CTA copy may change; assert the submit control exists.
  assert 'type="submit"' in html
  assert 'web_lunchbox_submit_click' in html


def test_lunchbox_post_stores_lead_and_redirects(monkeypatch):
  captured: dict[str, object] = {}

  def _fake_create_lead(**kwargs):
    captured["kwargs"] = kwargs
    return {
      "email": kwargs["email"],
    }

  monkeypatch.setattr(lunchbox_routes.joke_lead_operations, "create_lead",
                      _fake_create_lead)

  with app.test_client() as client:
    resp = client.post('/lunchbox?country_override=DE',
                       data={
                         'email': 'Test@Example.com',
                       })

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/lunchbox-thank-you')
  assert captured["kwargs"]["email"] == 'test@example.com'
  assert captured["kwargs"]["country_code"] == 'DE'
  assert captured["kwargs"]["signup_source"] == 'lunchbox'
  assert captured["kwargs"][
    "group_id"] == lunchbox_routes.joke_lead_operations.GROUP_SNICKERDOODLE_CLUB


def test_lunchbox_post_invalid_email_renders_error(monkeypatch):
  create_lead = Mock()
  monkeypatch.setattr(lunchbox_routes.joke_lead_operations, "create_lead",
                      create_lead)

  with app.test_client() as client:
    resp = client.post('/lunchbox', data={'email': 'not-an-email'})

  assert resp.status_code == 400
  html = resp.get_data(as_text=True)
  assert 'Please enter a valid email address.' in html
  create_lead.assert_not_called()


def test_lunchbox_post_mailerlite_failure_renders_error(monkeypatch):

  def _fail(**_kwargs):
    raise RuntimeError("MailerLite down")

  monkeypatch.setattr(lunchbox_routes.joke_lead_operations, "create_lead",
                      _fail)

  with app.test_client() as client:
    resp = client.post('/lunchbox?country_override=DE',
                       data={
                         'email': 'test@example.com',
                       })

  assert resp.status_code == 500
  html = resp.get_data(as_text=True)
  assert 'Unable to process your request. Please try again.' in html


def test_lunchbox_thank_you_renders():
  """Thank you page should render with correct Amazon URL."""
  with app.test_client() as client:
    resp = client.get('/lunchbox-thank-you')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'High Five!' in html
  assert 'id="thankyou-title"' in html
  assert 'Get the Book on Amazon' in html
  assert 'web_lunchbox_thank_you' in html
  # Should contain an amazon.com URL (default US)
  assert 'href="https://www.amazon.com/dp/B0G7F82P65' in html


def test_lunchbox_thank_you_uses_country_specific_domain():
  """Thank you page should use country-specific Amazon domain."""
  with app.test_client() as client:
    resp = client.get('/lunchbox-thank-you',
                      headers={'X-Appengine-Country': 'GB'})

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'www.amazon.co.uk' in html
  assert 'B0G7F82P65' in html  # Paperback ASIN


def test_lunchbox_thank_you_falls_back_to_ebook_for_unsupported_country():
  """Thank you page should use ebook for countries without paperback."""
  with app.test_client() as client:
    resp = client.get('/lunchbox-thank-you',
                      headers={'X-Appengine-Country': 'BR'})

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'www.amazon.com.br' in html
  assert 'B0G9765J19' in html  # Ebook ASIN (fallback)


def test_lunchbox_thank_you_includes_attribution_tag():
  """Thank you page should include attribution for lunchbox_thank_you source."""
  with app.test_client() as client:
    resp = client.get('/lunchbox-thank-you',
                      headers={'X-Appengine-Country': 'US'})

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Should contain the attribution tag configured for (B0G7F82P65, lunchbox_thank_you)
  assert 'maas=maas_adg_92547F51E50DB214BCBCD9D297E81344_afap_abs' in html
  assert 'ref_=aa_maas' in html
  assert 'tag=maas' in html


def test_lunchbox_download_pdf_renders(monkeypatch):
  calls: list[dict] = []

  def _mock_submit(**kwargs):
    calls.append(kwargs)

  monkeypatch.setattr(analytics_utils, "submit_ga4_event_fire_and_forget",
                      _mock_submit)
  monkeypatch.setattr(analytics_utils.config, "get_google_analytics_api_key",
                      lambda: "test-secret")

  with app.test_client() as client:
    client.set_cookie("_ga", "GA1.1.3333333333.4444444444")
    resp = client.get('/lunchbox-download-pdf')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<meta name="robots" content="noindex,nofollow">' in html
  assert "location.replace" in html
  assert 'lunchbox_notes_animal_jokes.pdf' in html
  assert 'web_lunchbox_download_client' in html
  assert 'CompleteRegistration' in html
  assert 'fbq' in html
  assert len(calls) == 1
  assert calls[0]["measurement_id"] == "G-D2B7E8PXJJ"
  assert calls[0]["client_id"] == "3333333333.4444444444"
  assert calls[0]["event_name"] == "web_lunchbox_download_server"
  assert calls[0]["event_params"]["asset"] == "lunchbox_notes_animal_jokes.pdf"
