"""KDP xlsx parsing helpers for daily sales and KENP stats."""

from __future__ import annotations

import datetime
import io
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import openpyxl
from common import book_defs, models

_CURRENCY_CODE_TO_USD_RATE: dict[str, float] = {
  "USD": 1.0,
  "CAD": 0.7320,
  "GBP": 1.3569,
}


class AmazonKdpError(Exception):
  """Raised when KDP report parsing or validation fails."""


@dataclass(kw_only=True)
class _DailyAggregate:
  """Mutable aggregate for one date while parsing report rows."""

  kenp_pages_read: int = 0
  ebook_units_sold: int = 0
  paperback_units_sold: int = 0
  hardcover_units_sold: int = 0
  total_royalties_usd: float = 0.0
  ebook_royalties_usd: float = 0.0
  paperback_royalties_usd: float = 0.0
  hardcover_royalties_usd: float = 0.0
  total_print_cost_usd: float = 0.0
  sale_items_by_asin: dict[str, models.AmazonProductStats] = field(
    default_factory=dict)


def parse_kdp_xlsx(file_bytes: bytes) -> list[models.AmazonKdpDailyStats]:
  """Parse a KDP dashboard xlsx into daily stats models."""
  if not file_bytes:
    raise AmazonKdpError("KDP xlsx upload was empty")

  workbook = _load_workbook(file_bytes)
  combined_sales = _read_sheet_rows(workbook, "Combined Sales")
  kenp_rows = _read_sheet_rows(workbook, "KENP Read")

  aggregates_by_date: dict[datetime.date,
                           _DailyAggregate] = defaultdict(_DailyAggregate)
  _apply_combined_sales_rows(combined_sales, aggregates_by_date)
  _apply_kenp_rows(kenp_rows, aggregates_by_date)

  output: list[models.AmazonKdpDailyStats] = []
  for date_value in sorted(aggregates_by_date.keys()):
    aggregate = aggregates_by_date[date_value]
    sale_items = sorted(
      aggregate.sale_items_by_asin.values(),
      key=lambda item: item.asin,
    )
    output.append(
      models.AmazonKdpDailyStats(
        date=date_value,
        total_units_sold=(aggregate.ebook_units_sold +
                          aggregate.paperback_units_sold +
                          aggregate.hardcover_units_sold),
        kenp_pages_read=aggregate.kenp_pages_read,
        ebook_units_sold=aggregate.ebook_units_sold,
        paperback_units_sold=aggregate.paperback_units_sold,
        hardcover_units_sold=aggregate.hardcover_units_sold,
        total_royalties_usd=round(aggregate.total_royalties_usd, 2),
        ebook_royalties_usd=round(aggregate.ebook_royalties_usd, 2),
        paperback_royalties_usd=round(aggregate.paperback_royalties_usd, 2),
        hardcover_royalties_usd=round(aggregate.hardcover_royalties_usd, 2),
        total_print_cost_usd=round(aggregate.total_print_cost_usd, 2),
        sale_items=sale_items,
      ))
  return output


def _load_workbook(file_bytes: bytes) -> openpyxl.Workbook:
  """Load an xlsx workbook from in-memory bytes."""
  try:
    return openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
  except Exception as exc:
    raise AmazonKdpError(f"Failed to parse xlsx: {exc}") from exc


def _read_sheet_rows(workbook: openpyxl.Workbook,
                     sheet_name: str) -> list[dict[str, Any]]:
  """Read a sheet into a list of dict rows keyed by header."""
  if sheet_name not in workbook.sheetnames:
    raise AmazonKdpError(f"Missing required sheet: {sheet_name}")
  sheet = workbook[sheet_name]
  all_rows = list(sheet.iter_rows(values_only=True))
  if not all_rows:
    return []

  headers_raw = all_rows[0]
  headers = [str(h).strip() if h is not None else "" for h in headers_raw]
  rows: list[dict[str, Any]] = []
  for row in all_rows[1:]:
    if all(cell is None or str(cell).strip() == "" for cell in row):
      continue
    row_dict: dict[str, Any] = {}
    for index, header in enumerate(headers):
      if not header:
        continue
      row_dict[header] = row[index] if index < len(row) else None
    rows.append(row_dict)
  return rows


def _apply_combined_sales_rows(
  rows: list[dict[str, Any]],
  aggregates_by_date: dict[datetime.date, _DailyAggregate],
) -> None:
  """Merge Combined Sales rows into daily aggregates with validations."""
  for row in rows:
    date_value = _parse_iso_date(row.get("Royalty Date"), "Royalty Date")
    asin_or_isbn = _required_str(row.get("ASIN/ISBN"), "ASIN/ISBN")
    currency_code = _required_str(row.get("Currency"), "Currency").upper()

    book_variant = book_defs.find_book_variant(asin_or_isbn)
    if book_variant is None:
      raise AmazonKdpError(f"Unknown ASIN/ISBN in KDP report: {asin_or_isbn}")

    format_name = _format_from_transaction_type(row.get("Transaction Type"))
    if book_variant.format.value != format_name:
      raise AmazonKdpError(
        f"Format mismatch for {asin_or_isbn}: report={format_name} book_defs={book_variant.format.value}"
      )

    net_units_sold = _as_int(row.get("Net Units Sold"))
    avg_offer_price_usd = _convert_amount_to_usd(
      _as_float(row.get("Avg. Offer Price without tax")),
      currency_code=currency_code,
    )

    royalty_usd = _convert_amount_to_usd(
      _as_float(row.get("Royalty")),
      currency_code=currency_code,
    )
    print_cost_per_unit_usd = _convert_amount_to_usd(
      _as_float(row.get("Avg. Delivery/Manufacturing cost")),
      currency_code=currency_code,
    )

    sales_amount_usd = avg_offer_price_usd * net_units_sold
    print_cost_usd = print_cost_per_unit_usd * net_units_sold

    aggregate = aggregates_by_date[date_value]
    if format_name == "ebook":
      aggregate.ebook_units_sold += net_units_sold
      aggregate.ebook_royalties_usd += royalty_usd
    elif format_name == "paperback":
      aggregate.paperback_units_sold += net_units_sold
      aggregate.paperback_royalties_usd += royalty_usd
    else:
      aggregate.hardcover_units_sold += net_units_sold
      aggregate.hardcover_royalties_usd += royalty_usd

    aggregate.total_royalties_usd += royalty_usd
    aggregate.total_print_cost_usd += print_cost_usd

    canonical_asin = book_variant.asin
    existing = aggregate.sale_items_by_asin.setdefault(
      canonical_asin,
      models.AmazonProductStats(
        asin=canonical_asin,
        total_print_cost_usd=0.0,
        total_royalty_usd=0.0,
      ))
    existing.units_sold += net_units_sold
    existing.total_sales_usd += sales_amount_usd
    existing.total_profit_usd += royalty_usd
    existing.total_royalty_usd = (existing.total_royalty_usd
                                  or 0.0) + royalty_usd
    existing.total_print_cost_usd = (existing.total_print_cost_usd
                                     or 0.0) + print_cost_usd


def _apply_kenp_rows(
  rows: list[dict[str, Any]],
  aggregates_by_date: dict[datetime.date, _DailyAggregate],
) -> None:
  """Merge KENP Read rows into daily aggregates."""
  for row in rows:
    date_value = _parse_iso_date(row.get("Date"), "Date")
    asin = _required_str(row.get("ASIN"), "ASIN")
    book_variant = book_defs.find_book_variant(asin)
    if book_variant is None:
      raise AmazonKdpError(f"Unknown ASIN in KENP Read sheet: {asin}")
    kenp_pages_read = _as_int(
      row.get("Kindle Edition Normalized Page (KENP) Read"))
    aggregate = aggregates_by_date[date_value]
    aggregate.kenp_pages_read += kenp_pages_read

    canonical_asin = book_variant.asin
    existing = aggregate.sale_items_by_asin.setdefault(
      canonical_asin,
      models.AmazonProductStats(
        asin=canonical_asin,
        total_print_cost_usd=0.0,
        total_royalty_usd=0.0,
      ))
    existing.kenp_pages_read += kenp_pages_read


def _format_from_transaction_type(value: Any) -> str:
  """Normalize KDP transaction type to format names used in book_defs."""
  transaction_type = _required_str(value, "Transaction Type").lower()
  if "hardcover" in transaction_type:
    return "hardcover"
  if "paperback" in transaction_type:
    return "paperback"
  return "ebook"


def _convert_amount_to_usd(amount: float, *, currency_code: str) -> float:
  """Convert a currency amount into USD."""
  if amount == 0.0:
    return 0.0
  rate = _CURRENCY_CODE_TO_USD_RATE.get(currency_code.upper())
  if rate is None:
    raise AmazonKdpError(
      f"Unsupported currency for KDP report: {currency_code}")
  return amount * rate


def _required_str(value: Any, field_name: str) -> str:
  """Return stripped string or raise when missing."""
  result = str(value).strip() if value is not None else ""
  if not result:
    raise AmazonKdpError(f"{field_name} is required")
  return result


def _as_float(value: Any) -> float:
  """Coerce an incoming value to float."""
  if value is None:
    return 0.0
  if isinstance(value, str) and value.strip().upper() in {"", "N/A"}:
    return 0.0
  return float(value)


def _as_int(value: Any) -> int:
  """Coerce an incoming value to int."""
  return int(round(_as_float(value)))


def _parse_iso_date(value: Any, field_name: str) -> datetime.date:
  """Parse strict ISO date in yyyy-mm-dd format."""
  raw_value = _required_str(value, field_name)
  try:
    return datetime.date.fromisoformat(raw_value)
  except ValueError as exc:
    raise AmazonKdpError(
      f"{field_name} must be in YYYY-MM-DD format: {raw_value}") from exc
