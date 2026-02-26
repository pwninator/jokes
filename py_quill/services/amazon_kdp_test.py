"""Tests for KDP xlsx parsing helpers."""

from __future__ import annotations

import datetime
import io

import openpyxl
import pytest
from services import amazon_kdp


def _build_kdp_workbook_bytes(
  *,
  combined_sales_rows: list[list[object]],
  kenp_rows: list[list[object]],
) -> bytes:
  workbook = openpyxl.Workbook()
  default_sheet = workbook.active
  workbook.remove(default_sheet)

  combined_sheet = workbook.create_sheet("Combined Sales")
  combined_sheet.append([
    "Royalty Date",
    "Title",
    "Author Name",
    "ASIN/ISBN",
    "Marketplace",
    "Royalty Type",
    "Transaction Type",
    "Units Sold",
    "Units Refunded",
    "Net Units Sold",
    "Avg. List Price without tax",
    "Avg. Offer Price without tax",
    "Avg. Delivery/Manufacturing cost",
    "Royalty",
    "Currency",
  ])
  for row in combined_sales_rows:
    combined_sheet.append(row)

  kenp_sheet = workbook.create_sheet("KENP Read")
  kenp_sheet.append([
    "Date",
    "Title",
    "Author Name",
    "ASIN",
    "Marketplace",
    "Kindle Edition Normalized Page (KENP) Read",
  ])
  for row in kenp_rows:
    kenp_sheet.append(row)

  output = io.BytesIO()
  workbook.save(output)
  return output.getvalue()


def test_parse_kdp_xlsx_aggregates_rows_and_converts_currency():
  workbook_bytes = _build_kdp_workbook_bytes(
    combined_sales_rows=[
      [
        "2026-02-25",
        "Cute & Silly Animal Jokes",
        "Amelia Blanc",
        "B0G9765J19",
        "Amazon.com",
        "35%",
        "Standard",
        1,
        0,
        1,
        2.99,
        2.99,
        "N/A",
        1.05,
        "USD",
      ],
      [
        "2026-02-25",
        "Cute & Silly Animal Jokes",
        "Amelia Blanc",
        "B0GNHFKQ8W",
        "Amazon.com",
        "60%",
        "Standard - Paperback",
        1,
        0,
        1,
        11.99,
        11.99,
        2.91,
        4.28,
        "USD",
      ],
      [
        "2026-02-24",
        "Cute & Silly Valentine's Day Jokes",
        "Amelia Blanc",
        "B0GKYSMX7P",
        "Amazon.ca",
        "60%",
        "Standard - Paperback",
        2,
        0,
        2,
        16.33,
        16.33,
        8.03,
        3.54,
        "CAD",
      ],
    ],
    kenp_rows=[
      [
        "2026-02-25",
        "Cute & Silly Animal Jokes",
        "Amelia Blanc",
        "B0G9765J19",
        "Amazon.com",
        55,
      ],
      [
        "2026-02-25",
        "Cute & Silly Valentine's Day Jokes",
        "Amelia Blanc",
        "B0GNMFVYC5",
        "Amazon.com",
        40,
      ],
    ],
  )

  stats = amazon_kdp.parse_kdp_xlsx(workbook_bytes)

  assert [s.date for s in stats] == [
    datetime.date(2026, 2, 24),
    datetime.date(2026, 2, 25),
  ]
  day_0224 = stats[0]
  day_0225 = stats[1]

  assert day_0224.paperback_units_sold == 2
  assert day_0224.total_units_sold == 2
  assert day_0224.total_royalties_usd == pytest.approx(2.59, abs=0.01)
  assert day_0224.total_print_cost_usd == pytest.approx(11.76, abs=0.01)

  assert day_0225.kenp_pages_read == 95
  assert day_0225.ebook_units_sold == 1
  assert day_0225.paperback_units_sold == 1
  assert day_0225.total_units_sold == 2
  assert day_0225.total_royalties_usd == pytest.approx(5.33, abs=0.01)
  assert day_0225.total_print_cost_usd == pytest.approx(2.91, abs=0.01)
  assert [item.asin for item in day_0225.sale_items] == [
    "B0G9765J19",
    "B0GNHFKQ8W",
  ]


def test_parse_kdp_xlsx_raises_on_format_mismatch():
  workbook_bytes = _build_kdp_workbook_bytes(
    combined_sales_rows=[[
      "2026-02-25",
      "Cute & Silly Animal Jokes",
      "Amelia Blanc",
      "B0G9765J19",
      "Amazon.com",
      "35%",
      "Standard - Paperback",
      1,
      0,
      1,
      2.99,
      2.99,
      0.0,
      1.05,
      "USD",
    ]],
    kenp_rows=[],
  )

  with pytest.raises(amazon_kdp.AmazonKdpError, match="Format mismatch"):
    amazon_kdp.parse_kdp_xlsx(workbook_bytes)


def test_parse_kdp_xlsx_raises_on_print_cost_mismatch():
  workbook_bytes = _build_kdp_workbook_bytes(
    combined_sales_rows=[[
      "2026-02-25",
      "Cute & Silly Animal Jokes",
      "Amelia Blanc",
      "B0GNHFKQ8W",
      "Amazon.com",
      "60%",
      "Standard - Paperback",
      1,
      0,
      1,
      11.99,
      11.99,
      1.00,
      4.28,
      "USD",
    ]],
    kenp_rows=[],
  )

  with pytest.raises(amazon_kdp.AmazonKdpError, match="Print cost mismatch"):
    amazon_kdp.parse_kdp_xlsx(workbook_bytes)


def test_parse_kdp_xlsx_raises_on_royalty_rate_mismatch():
  workbook_bytes = _build_kdp_workbook_bytes(
    combined_sales_rows=[[
      "2026-02-25",
      "Cute & Silly Animal Jokes",
      "Amelia Blanc",
      "B0GNHFKQ8W",
      "Amazon.com",
      "60%",
      "Standard - Paperback",
      1,
      0,
      1,
      11.99,
      11.99,
      2.91,
      5.20,
      "USD",
    ]],
    kenp_rows=[],
  )

  with pytest.raises(amazon_kdp.AmazonKdpError, match="Royalty rate mismatch"):
    amazon_kdp.parse_kdp_xlsx(workbook_bytes)
