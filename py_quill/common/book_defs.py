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
  ARCHIVED_BOOKS = "archived-books"


@dataclasses.dataclass(frozen=True)
class BookVariant:
  """A specific book format and its Amazon data."""

  asin: str
  format: BookFormat = BookFormat.PAPERBACK
  print_cost: float = 0.0
  royalty_rate: float = 0.0
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
        format=BookFormat.PAPERBACK,
        print_cost=2.91,
        royalty_rate=0.6,
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
        format=BookFormat.PAPERBACK,
        print_cost=2.91,
        royalty_rate=0.6,
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
  BookKey.ARCHIVED_BOOKS:
  Book(
    title="Archived Books",
    variants={
      BookFormat.PAPERBACK:
      BookVariant(
        # Animal Jokes premium color paperback
        asin='B0G7F82P65',
        format=BookFormat.PAPERBACK,
        print_cost=5.88,
        royalty_rate=0.6,
      ),
      BookFormat.EBOOK:
      BookVariant(
        # Valentine's Day premium color ebook
        asin='B0GKYSMX7P',
        format=BookFormat.PAPERBACK,
        print_cost=5.88,
        royalty_rate=0.6,
      ),
    },
  ),
}

BOOK_VARIANTS_BY_ASIN: dict[str, BookVariant] = {
  variant.asin: variant
  for book in BOOKS.values()
  for variant in book.variants.values()
}
