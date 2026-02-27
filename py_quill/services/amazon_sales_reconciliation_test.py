"""Tests for KDP vs ads sales reconciliation."""

from __future__ import annotations

import datetime
from collections import deque

from common import models
from services import amazon_sales_reconciliation
from services import firestore


def _build_ads_daily_stat(
  date_value: datetime.date,
  *,
  asin: str,
  units: int,
  country_code: str = "US",
  kenp_pages_read: int = 0,
) -> models.AmazonAdsDailyStats:
  campaign = models.AmazonAdsDailyCampaignStats(
    campaign_id="campaign-1",
    campaign_name="Campaign 1",
    date=date_value,
    total_units_sold=units,
    kenp_pages_read=kenp_pages_read,
    sale_items_by_asin_country={
      asin: {
        country_code:
        models.AmazonProductStats(
          asin=asin,
          units_sold=units,
          kenp_pages_read=kenp_pages_read,
          total_sales_usd=0.0,
          total_profit_usd=0.0,
        )
      }
    },
  )
  return models.AmazonAdsDailyStats(
    date=date_value,
    total_units_sold=units,
    campaigns_by_id={
      campaign.campaign_id: campaign,
    },
  )


def _build_kdp_daily_stat(
  date_value: datetime.date,
  *,
  asin: str,
  units: int,
  country_code: str = "US",
  kenp_pages_read: int = 0,
  sales_usd: float,
  royalty_usd: float,
  print_cost_usd: float,
) -> models.AmazonKdpDailyStats:
  return models.AmazonKdpDailyStats(
    date=date_value,
    total_units_sold=units,
    total_royalties_usd=royalty_usd,
    total_print_cost_usd=print_cost_usd,
    sale_items_by_asin_country={
      asin: {
        country_code:
        models.AmazonProductStats(
          asin=asin,
          units_sold=units,
          kenp_pages_read=kenp_pages_read,
          total_sales_usd=sales_usd,
          total_profit_usd=royalty_usd,
          total_print_cost_usd=print_cost_usd,
          total_royalty_usd=royalty_usd,
        )
      }
    },
  )


def test_reconcile_daily_sales_uses_seed_and_matches_earliest_unmatched_lot(
    monkeypatch):
  asin = "B0G9765J19"
  changed_date = datetime.date(2026, 1, 20)
  run_time_utc = datetime.datetime(2026, 1, 30, tzinfo=datetime.timezone.utc)

  def _bounds(collection_name: str):
    if collection_name == firestore.AMAZON_ADS_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 1, 1), datetime.date(2026, 1, 20))
    if collection_name == firestore.AMAZON_KDP_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 1, 10), datetime.date(2026, 1, 20))
    return None

  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_get_collection_date_bounds",
    _bounds,
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [],
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_kdp_daily_stats",
    lambda *, start_date, end_date: [
      _build_kdp_daily_stat(
        datetime.date(2026, 1, 10),
        asin=asin,
        units=1,
        sales_usd=10.0,
        royalty_usd=4.0,
        print_cost_usd=2.0,
      ),
      _build_kdp_daily_stat(
        datetime.date(2026, 1, 20),
        asin=asin,
        units=1,
        sales_usd=10.0,
        royalty_usd=4.0,
        print_cost_usd=2.0,
      ),
    ],
  )
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_load_seed_lots",
    lambda seed_date: {
      amazon_sales_reconciliation._AsinCountryKey(asin=asin, country_code="US"):
      deque([
        models.AmazonSalesReconciledAdsLot(
          purchase_date=datetime.date(2026, 1, 1),
          units_remaining=1,
        ),
        models.AmazonSalesReconciledAdsLot(
          purchase_date=datetime.date(2026, 1, 2),
          units_remaining=1,
        ),
      ])
    },
  )

  captured_docs: list[models.AmazonSalesReconciledDailyStats] = []
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_upsert_reconciled_docs",
    lambda docs: captured_docs.extend(docs),
  )

  stats = amazon_sales_reconciliation.reconcile_daily_sales(
    earliest_changed_date=changed_date,
    run_time_utc=run_time_utc,
  )

  assert stats["seeded_from_previous_day"] is True
  assert stats["reconciled_start_date"] == "2026-01-06"
  assert stats["reconciled_end_date"] == "2026-01-20"

  by_date = {doc.date.isoformat(): doc for doc in captured_docs}
  day_10 = by_date["2026-01-10"]
  day_20 = by_date["2026-01-20"]

  day_10_by_asin_country = day_10.by_asin_country[asin]["US"]
  assert day_10_by_asin_country.kdp_units == 1
  assert day_10_by_asin_country.ads_ship_date_units == 1
  assert day_10_by_asin_country.organic_units == 0

  day_20_by_asin_country = day_20.by_asin_country[asin]["US"]
  assert day_20_by_asin_country.kdp_units == 1
  assert day_20_by_asin_country.ads_ship_date_units == 0
  assert day_20_by_asin_country.organic_units == 1
  assert day_10.zzz_ending_unmatched_ads_lots_by_asin_country[asin]["US"][
    0].units_remaining == 1
  assert day_20.unmatched_ads_click_date_units_total == 0
  assert day_10.ads_click_date_units_total == 0


def test_reconcile_daily_sales_falls_back_to_full_recompute_when_seed_missing(
    monkeypatch):
  asin = "B0G9765J19"
  changed_date = datetime.date(2026, 1, 20)

  def _bounds(collection_name: str):
    if collection_name == firestore.AMAZON_ADS_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 1, 1), datetime.date(2026, 1, 20))
    if collection_name == firestore.AMAZON_KDP_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 1, 10), datetime.date(2026, 1, 20))
    return None

  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_get_collection_date_bounds",
    _bounds,
  )
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_load_seed_lots",
    lambda seed_date: None,
  )

  requested_ranges: list[tuple[datetime.date, datetime.date]] = []
  monkeypatch.setattr(
    firestore,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: requested_ranges.append(
      (start_date, end_date)) or [
        _build_ads_daily_stat(datetime.date(2026, 1, 1), asin=asin, units=1),
      ],
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_kdp_daily_stats",
    lambda *, start_date, end_date: requested_ranges.append(
      (start_date, end_date)) or [
        _build_kdp_daily_stat(
          datetime.date(2026, 1, 10),
          asin=asin,
          units=1,
          sales_usd=10.0,
          royalty_usd=4.0,
          print_cost_usd=2.0,
        )
      ],
  )

  captured_docs: list[models.AmazonSalesReconciledDailyStats] = []
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_upsert_reconciled_docs",
    lambda docs: captured_docs.extend(docs),
  )

  stats = amazon_sales_reconciliation.reconcile_daily_sales(
    earliest_changed_date=changed_date)

  assert stats["seeded_from_previous_day"] is False
  assert stats["reconciled_start_date"] == "2026-01-01"
  assert requested_ranges[0][0] == datetime.date(2026, 1, 1)
  assert requested_ranges[1][0] == datetime.date(2026, 1, 1)

  by_date = {doc.date.isoformat(): doc for doc in captured_docs}
  day_10_by_asin_country = by_date["2026-01-10"].by_asin_country[asin]["US"]
  assert day_10_by_asin_country.ads_ship_date_units == 1
  assert day_10_by_asin_country.organic_units == 0


def test_reconcile_daily_sales_normalizes_kdp_isbn_to_variant_asin(
    monkeypatch):
  ads_asin = "B0GNHFKQ8W"
  paperback_isbn = "9798247846802"
  changed_date = datetime.date(2026, 2, 23)

  def _bounds(collection_name: str):
    if collection_name == firestore.AMAZON_ADS_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 2, 20), datetime.date(2026, 2, 23))
    if collection_name == firestore.AMAZON_KDP_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 2, 20), datetime.date(2026, 2, 23))
    return None

  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_get_collection_date_bounds",
    _bounds,
  )
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_load_seed_lots",
    lambda seed_date: None,
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [
      _build_ads_daily_stat(datetime.date(2026, 2, 20), asin=ads_asin, units=1
                            ),
    ],
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_kdp_daily_stats",
    lambda *, start_date, end_date: [
      _build_kdp_daily_stat(
        datetime.date(2026, 2, 23),
        asin=paperback_isbn,
        units=1,
        sales_usd=11.99,
        royalty_usd=4.28,
        print_cost_usd=2.91,
      ),
    ],
  )

  captured_docs: list[models.AmazonSalesReconciledDailyStats] = []
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_upsert_reconciled_docs",
    lambda docs: captured_docs.extend(docs),
  )

  _ = amazon_sales_reconciliation.reconcile_daily_sales(
    earliest_changed_date=changed_date)

  by_date = {doc.date.isoformat(): doc for doc in captured_docs}
  day_23 = by_date["2026-02-23"]
  assert paperback_isbn not in day_23.by_asin
  assert ads_asin in day_23.by_asin
  assert day_23.by_asin_country[ads_asin]["US"].ads_ship_date_units == 1
  assert day_23.by_asin_country[ads_asin]["US"].organic_units == 0


def test_reconcile_daily_sales_records_click_date_and_unmatched_stats(
    monkeypatch):
  asin = "B0G9765J19"
  changed_date = datetime.date(2026, 1, 15)

  def _bounds(collection_name: str):
    if collection_name == firestore.AMAZON_ADS_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 1, 1), datetime.date(2026, 1, 15))
    if collection_name == firestore.AMAZON_KDP_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 1, 1), datetime.date(2026, 1, 15))
    return None

  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_get_collection_date_bounds",
    _bounds,
  )
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_load_seed_lots",
    lambda seed_date: None,
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [
      _build_ads_daily_stat(
        datetime.date(2026, 1, 1),
        asin=asin,
        units=2,
        kenp_pages_read=7,
      ),
    ],
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_kdp_daily_stats",
    lambda *, start_date, end_date: [
      _build_kdp_daily_stat(
        datetime.date(2026, 1, 5),
        asin=asin,
        units=1,
        kenp_pages_read=5,
        sales_usd=10.0,
        royalty_usd=4.0,
        print_cost_usd=2.0,
      ),
    ],
  )

  captured_docs: list[models.AmazonSalesReconciledDailyStats] = []
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_upsert_reconciled_docs",
    lambda docs: captured_docs.extend(docs),
  )

  _ = amazon_sales_reconciliation.reconcile_daily_sales(
    earliest_changed_date=changed_date)

  by_date = {doc.date.isoformat(): doc for doc in captured_docs}
  click_day = by_date["2026-01-01"]
  ship_day = by_date["2026-01-05"]

  assert ship_day.ads_ship_date_units_total == 1
  assert ship_day.organic_units_total == 0
  assert ship_day.ads_ship_date_kenp_pages_read_total == 5
  assert ship_day.organic_kenp_pages_read_total == 0

  assert click_day.ads_click_date_units_total == 1
  assert click_day.unmatched_ads_click_date_units_total == 1
  assert click_day.ads_click_date_kenp_pages_read_total == 5
  assert click_day.unmatched_ads_click_date_kenp_pages_read_total == 2
  click_stats = click_day.by_asin_country[asin]["US"]
  assert click_stats.ads_click_date_units == 1
  assert click_stats.unmatched_ads_click_date_units == 1
  assert click_stats.ads_click_date_kenp_pages_read == 5
  assert click_stats.unmatched_ads_click_date_kenp_pages_read == 2


def test_reconcile_daily_sales_matches_only_same_country(monkeypatch):
  asin = "B0G9765J19"
  changed_date = datetime.date(2026, 2, 15)

  def _bounds(collection_name: str):
    if collection_name == firestore.AMAZON_ADS_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 2, 1), datetime.date(2026, 2, 15))
    if collection_name == firestore.AMAZON_KDP_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 2, 1), datetime.date(2026, 2, 15))
    return None

  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_get_collection_date_bounds",
    _bounds,
  )
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_load_seed_lots",
    lambda seed_date: None,
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [
      _build_ads_daily_stat(
        datetime.date(2026, 2, 10),
        asin=asin,
        country_code="US",
        units=1,
      ),
    ],
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_kdp_daily_stats",
    lambda *, start_date, end_date: [
      _build_kdp_daily_stat(
        datetime.date(2026, 2, 15),
        asin=asin,
        country_code="US",
        units=1,
        sales_usd=2.99,
        royalty_usd=1.05,
        print_cost_usd=0.0,
      ),
    ],
  )

  captured_docs: list[models.AmazonSalesReconciledDailyStats] = []
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_upsert_reconciled_docs",
    lambda docs: captured_docs.extend(docs),
  )

  _ = amazon_sales_reconciliation.reconcile_daily_sales(
    earliest_changed_date=changed_date)

  by_date = {doc.date.isoformat(): doc for doc in captured_docs}
  ship_day = by_date["2026-02-15"]
  click_day = by_date["2026-02-10"]
  assert ship_day.by_asin_country[asin]["US"].ads_ship_date_units == 1
  assert ship_day.by_asin_country[asin]["US"].organic_units == 0
  assert click_day.by_asin_country[asin]["US"].ads_click_date_units == 1


def test_reconcile_daily_sales_does_not_cross_match_countries(monkeypatch):
  asin = "B0G9765J19"
  changed_date = datetime.date(2026, 2, 15)

  def _bounds(collection_name: str):
    if collection_name == firestore.AMAZON_ADS_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 2, 1), datetime.date(2026, 2, 15))
    if collection_name == firestore.AMAZON_KDP_DAILY_STATS_COLLECTION:
      return (datetime.date(2026, 2, 1), datetime.date(2026, 2, 15))
    return None

  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_get_collection_date_bounds",
    _bounds,
  )
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_load_seed_lots",
    lambda seed_date: None,
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [
      _build_ads_daily_stat(
        datetime.date(2026, 2, 10),
        asin=asin,
        country_code="US",
        units=1,
      ),
    ],
  )
  monkeypatch.setattr(
    firestore,
    "list_amazon_kdp_daily_stats",
    lambda *, start_date, end_date: [
      _build_kdp_daily_stat(
        datetime.date(2026, 2, 15),
        asin=asin,
        country_code="CA",
        units=1,
        sales_usd=2.99,
        royalty_usd=1.05,
        print_cost_usd=0.0,
      ),
    ],
  )

  captured_docs: list[models.AmazonSalesReconciledDailyStats] = []
  monkeypatch.setattr(
    amazon_sales_reconciliation,
    "_upsert_reconciled_docs",
    lambda docs: captured_docs.extend(docs),
  )

  _ = amazon_sales_reconciliation.reconcile_daily_sales(
    earliest_changed_date=changed_date)

  by_date = {doc.date.isoformat(): doc for doc in captured_docs}
  ship_day = by_date["2026-02-15"]
  click_day = by_date["2026-02-10"]
  assert ship_day.by_asin_country[asin]["CA"].ads_ship_date_units == 0
  assert ship_day.by_asin_country[asin]["CA"].organic_units == 1
  assert click_day.by_asin_country[asin]["US"].ads_click_date_units == 0
  assert click_day.by_asin_country[asin][
    "US"].unmatched_ads_click_date_units == 1
