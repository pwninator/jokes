"""Tests for amazon_redirect helpers."""

import pytest

from common import amazon_redirect


def test_get_amazon_domain_known_country():
  assert amazon_redirect.get_amazon_domain("de") == "amazon.de"
  assert amazon_redirect.get_amazon_domain("GB") == "amazon.co.uk"


def test_get_amazon_domain_unknown_defaults_to_us():
  assert amazon_redirect.get_amazon_domain(
    "zz") == amazon_redirect.DEFAULT_DOMAIN
  assert amazon_redirect.get_amazon_domain(
    None) == amazon_redirect.DEFAULT_DOMAIN


def test_normalize_source_strips_whitespace_only():
  assert amazon_redirect._normalize_source(" aae ") == "aae"
  assert amazon_redirect._normalize_source("  ") is None
  assert amazon_redirect._normalize_source(None) is None


def test_get_attribution_query_requires_exact_match(monkeypatch):
  monkeypatch.setattr(amazon_redirect, "AMAZON_ATTRIBUTION_TAGS",
                      {("B0TEST", "aae"): "ref_=aa&tag=tag-20"})

  assert amazon_redirect._get_attribution_tag(
    "B0TEST",
    "aae",
  ) == "ref_=aa&tag=tag-20"
  assert amazon_redirect._get_attribution_tag("B0TEST", "AAE") is None


def test_apply_attribution_query_merges_existing_query():
  source = "https://www.amazon.com/dp/B0TEST?ref_=old&tag=old-20&foo=bar"
  result = amazon_redirect._apply_attribution_tag(
    source,
    "ref_=aa&tag=new-21",
  )
  assert result.startswith("https://www.amazon.com/dp/B0TEST")
  assert "ref_=aa" in result
  assert "tag=new-21" in result
  assert "tag=old-20" not in result
  assert "foo=bar" in result


def test_apply_attribution_query_adds_query_when_missing():
  source = "https://www.amazon.com/dp/B0TEST"
  result = amazon_redirect._apply_attribution_tag(
    source,
    "ref_=aa&tag=new-21",
  )
  assert result.startswith("https://www.amazon.com/dp/B0TEST")
  assert "ref_=aa" in result
  assert "tag=new-21" in result


def test_amazon_redirect_config_base_urls():
  product = amazon_redirect.AmazonRedirectConfig(
    asin="B0PROD",
    page_type=amazon_redirect.AmazonRedirectPageType.PRODUCT,
    label="Product",
    description="Test product",
  )
  review = amazon_redirect.AmazonRedirectConfig(
    asin="B0REV",
    page_type=amazon_redirect.AmazonRedirectPageType.REVIEW,
    label="Review",
    description="Test review",
  )

  assert (product._construct_url("B0PROD",
                                 "US") == "https://www.amazon.com/dp/B0PROD")
  assert (review._construct_url(
    "B0REV",
    "US") == "https://www.amazon.com/review/create-review/?ie=UTF8&asin=B0REV")


def test_resolve_country_and_asin_with_supported_list():
  config = amazon_redirect.AmazonRedirectConfig(
    asin="B0ANY",
    page_type=amazon_redirect.AmazonRedirectPageType.PRODUCT,
    label="Limited",
    description="Limited countries",
    supported_countries=frozenset({"US", "DE"}),
  )

  assert config._resolve_country_and_asin("de") == ("DE", "B0ANY")
  assert config._resolve_country_and_asin("BR") == ("US", "B0ANY")
  assert config._resolve_country_and_asin(None) == ("US", "B0ANY")


def test_default_supported_countries_is_all():
  config = amazon_redirect.AmazonRedirectConfig(
    asin="B0GLOBAL",
    page_type=amazon_redirect.AmazonRedirectPageType.PRODUCT,
    label="Global",
    description="All countries",
  )

  assert config.supported_countries == amazon_redirect.ALL_COUNTRIES


def test_resolve_target_url_falls_back_to_ebook_for_unsupported_country():
  config = amazon_redirect.AmazonRedirectConfig(
    asin="B0PRINT",
    fallback_asin="B0EBOOK",
    page_type=amazon_redirect.AmazonRedirectPageType.PRODUCT,
    label="Product",
    description="Test product",
    supported_countries=frozenset({"US", "DE"}),
  )

  target_url, resolved_country, resolved_asin = config.resolve_target_url(
    "DE",
    None,
  )
  assert resolved_country == "DE"
  assert resolved_asin == "B0PRINT"
  assert "amazon.de" in target_url
  assert "B0PRINT" in target_url

  fallback_url, fallback_country, fallback_asin = config.resolve_target_url(
    "BR",
    None,
  )
  assert fallback_country == "BR"
  assert fallback_asin == "B0EBOOK"
  assert "amazon.com.br" in fallback_url
  assert "B0EBOOK" in fallback_url

  unknown_url, unknown_country, unknown_asin = config.resolve_target_url(
    "ZZ",
    None,
  )
  assert unknown_country == "US"
  assert unknown_asin == "B0EBOOK"
  assert "amazon.com/dp/B0EBOOK" in unknown_url
