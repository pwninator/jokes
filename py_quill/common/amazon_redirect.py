"""Helpers for building Amazon URLs that respect country-specific domains."""

from __future__ import annotations

import dataclasses
import enum
import urllib.parse

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
  supported_countries: frozenset[str] | None = None

  def base_url(self) -> str:
    """Return the canonical US Amazon URL for this config."""
    match self.page_type:
      case AmazonRedirectPageType.PRODUCT:
        return (f"https://www.{DEFAULT_DOMAIN}/"
                f"Cute-Silly-Animal-Jokes-Snickerdoodle/dp/{self.asin}")
      case AmazonRedirectPageType.REVIEW:
        return (f"https://www.{DEFAULT_DOMAIN}/review/create-review/"
                f"?ie=UTF8&asin={self.asin}")

  def resolve_country_code(self, requested_code: str | None) -> str:
    """Return a supported country code for this redirect."""
    normalized = normalize_country_code(requested_code) or DEFAULT_COUNTRY_CODE
    if not self.supported_countries:
      return normalized
    if normalized in self.supported_countries:
      return normalized
    return DEFAULT_COUNTRY_CODE

  def supported_country_list(self) -> list[str] | None:
    """Return sorted supported country codes or None if global."""
    if not self.supported_countries:
      return None
    return sorted(self.supported_countries)


AMAZON_REDIRECTS: dict[str, AmazonRedirectConfig] = {
  # Cute & Silly Animal Jokes - Paperback
  'review-animal-jokes':
  AmazonRedirectConfig(
    asin='B0G7F82P65',
    page_type=AmazonRedirectPageType.REVIEW,
    label='Cute & Silly Animal Jokes - Paperback Reviews',
    description=
    'Redirects to the customer review page for the animal joke book.',
    supported_countries=BOOK_PRINT_COUNTRIES,
  ),
  'book-animal-jokes':
  AmazonRedirectConfig(
    asin='B0G7F82P65',
    page_type=AmazonRedirectPageType.PRODUCT,
    label='Cute & Silly Animal Jokes - Paperback',
    description='Redirects to the product page for the animal joke book.',
    supported_countries=BOOK_PRINT_COUNTRIES,
  ),

  # Cute & Silly Animal Jokes - Ebook
  'review-animal-jokes-ebook':
  AmazonRedirectConfig(
    asin='B0G9765J19',
    page_type=AmazonRedirectPageType.REVIEW,
    label='Cute & Silly Animal Jokes - Ebook Reviews',
    description=
    'Redirects to the customer review page for the animal joke book.',
  ),
  'book-animal-jokes-ebook':
  AmazonRedirectConfig(
    asin='B0G9765J19',
    page_type=AmazonRedirectPageType.PRODUCT,
    label='Cute & Silly Animal Jokes - Ebook',
    description='Redirects to the product page for the animal joke book.',
  ),
}


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


def _apply_affiliate_tag(query: str, affiliate_tag: str | None) -> str:
  """Return a query string with the affiliate tag injected or replaced."""
  if not affiliate_tag:
    return query
  params = urllib.parse.parse_qsl(query, keep_blank_values=True)
  updated = False
  for idx, (key, _) in enumerate(params):
    if key == "tag":
      params[idx] = ("tag", affiliate_tag)
      updated = True
      break
  if not updated:
    params.append(("tag", affiliate_tag))
  return urllib.parse.urlencode(params)


def transform_amazon_url(
  base_url: str,
  country_code: str | None,
  *,
  affiliate_tag: str | None = None,
) -> str:
  """Return `base_url` rewritten to the domain for `country_code`.

  Args:
    base_url: The original Amazon URL (product page, review page, etc.).
    country_code: ISO 3166-1 alpha-2 country code (case-insensitive).
    affiliate_tag: Optional Amazon Associates tag.

  Raises:
    ValueError: If `base_url` is empty or malformed.
  """
  if not base_url:
    raise ValueError("base_url is required")

  parsed = urllib.parse.urlparse(base_url)
  if not parsed.netloc and parsed.path:
    parsed = urllib.parse.urlparse(f"https://{base_url.lstrip('/')}")

  scheme = parsed.scheme or "https"
  domain = get_amazon_domain(country_code)
  netloc = f"www.{domain}"
  query = _apply_affiliate_tag(parsed.query, affiliate_tag)

  rebuilt = parsed._replace(scheme=scheme, netloc=netloc, query=query)
  return urllib.parse.urlunparse(rebuilt)
