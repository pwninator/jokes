"""Tests for Amazon Ads search-term Firestore helpers."""

from __future__ import annotations

import datetime

import pytest
from models import amazon_ads_models
from storage import amazon_ads_firestore


def _build_stat(
  *,
  date_value: datetime.date = datetime.date(2026, 2, 20),
  search_term: str = "dad jokes",
) -> amazon_ads_models.AmazonAdsSearchTermDailyStat:
  return amazon_ads_models.AmazonAdsSearchTermDailyStat(
    date=date_value,
    profile_id="profile-1",
    profile_country="US",
    region="na",
    campaign_id="c1",
    campaign_name="Campaign 1",
    ad_group_id="ag1",
    ad_group_name="Ad Group 1",
    search_term=search_term,
    keyword_id="k1",
    keyword="dad joke",
    targeting="",
    keyword_type="EXACT",
    match_type="EXACT",
    ad_keyword_status="ENABLED",
    impressions=100,
    clicks=10,
    cost_usd=15.0,
    sales14d_usd=40.0,
    purchases14d=2,
    units_sold_clicks14d=2,
    kenp_pages_read14d=0,
    kenp_royalties14d_usd=0.0,
    currency_code="USD",
    source_report_id="report-1",
    source_report_name="report-name",
  )


def test_upsert_amazon_ads_search_term_daily_stats_uses_stat_key(monkeypatch):
  captured: dict[str, object] = {}

  class DummyBatch:

    def set(self, doc_ref, data, merge=False):
      captured["doc_ref"] = doc_ref
      captured["data"] = data
      captured["merge"] = merge

    def commit(self):
      captured["committed"] = True

  class DummyCollection:

    def document(self, doc_id):
      captured["doc_id"] = doc_id
      return f"doc::{doc_id}"

  class DummyDB:

    def batch(self):
      return DummyBatch()

    def collection(self, name):
      captured["collection"] = name
      return DummyCollection()

  monkeypatch.setattr(amazon_ads_firestore.firestore, "db", lambda: DummyDB())
  stat = _build_stat()

  saved = amazon_ads_firestore.upsert_amazon_ads_search_term_daily_stats([stat])

  assert len(saved) == 1
  assert saved[0].key
  assert captured["collection"] == (
    amazon_ads_firestore.AMAZON_ADS_SEARCH_TERM_DAILY_STATS_COLLECTION)
  assert captured["doc_id"] == stat.key
  assert captured["doc_ref"] == f"doc::{stat.key}"
  assert captured["merge"] is True
  assert captured["committed"] is True
  assert isinstance(captured["data"], dict)
  assert captured["data"]["search_term"] == "dad jokes"
  assert captured["data"]["cost_usd"] == 15.0


def test_upsert_amazon_ads_search_term_daily_stats_is_deterministic(monkeypatch):
  writes: list[str] = []

  class DummyBatch:

    def set(self, doc_ref, data, merge=False):
      del data, merge
      writes.append(str(doc_ref))

    def commit(self):
      return None

  class DummyCollection:

    def document(self, doc_id):
      return doc_id

  class DummyDB:

    def batch(self):
      return DummyBatch()

    def collection(self, _name):
      return DummyCollection()

  monkeypatch.setattr(amazon_ads_firestore.firestore, "db", lambda: DummyDB())
  stat_a = _build_stat()
  stat_b = _build_stat()

  _ = amazon_ads_firestore.upsert_amazon_ads_search_term_daily_stats([stat_a])
  _ = amazon_ads_firestore.upsert_amazon_ads_search_term_daily_stats([stat_b])

  assert len(writes) == 2
  assert writes[0] == writes[1]


def test_list_amazon_ads_search_term_daily_stats_filters_by_date(monkeypatch):
  captured_filters: list[object] = []

  class DummyFieldFilter:

    def __init__(self, field_path, op_string, value):
      self.field_path = field_path
      self.op_string = op_string
      self.value = value

  class DummyDoc:
    exists = True
    id = "2026-02-20__profile-1__abc123"

    def to_dict(self):
      return _build_stat().to_dict()

  class DummyQuery:

    def where(self, *, filter):
      captured_filters.append(filter)
      return self

    def order_by(self, _field_path, direction=None):
      del direction
      return self

    def stream(self):
      return [DummyDoc()]

  class DummyCollection:

    def where(self, *, filter):
      return DummyQuery().where(filter=filter)

  class DummyDB:

    def collection(self, _name):
      return DummyCollection()

  monkeypatch.setattr(amazon_ads_firestore, "FieldFilter", DummyFieldFilter)
  monkeypatch.setattr(amazon_ads_firestore.firestore, "db", lambda: DummyDB())

  rows = amazon_ads_firestore.list_amazon_ads_search_term_daily_stats(
    start_date=datetime.date(2026, 2, 1),
    end_date=datetime.date(2026, 2, 28),
  )

  assert len(rows) == 1
  assert rows[0].key == "2026-02-20__profile-1__abc123"
  assert rows[0].search_term == "dad jokes"
  assert len(captured_filters) == 2
  assert captured_filters[0].field_path == "date"
  assert captured_filters[0].op_string == ">="
  assert captured_filters[0].value == "2026-02-01"
  assert captured_filters[1].field_path == "date"
  assert captured_filters[1].op_string == "<="
  assert captured_filters[1].value == "2026-02-28"


def test_list_amazon_ads_search_term_daily_stats_invalid_range_raises():
  with pytest.raises(ValueError, match="end_date must be on or after start_date"):
    _ = amazon_ads_firestore.list_amazon_ads_search_term_daily_stats(
      start_date=datetime.date(2026, 3, 1),
      end_date=datetime.date(2026, 2, 1),
    )

