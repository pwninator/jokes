"""Helpers for building Amazon URLs that respect country-specific domains."""

from __future__ import annotations

import dataclasses
import enum
import urllib.parse

from firebase_functions import logger

# Default domain if a country code is missing or unsupported.
DEFAULT_DOMAIN = "amazon.com"
DEFAULT_COUNTRY_CODE = "US"

# Mapping of ISO 3166-1 alpha-2 country codes to Amazon domains.
COUNTRY_TO_DOMAIN = {
  "AE": "amazon.ae",
  "AU": "amazon.com.au",
  "BE": "amazon.com.be",
  "BR": "amazon.com.br",
  "CA": "amazon.ca",
  "DE": "amazon.de",
  "ES": "amazon.es",
  "FR": "amazon.fr",
  "GB": "amazon.co.uk",
  "IE": "amazon.ie",
  "IN": "amazon.in",
  "IT": "amazon.it",
  "JP": "amazon.co.jp",
  "MX": "amazon.com.mx",
  "NL": "amazon.nl",
  "PL": "amazon.pl",
  "SA": "amazon.sa",
  "SE": "amazon.se",
  "SG": "amazon.sg",
  "UK": "amazon.co.uk",  # Accept UK alias for convenience.
  "US": "amazon.com",
}

ALL_COUNTRIES = frozenset(COUNTRY_TO_DOMAIN.keys())
BOOK_PRINT_COUNTRIES = frozenset({
  "AU", "BE", "CA", "DE", "ES", "FR", "GB", "IE", "IT", "JP", "NL", "PL", "SE",
  "UK", "US"
})


class AmazonRedirectPageType(enum.Enum):
  """Type of Amazon page to redirect to."""
  PRODUCT = "product"
  REVIEW = "review"


@dataclasses.dataclass(frozen=True)
class AmazonRedirectConfig:
  """Definition for a redirect target."""

  asin: str
  page_type: AmazonRedirectPageType
  label: str
  description: str
  supported_countries: frozenset[str] = ALL_COUNTRIES

  apply_attribution: bool = True
  """Whether to apply affiliate attribution tags for this redirect."""

  fallback_asin: str | None = None
  """If provided, keep the requested counttry and fall back to this ASIN. Otherwise, fall back to the default country with the main ASIN."""

  def resolve_target_url(
    self,
    requested_country_code: str | None,
    source: str | None = None,
  ) -> tuple[str, str, str]:
    """Return the target URL, resolved country, and product variant.
    
    If the requested country code is supported, return the target URL for the country's domain using the main ASIN.
    If the requested country code is not supported, and a fallback ASIN is provided, return the target URL using the requested country (as long as it's in the all countries set) for the fallback ASIN.
    If the requested country code is not supported, and no fallback ASIN is provided, return the target URL using the default country and the main ASIN.
    If attribution is enabled and a source maps to an attribution query, apply it to the target URL.

    Args:
      requested_country_code: ISO 3166-1 alpha-2 country code (case-insensitive).
      source: Source identifier used for attribution tag lookup.
    
    Returns:
      target_url: The target URL for the redirect.
      resolved_country: The resolved country code.
      resolved_asin: The resolved ASIN.
    """
    resolved_country, resolved_asin = self._resolve_country_and_asin(
      requested_country_code)
    target_url = self._construct_url(resolved_asin, resolved_country)

    attribution_tag = _get_attribution_tag(resolved_asin, source)
    if self.apply_attribution and attribution_tag:
      target_url = _apply_attribution_tag(target_url, attribution_tag)

    return target_url, resolved_country, resolved_asin

  def _product_base_url(self, asin: str, domain: str) -> str:
    return f"https://www.{domain}/dp/{asin}"

  def _review_base_url(self, asin: str, domain: str) -> str:
    return f"https://www.{domain}/review/create-review/?ie=UTF8&asin={asin}"

  def _construct_url(self, asin: str, country_code: str) -> str:
    """Return the Amazon URL for this redirect."""
    domain = get_amazon_domain(country_code)
    match self.page_type:
      case AmazonRedirectPageType.PRODUCT:
        return self._product_base_url(asin, domain)
      case AmazonRedirectPageType.REVIEW:
        return self._review_base_url(asin, domain)

  def _resolve_country_and_asin(
    self,
    requested_country_code: str | None,
  ) -> tuple[str, str]:
    """Return a supported country code and ASIN for this redirect."""
    requested_country_code = normalize_country_code(
      requested_country_code) or DEFAULT_COUNTRY_CODE

    if requested_country_code in self.supported_countries:
      # The requested country is supported, so use it and the main ASIN
      resolved_country = requested_country_code
      resolved_asin = self.asin
    elif self.fallback_asin:
      # Country is not supported, but a fallback ASIN is provided, so use it and the requested country if it's in the all countries set.
      resolved_country = requested_country_code if requested_country_code in ALL_COUNTRIES else DEFAULT_COUNTRY_CODE
      resolved_asin = self.fallback_asin
    else:
      # Country is not supported, and no fallback ASIN is provided, so use the default country and the main ASIN.
      resolved_country = DEFAULT_COUNTRY_CODE
      resolved_asin = self.asin
    return resolved_country, resolved_asin


AMAZON_REDIRECTS: dict[str, AmazonRedirectConfig] = {
  # Cute & Silly Animal Jokes - Product Page
  'book-animal-jokes':
  AmazonRedirectConfig(
    asin='B0G7F82P65',
    fallback_asin='B0G9765J19',
    page_type=AmazonRedirectPageType.PRODUCT,
    label='Cute & Silly Animal Jokes - Paperback',
    description='Redirects to the product page for the animal joke book.',
    supported_countries=BOOK_PRINT_COUNTRIES,
  ),

  # Cute & Silly Animal Jokes - Review Pages
  'review-animal-jokes':
  AmazonRedirectConfig(
    asin='B0G7F82P65',
    page_type=AmazonRedirectPageType.REVIEW,
    label='Cute & Silly Animal Jokes - Paperback Reviews',
    description=
    'Redirects to the customer review page for the animal joke book.',
    supported_countries=BOOK_PRINT_COUNTRIES,
    apply_attribution=False,
  ),
  'review-animal-jokes-ebook':
  AmazonRedirectConfig(
    asin='B0G9765J19',
    page_type=AmazonRedirectPageType.REVIEW,
    label='Cute & Silly Animal Jokes - Ebook Reviews',
    description=
    'Redirects to the customer review page for the animal joke book.',
    apply_attribution=False,
  ),
}

AMAZON_ATTRIBUTION_TAGS: dict[tuple[str, str], str] = {
  # Cute & Silly Animal Jokes - Ebook
  ("B0G9765J19", "aa"):
  ("maas=maas_adg_88E95258EF6D9D50F8DBAADDFA5F7DE4_afap_abs&ref_=aa_maas&tag=maas"
   ),
  ("B0G9765J19", "lunchbox_thank_you"):
  ("maas=maas_adg_74E52113CF106F9D73EF19BC150AC09F_afap_abs&ref_=aa_maas&tag=maas"
   ),
  # Cute & Silly Animal Jokes - Paperback
  ("B0G7F82P65", "aa"):
  ("maas=maas_adg_283BD8DDB074184DB7B5EBB2ED3EC3E7_afap_abs&ref_=aa_maas&tag=maas"
   ),
  ("B0G7F82P65", "lunchbox_thank_you"):
  ("maas=maas_adg_92547F51E50DB214BCBCD9D297E81344_afap_abs&ref_=aa_maas&tag=maas"
   ),
}
"""Attribution query strings keyed by (ASIN, source) pairs."""


def normalize_country_code(country_code: str | None) -> str | None:
  """Normalize a user-provided country code for lookup."""
  if not country_code:
    return None
  country_code = country_code.strip().upper()
  return country_code or None


def get_amazon_domain(country_code: str | None) -> str:
  """Return the Amazon domain for the provided country code."""
  normalized = normalize_country_code(country_code)
  if not normalized:
    return DEFAULT_DOMAIN
  return COUNTRY_TO_DOMAIN.get(normalized, DEFAULT_DOMAIN)


def _normalize_source(source: str | None) -> str | None:
  """Normalize a source parameter by trimming whitespace only."""
  if source is None:
    return None
  stripped = source.strip()
  return stripped or None


def _get_attribution_tag(asin: str, source: str | None) -> str | None:
  """Return the attribution query for a given ASIN/source pair."""
  normalized_source = _normalize_source(source)
  if not normalized_source:
    return None
  tag = AMAZON_ATTRIBUTION_TAGS.get((asin, normalized_source))
  if not tag:
    logger.warn(
      f"Unknown Amazon attribution source '{normalized_source}' for ASIN {asin}"
    )
  return tag


def _apply_attribution_tag(base_url: str,
                           attribution_query: str | None) -> str:
  """Return `base_url` with attribution params merged into its query."""
  if not attribution_query:
    return base_url
  query = attribution_query.lstrip("?")
  parsed = urllib.parse.urlparse(base_url)
  if not parsed.netloc and parsed.path:
    parsed = urllib.parse.urlparse(f"https://{base_url.lstrip('/')}")
  existing_params = urllib.parse.parse_qsl(parsed.query,
                                           keep_blank_values=True)
  attribution_params = urllib.parse.parse_qsl(query, keep_blank_values=True)
  attribution_keys = {key for key, _ in attribution_params}
  merged_params = [(key, value) for key, value in existing_params
                   if key not in attribution_keys]
  merged_params.extend(attribution_params)
  merged_query = urllib.parse.urlencode(merged_params)
  rebuilt = parsed._replace(query=merged_query)
  return urllib.parse.urlunparse(rebuilt)
