"""Book metadata definitions shared by redirect flows."""

from __future__ import annotations

import dataclasses
import enum
from typing import cast

ALL_COUNTRIES = frozenset({
  "AE",
  "AU",
  "BE",
  "BR",
  "CA",
  "DE",
  "ES",
  "FR",
  "GB",
  "IE",
  "IN",
  "IT",
  "JP",
  "MX",
  "NL",
  "PL",
  "SA",
  "SE",
  "SG",
  "UK",
  "US",
})
BOOK_PRINT_COUNTRIES = frozenset({
  "AU", "BE", "CA", "DE", "ES", "FR", "GB", "IE", "IT", "JP", "NL", "PL", "SE",
  "UK", "US"
})

EBOOK_MIN_PRICE_USD = 0.0
EBOOK_MAX_PRICE_USD = 4.0
PAPERBACK_MIN_PRICE_USD = 8.0
PAPERBACK_MAX_PRICE_USD = 15.0


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
  ANIMAL_JOKES_ARCHIVED = "animal-jokes-archived"
  VALENTINE_JOKES_ARCHIVED = "valentine-jokes-archived"


@dataclasses.dataclass(frozen=True)
class BookVariant:
  """A specific book format and its Amazon data."""

  asin: str
  isbn13: str | None = None
  format: BookFormat = BookFormat.PAPERBACK
  print_cost: float = 0.0
  royalty_rate: float = 0.0
  min_price_usd: float | None = None
  max_price_usd: float | None = None
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


BOOKS: dict[BookKey, Book] = {
  BookKey.ANIMAL_JOKES:
  Book(
    title='Cute & Silly Animal Jokes',
    variants={
      BookFormat.PAPERBACK:
      BookVariant(
        asin='B0GNHFKQ8W',
        isbn13='9798247846802',
        format=BookFormat.PAPERBACK,
        print_cost=2.91,
        royalty_rate=0.6,
        min_price_usd=PAPERBACK_MIN_PRICE_USD,
        max_price_usd=PAPERBACK_MAX_PRICE_USD,
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
        format=BookFormat.EBOOK,
        print_cost=0.0,
        royalty_rate=0.35,
        min_price_usd=EBOOK_MIN_PRICE_USD,
        max_price_usd=EBOOK_MAX_PRICE_USD,
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
        isbn13='9798248180011',
        format=BookFormat.PAPERBACK,
        print_cost=2.91,
        royalty_rate=0.6,
        min_price_usd=PAPERBACK_MIN_PRICE_USD,
        max_price_usd=PAPERBACK_MAX_PRICE_USD,
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
        asin='B0GNMFVYC5',
        format=BookFormat.EBOOK,
        print_cost=0.0,
        royalty_rate=0.35,
        min_price_usd=EBOOK_MIN_PRICE_USD,
        max_price_usd=EBOOK_MAX_PRICE_USD,
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
  BookKey.ANIMAL_JOKES_ARCHIVED:
  Book(
    title="Cute & Silly Animal Jokes (Archived)",
    variants={
      BookFormat.PAPERBACK:
      BookVariant(
        # Animal Jokes premium color paperback
        asin='B0G7F82P65',
        isbn13='9798274472616',
        format=BookFormat.PAPERBACK,
        print_cost=5.88,
        royalty_rate=0.6,
        min_price_usd=PAPERBACK_MIN_PRICE_USD,
        max_price_usd=PAPERBACK_MAX_PRICE_USD,
      ),
    }),
  BookKey.VALENTINE_JOKES_ARCHIVED:
  Book(
    title="Cute & Silly Valentine's Day Jokes (Archived)",
    variants={
      BookFormat.PAPERBACK:
      BookVariant(
        # Valentine's Day premium color ebook
        asin='B0GKYSMX7P',
        isbn13='9798246291917',
        format=BookFormat.PAPERBACK,
        print_cost=5.88,
        royalty_rate=0.6,
        min_price_usd=PAPERBACK_MIN_PRICE_USD,
        max_price_usd=PAPERBACK_MAX_PRICE_USD,
      ),
    },
  ),
}

BOOK_VARIANTS_BY_ASIN: dict[str, BookVariant] = {
  variant.asin: variant
  for book in BOOKS.values()
  for variant in book.variants.values()
}

BOOK_VARIANTS_BY_ISBN13: dict[str, BookVariant] = {
  variant.isbn13: variant
  for book in BOOKS.values()
  for variant in book.variants.values() if variant.isbn13
}
BOOK_KEY_BY_VARIANT_ASIN: dict[str, BookKey] = {
  variant.asin: book_key
  for book_key, book in BOOKS.items()
  for variant in book.variants.values()
}
BOOK_KEY_BY_VARIANT_ISBN13: dict[str, BookKey] = {
  variant.isbn13: book_key
  for book_key, book in BOOKS.items()
  for variant in book.variants.values() if variant.isbn13
}


def find_book_variant(asin_or_isbn13: str) -> BookVariant | None:
  """Find a book variant by ASIN or ISBN-13."""
  return BOOK_VARIANTS_BY_ASIN.get(
    asin_or_isbn13) or BOOK_VARIANTS_BY_ISBN13.get(asin_or_isbn13)


def canonical_variant_asin(asin_or_isbn13: str) -> str | None:
  """Return canonical variant ASIN for an ASIN/ISBN identifier."""
  identifier = asin_or_isbn13.strip()
  if not identifier:
    return None
  book_variant = find_book_variant(identifier)
  if book_variant is None:
    return None
  return book_variant.asin


def ads_kenp_variant_asin(asin_or_isbn13: str) -> str | None:
  """Return the ASIN that ads KENP should be attributed to for a variant.

  Sponsored Products advertised-product rows can report KENP on the advertised
  paperback ASIN even when the read actually belongs to the ebook variant of the
  same book. When a book has both paperback and ebook variants, attribute ads
  KENP to the ebook ASIN. Otherwise keep the canonical input ASIN.
  """
  canonical_asin = canonical_variant_asin(asin_or_isbn13)
  if canonical_asin is None:
    return None
  book = find_book(asin_or_isbn13)
  if book is None:
    return canonical_asin

  book_variant = find_book_variant(asin_or_isbn13)
  if book_variant is None or book_variant.format != BookFormat.PAPERBACK:
    return canonical_asin

  ebook_variant = book.variants.get(BookFormat.EBOOK)
  if ebook_variant is None:
    return canonical_asin
  return ebook_variant.asin


def find_book(asin_or_isbn13: str) -> Book | None:
  """Find a book by any of its variant ASIN/ISBN identifiers."""
  book_key = (BOOK_KEY_BY_VARIANT_ASIN.get(asin_or_isbn13)
              or BOOK_KEY_BY_VARIANT_ISBN13.get(asin_or_isbn13))
  if not book_key:
    return None
  return BOOKS.get(book_key)
