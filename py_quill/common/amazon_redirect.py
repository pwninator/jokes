"""Helpers for building Amazon URLs that respect country-specific domains."""

from __future__ import annotations

import dataclasses
import enum
import urllib.parse
from typing import cast

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


class BookFormat(enum.Enum):
  """Supported Amazon formats for a book."""
  PAPERBACK = ("paperback", "Paperback")
  EBOOK = ("ebook", "Ebook")

  def __new__(cls, value: str, label: str):
    obj = object.__new__(cls)
    obj._value_ = value
    obj._label = label  # pyright: ignore[reportAttributeAccessIssue]
    return obj

  @property
  def label(self) -> str:
    """Human-readable label for the format."""
    return cast(str,
                self._label)  # pyright: ignore[reportAttributeAccessIssue]


class AttributionSource(enum.Enum):
  """Known attribution sources for Amazon redirects."""
  AA = "aa"
  LUNCHBOX_THANK_YOU = "lunchbox_thank_you"
  WEB_BOOK_PAGE = "web_book_page"
  PRINTABLE_QR_CODE = "pqc"


class BookKey(enum.Enum):
  """Identifiers for supported books."""
  ANIMAL_JOKES = "animal-jokes"
  VALENTINE_JOKES = "valentine-jokes"


class AmazonRedirectPageType(enum.Enum):
  """Type of Amazon page to redirect to."""
  PRODUCT = "product"
  REVIEW = "review"


@dataclasses.dataclass(frozen=True)
class BookVariant:
  """A specific book format and its Amazon data."""

  asin: str
  supported_countries: frozenset[str] = ALL_COUNTRIES
  attribution_tags: dict[AttributionSource,
                         str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Book:
  """Metadata for a book and its format variants."""

  title: str
  variants: dict[BookFormat, BookVariant]

  def variant_for(self, book_format: BookFormat) -> BookVariant:
    """Return the variant for the given format."""
    variant = self.variants.get(book_format)
    if not variant:
      raise KeyError(f"Missing book variant for format {book_format.value}")
    return variant


@dataclasses.dataclass(frozen=True)
class AmazonRedirectConfig:
  """Definition for a redirect target."""

  book_key: BookKey
  page_type: AmazonRedirectPageType
  description: str
  format: BookFormat | None = None

  def __post_init__(self) -> None:
    if self.page_type == AmazonRedirectPageType.REVIEW:
      if self.format is None:
        raise ValueError("Review redirects require a format.")
    elif self.format is not None:
      raise ValueError("Product redirects do not support format overrides.")

  @property
  def label(self) -> str:
    """Human-readable label for the redirect."""
    book = self._book()
    format_label = self._primary_format().label
    if self.page_type == AmazonRedirectPageType.PRODUCT:
      return f"{book.title} - {format_label}"
    return f"{book.title} - {format_label} Reviews"

  @property
  def apply_attribution(self) -> bool:
    """Whether to apply attribution tags to the target URL."""
    return self.page_type == AmazonRedirectPageType.PRODUCT

  @property
  def primary_asin(self) -> str:
    """ASIN for the primary variant."""
    return self._primary_variant().asin

  @property
  def primary_supported_countries(self) -> frozenset[str]:
    """Countries that the primary variant is supported in."""
    return self._primary_variant().supported_countries

  def resolve_target_url(
    self,
    requested_country_code: str | None,
    source: str | AttributionSource | None = None,
  ) -> tuple[str, str, str]:
    """Return the target URL, resolved country, and ASIN.

    Args:
      requested_country_code: ISO 3166-1 alpha-2 country code (case-insensitive).
      source: Source identifier used for attribution tag lookup.

    Returns:
      target_url: The target URL for the redirect.
      resolved_country: The resolved country code.
      resolved_asin: The resolved ASIN.
    """
    resolved_country, resolved_variant = self._resolve_country_and_variant(
      requested_country_code)
    target_url = self._construct_url(resolved_variant.asin, resolved_country)

    attribution_tag = _get_attribution_tag(resolved_variant, source)
    if self.apply_attribution and attribution_tag:
      target_url = _apply_attribution_tag(target_url, attribution_tag)

    return target_url, resolved_country, resolved_variant.asin

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

  def _book(self) -> Book:
    return BOOKS[self.book_key]

  def _primary_format(self) -> BookFormat:
    if self.page_type == AmazonRedirectPageType.REVIEW:
      if self.format is None:
        raise ValueError("Review redirects require a format.")
      return self.format
    return BookFormat.PAPERBACK

  def _primary_variant(self) -> BookVariant:
    return self._book().variant_for(self._primary_format())

  def _fallback_variant(self) -> BookVariant | None:
    if self.page_type != AmazonRedirectPageType.PRODUCT:
      return None
    return self._book().variants.get(BookFormat.EBOOK)

  def _resolve_country_and_variant(
    self,
    requested_country_code: str | None,
  ) -> tuple[str, BookVariant]:
    """Return a supported country code and variant for this redirect."""
    requested_country_code = normalize_country_code(
      requested_country_code) or DEFAULT_COUNTRY_CODE

    primary_variant = self._primary_variant()
    if requested_country_code in primary_variant.supported_countries:
      return requested_country_code, primary_variant

    fallback_variant = self._fallback_variant()
    if fallback_variant:
      if requested_country_code in fallback_variant.supported_countries:
        return requested_country_code, fallback_variant
      return DEFAULT_COUNTRY_CODE, fallback_variant

    return DEFAULT_COUNTRY_CODE, primary_variant


BOOKS: dict[BookKey, Book] = {
  BookKey.ANIMAL_JOKES:
  Book(
    title='Cute & Silly Animal Jokes',
    variants={
      BookFormat.PAPERBACK:
      BookVariant(
        asin='B0GNHFKQ8W',
        supported_countries=BOOK_PRINT_COUNTRIES,
        attribution_tags={
          AttributionSource.AA:
          ("maas=maas_adg_6A723A0BB792380DDC25626BCF75CEC2_afap_abs&ref_=aa_maas&tag=maas"
           ),
          AttributionSource.LUNCHBOX_THANK_YOU:
          ("maas=maas_adg_6EAAB0B82279F865D82926461F19295D_afap_abs&ref_=aa_maas&tag=maas"
           ),
          AttributionSource.WEB_BOOK_PAGE:
          ("maas=maas_adg_D9F839E029FE823F6776B65B865F1494_afap_abs&ref_=aa_maas&tag=maas"
           ),
          AttributionSource.PRINTABLE_QR_CODE:
          ("maas=maas_adg_79F411A380CF8D44AA0D8594E45FD53E_afap_abs&ref_=aa_maas&tag=maas"
           ),
        },
      ),
      BookFormat.EBOOK:
      BookVariant(
        asin='B0G9765J19',
        attribution_tags={
          AttributionSource.AA:
          ("maas=maas_adg_88E95258EF6D9D50F8DBAADDFA5F7DE4_afap_abs&ref_=aa_maas&tag=maas"
           ),
          AttributionSource.LUNCHBOX_THANK_YOU:
          ("maas=maas_adg_74E52113CF106F9D73EF19BC150AC09F_afap_abs&ref_=aa_maas&tag=maas"
           ),
          AttributionSource.WEB_BOOK_PAGE:
          ("maas=maas_adg_491AB0D3F2B3A7CC4ABF08A4C6238A15_afap_abs&ref_=aa_maas&tag=maas"
           ),
          AttributionSource.PRINTABLE_QR_CODE:
          ("maas=maas_adg_C14294AAE6E358275AB7BFB2F5EE6766_afap_abs&ref_=aa_maas&tag=maas"
           ),
        },
      ),
    },
  ),
  BookKey.VALENTINE_JOKES:
  Book(
    title="Cute & Silly Valentine's Day Jokes",
    variants={
      BookFormat.PAPERBACK:
      BookVariant(
        asin='B0GNJZXRDM',
        supported_countries=BOOK_PRINT_COUNTRIES,
        # No tags yet
        # attribution_tags={
        #   AttributionSource.AA:
        #   ("maas=maas_adg_283BD8DDB074184DB7B5EBB2ED3EC3E7_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        #   AttributionSource.LUNCHBOX_THANK_YOU:
        #   ("maas=maas_adg_92547F51E50DB214BCBCD9D297E81344_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        #   AttributionSource.WEB_BOOK_PAGE:
        #   ("maas=maas_adg_67CA692EED615032D6E3E602791A40E5_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        #   AttributionSource.PRINTABLE_QR_CODE:
        #   ("maas=maas_adg_55BD52E1D36F33FB01C05ECD64C29FD7_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        # },
      ),
      BookFormat.EBOOK:
      BookVariant(
        # TODO: Add ASIN
        asin='0000000000',
        # No tags yet
        # attribution_tags={
        #   AttributionSource.AA:
        #   ("maas=maas_adg_88E95258EF6D9D50F8DBAADDFA5F7DE4_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        #   AttributionSource.LUNCHBOX_THANK_YOU:
        #   ("maas=maas_adg_74E52113CF106F9D73EF19BC150AC09F_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        #   AttributionSource.WEB_BOOK_PAGE:
        #   ("maas=maas_adg_491AB0D3F2B3A7CC4ABF08A4C6238A15_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        #   AttributionSource.PRINTABLE_QR_CODE:
        #   ("maas=maas_adg_C14294AAE6E358275AB7BFB2F5EE6766_afap_abs&ref_=aa_maas&tag=maas"
        #    ),
        # },
      ),
    },
  ),
}

AMAZON_REDIRECTS: dict[str, AmazonRedirectConfig] = {
  # Cute & Silly Animal Jokes - Product Page
  'book-animal-jokes':
  AmazonRedirectConfig(
    book_key=BookKey.ANIMAL_JOKES,
    page_type=AmazonRedirectPageType.PRODUCT,
    description='Redirects to the product page for the animal joke book.',
  ),

  # Cute & Silly Animal Jokes - Review Pages
  'review-animal-jokes':
  AmazonRedirectConfig(
    book_key=BookKey.ANIMAL_JOKES,
    page_type=AmazonRedirectPageType.REVIEW,
    format=BookFormat.PAPERBACK,
    description=
    'Redirects to the customer review page for the animal joke book.',
  ),
  'review-animal-jokes-ebook':
  AmazonRedirectConfig(
    book_key=BookKey.ANIMAL_JOKES,
    page_type=AmazonRedirectPageType.REVIEW,
    format=BookFormat.EBOOK,
    description=
    'Redirects to the customer review page for the animal joke book.',
  ),

  # Cute & Silly Valentine's Day Jokes - Product Page
  'book-valentine-jokes':
  AmazonRedirectConfig(
    book_key=BookKey.VALENTINE_JOKES,
    page_type=AmazonRedirectPageType.PRODUCT,
    description=
    "Redirects to the product page for the Valentine's Day joke book.",
  ),

  # Cute & Silly Valentine's Day Jokes - Review Pages
  'review-valentine-jokes':
  AmazonRedirectConfig(
    book_key=BookKey.VALENTINE_JOKES,
    page_type=AmazonRedirectPageType.REVIEW,
    format=BookFormat.PAPERBACK,
    description=
    "Redirects to the customer review page for the Valentine's Day joke book.",
  ),
  'review-valentine-jokes-ebook':
  AmazonRedirectConfig(
    book_key=BookKey.VALENTINE_JOKES,
    page_type=AmazonRedirectPageType.REVIEW,
    format=BookFormat.EBOOK,
    description=
    "Redirects to the customer review page for the Valentine's Day joke book.",
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


def _normalize_source(source: str | None) -> str | None:
  """Normalize a source parameter by trimming whitespace only."""
  if not source:
    return None
  stripped = source.strip()
  return stripped or None


def _get_attribution_tag(
  variant: BookVariant,
  source: str | AttributionSource | None,
) -> str | None:
  """Return the attribution query for a given variant/source pair."""
  if source is None:
    return None
  if isinstance(source, AttributionSource):
    source_key = source
  else:
    normalized_source = _normalize_source(source)
    if not normalized_source:
      return None
    try:
      source_key = AttributionSource(normalized_source)
    except ValueError:
      logger.warn(
        f"Unknown Amazon attribution source '{source}' for ASIN {variant.asin}"
      )
      return None
  tag = variant.attribution_tags.get(source_key)
  if not tag:
    logger.warn(
      f"Unknown Amazon attribution source {source_key} for ASIN {variant.asin}"
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
