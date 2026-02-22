"""Tests for joke_auto_fns helper module."""

from __future__ import annotations

import datetime
import random
from typing import cast
from unittest.mock import MagicMock, Mock

import pytest
from common import models
from functions import joke_auto_fns
from services import amazon, firestore


@pytest.fixture(autouse=True, name='mock_logger')
def mock_logger_fixture(monkeypatch):
  """Silence firebase logger interactions during tests."""
  mock_log = Mock()
  monkeypatch.setattr('functions.joke_auto_fns.logger', mock_log)
  return mock_log


def _create_test_datetime(year=2024, month=1, day=20, hour=0, minute=0):
  """Create a test datetime in UTC timezone."""
  return datetime.datetime(year,
                           month,
                           day,
                           hour,
                           minute,
                           0,
                           tzinfo=datetime.timezone.utc)


def _setup_mock_db_and_batch(monkeypatch, docs, book_docs=None):
  """Helper to set up mock Firestore db and batch."""
  mock_batch = MagicMock()
  mock_db = MagicMock()

  def _collection_side_effect(name):
    collection = MagicMock()
    if name == "jokes":
      collection.stream.return_value = docs
    elif name == "joke_books":
      collection.stream.return_value = book_docs or []
    else:
      collection.stream.return_value = []
    return collection

  mock_db.collection.side_effect = _collection_side_effect
  mock_db.batch.return_value = mock_batch
  monkeypatch.setattr('functions.joke_auto_fns.firestore.db', lambda: mock_db)
  return mock_db, mock_batch


def _setup_decay_test_mocks(monkeypatch,
                            mock_sync=True,
                            mock_update_feed=True):
  """Helper to set up common mocks for decay tests."""
  if mock_sync:
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
  if mock_update_feed:
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
  monkeypatch.setattr(
    'common.joke_category_operations.refresh_category_caches',
    Mock(
      return_value={
        "categories_processed": 0,
        "categories_updated": 0,
        "categories_emptied": 0,
        "categories_failed": 0
      }))
  monkeypatch.setattr(
    'common.joke_category_operations.rebuild_joke_categories_index',
    Mock(return_value={}))


def _create_mock_joke_doc(joke_id: str,
                          overrides: dict | None = None) -> MagicMock:
  """Creates a mock Firestore document for a joke with complete default data."""
  now = _create_test_datetime()
  default_data = {
    "key": joke_id,
    "setup_text": f"Setup for {joke_id}",
    "punchline_text": f"Punchline for {joke_id}",
    "state": models.JokeState.PUBLISHED.value,
    "is_public": True,
    "category_id": "_uncategorized",
    "public_timestamp": now - datetime.timedelta(days=1),
    "last_recent_stats_update_time": now - datetime.timedelta(days=1),
    "num_viewed_users": 100,
    "num_saved_users": 50,
    "num_shared_users": 10,
    "num_thumbs_up": 60,
    "num_thumbs_down": 5,
    "num_viewed_users_recent": 10.0,
    "num_saved_users_recent": 5.0,
    "num_shared_users_recent": 1.0,
    "num_saved_users_fraction": 0.5,
    "num_shared_users_fraction": 0.1,
    "popularity_score": 100.0,
    "pun_theme": None,
    "phrase_topic": None,
    "tags": [],
    "for_kids": False,
    "for_adults": False,
    "seasonal": None,
    "pun_word": None,
    "punned_word": None,
    "setup_image_description": None,
    "punchline_image_description": None,
    "setup_image_prompt": None,
    "punchline_image_prompt": None,
    "setup_image_url": None,
    "punchline_image_url": None,
    "setup_image_url_upscaled": None,
    "punchline_image_url_upscaled": None,
    "all_setup_image_urls": [],
    "all_punchline_image_urls": [],
    "admin_rating": models.JokeAdminRating.UNREVIEWED.value,
    "book_id": None,
    "owner_user_id": None,
    "generation_metadata": {
      "generations": []
    },
    "random_id": None,
  }
  if overrides:
    default_data.update(overrides)

  doc = MagicMock()
  doc.exists = True
  doc.id = joke_id
  doc.reference = MagicMock()
  doc.to_dict.return_value = default_data
  return doc


def _create_mock_book_doc(book_id: str, joke_ids: list[str]) -> MagicMock:
  """Creates a mock Firestore document for a joke book."""
  doc = MagicMock()
  doc.exists = True
  doc.id = book_id
  doc.to_dict.return_value = {"jokes": joke_ids}
  return doc


class TestAdsStatsFetcher:
  """Tests for Amazon Ads stats fetcher jobs."""

  def test_internal_fetches_us_ca_uk_and_requests_reports(self, monkeypatch):
    now_utc = _create_test_datetime(2026, 2, 18, 5, 30)
    report_end_date = now_utc.date() - datetime.timedelta(days=1)
    report_start_date = report_end_date - datetime.timedelta(
      days=joke_auto_fns._ADS_STATS_REPORT_WINDOW_DAYS)
    profiles = [
      amazon.AmazonAdsProfile(
        profile_id="us-profile",
        region="na",
        api_base="https://advertising-api.amazon.com",
        country_code="US",
      ),
      amazon.AmazonAdsProfile(
        profile_id="ca-profile",
        region="na",
        api_base="https://advertising-api.amazon.com",
        country_code="CA",
      ),
      amazon.AmazonAdsProfile(
        profile_id="uk-profile",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
        country_code="UK",
      ),
      amazon.AmazonAdsProfile(
        profile_id="fr-profile",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
        country_code="FR",
      ),
    ]

    monkeypatch.setattr('functions.joke_auto_fns.amazon.get_profiles',
                        lambda region: profiles)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.list_amazon_ads_reports',
      lambda created_on_or_after: [],
    )
    sleep_calls: list[int] = []
    monkeypatch.setattr('functions.joke_auto_fns.time.sleep',
                        lambda sec: sleep_calls.append(sec))

    calls: list[dict[str, object]] = []

    def _mock_request_reports(*, profile, start_date, end_date):
      calls.append({
        "profile_id": profile.profile_id,
        "country_code": profile.country_code,
        "start_date": start_date,
        "end_date": end_date,
        "region": profile.region,
      })
      return amazon.ReportPair(
        campaigns_report=amazon.AmazonAdsReport(
          report_id=f"campaigns-{profile.profile_id}",
          status="PENDING",
          report_name="Campaign report request",
          report_type_id="spCampaigns",
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
          updated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
        ),
        advertised_products_report=amazon.AmazonAdsReport(
          report_id=f"advertised-{profile.profile_id}",
          status="PENDING",
          report_name="Advertised report request",
          report_type_id="spAdvertisedProduct",
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
          updated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
        ),
        purchased_products_report=amazon.AmazonAdsReport(
          report_id=f"products-{profile.profile_id}",
          status="PENDING",
          report_name="Product report request",
          report_type_id="spPurchasedProduct",
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
          updated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
        ),
      )

    monkeypatch.setattr(
      'functions.joke_auto_fns.amazon.request_daily_campaign_stats_reports',
      _mock_request_reports)

    status_calls: list[dict[str, object]] = []

    def _mock_get_reports(*, profile_id, region, report_ids):
      status_calls.append({
        "profile_id": profile_id,
        "region": region,
        "report_ids": report_ids,
      })
      return [
        amazon.AmazonAdsReport(
          report_id=f"campaigns-{profile_id}",
          status="IN_PROGRESS",
          report_name="Campaign report",
          report_type_id="spCampaigns",
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
          updated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            tzinfo=datetime.timezone.utc,
          ),
          url="",
        ),
        amazon.AmazonAdsReport(
          report_id=f"advertised-{profile_id}",
          status="COMPLETED",
          report_name="Advertised report",
          report_type_id="spAdvertisedProduct",
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            1,
            tzinfo=datetime.timezone.utc,
          ),
          updated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            2,
            tzinfo=datetime.timezone.utc,
          ),
          generated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            2,
            tzinfo=datetime.timezone.utc,
          ),
          url="https://example.com/advertised.gz",
        ),
        amazon.AmazonAdsReport(
          report_id=f"products-{profile_id}",
          status="COMPLETED",
          report_name="Product report",
          report_type_id="spPurchasedProduct",
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            1,
            tzinfo=datetime.timezone.utc,
          ),
          updated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            3,
            tzinfo=datetime.timezone.utc,
          ),
          generated_at=datetime.datetime(
            2026,
            2,
            18,
            5,
            0,
            3,
            tzinfo=datetime.timezone.utc,
          ),
          url="https://example.com/products.gz",
        ),
      ]

    monkeypatch.setattr('functions.joke_auto_fns.amazon.get_reports',
                        _mock_get_reports)
    monkeypatch.setattr(
      'functions.joke_auto_fns.amazon.get_daily_campaign_stats_from_reports',
      lambda profile, campaigns_report, advertised_products_report,
      purchased_products_report: [],
    )

    stats = joke_auto_fns._auto_ads_stats_internal(now_utc)
    expected_selected_profiles = [
      profile for profile in profiles
      if profile.country_code in joke_auto_fns._ADS_STATS_TARGET_COUNTRY_CODES
    ]
    expected_report_count_per_profile = len(
      joke_auto_fns._ADS_STATS_REQUIRED_REPORT_TYPES)

    assert stats["report_date"] == report_end_date.isoformat()
    assert stats["report_start_date"] == report_start_date.isoformat()
    assert stats["report_end_date"] == report_end_date.isoformat()
    assert stats["profiles_considered"] == 4
    assert stats["profiles_selected"] == len(expected_selected_profiles)
    assert stats["reports_requested"] == len(expected_selected_profiles)
    assert len(calls) == len(expected_selected_profiles)
    assert sleep_calls == [5]
    called_profile_ids = {call["profile_id"] for call in calls}
    assert called_profile_ids == {
      profile.profile_id
      for profile in expected_selected_profiles
    }
    for call in calls:
      assert call["start_date"] == report_start_date
      assert call["end_date"] == report_end_date
    assert len(status_calls) == len(expected_selected_profiles)
    for call in status_calls:
      assert len(cast(list[str],
                      call["report_ids"])) == expected_report_count_per_profile
      assert cast(list[str], call["report_ids"])[0].startswith("campaigns-")
      assert cast(list[str], call["report_ids"])[1].startswith("advertised-")
      assert cast(list[str], call["report_ids"])[2].startswith("products-")
    assert (stats["reports_fetched"] == len(expected_selected_profiles) *
            expected_report_count_per_profile)
    assert stats["daily_campaign_stats_count"] == 0
    assert (len(
      cast(list[dict[str, object]],
           stats["report_metadata"])) == len(expected_selected_profiles) *
            expected_report_count_per_profile)

  def test_internal_skips_creation_when_today_reports_already_exist(
      self, monkeypatch):
    now_utc = _create_test_datetime(2026, 2, 18, 5, 30)
    report_end_date = now_utc.date() - datetime.timedelta(days=1)
    report_start_date = report_end_date - datetime.timedelta(
      days=joke_auto_fns._ADS_STATS_REPORT_WINDOW_DAYS)
    profiles = [
      amazon.AmazonAdsProfile(
        profile_id="us-profile",
        region="na",
        api_base="https://advertising-api.amazon.com",
        country_code="US",
      ),
      amazon.AmazonAdsProfile(
        profile_id="uk-profile",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
        country_code="UK",
      ),
    ]
    monkeypatch.setattr('functions.joke_auto_fns.amazon.get_profiles',
                        lambda region: profiles)

    existing_reports = [
      amazon.AmazonAdsReport(
        report_id="campaigns-us-profile",
        report_name="campaigns-us",
        status="PENDING",
        report_type_id="spCampaigns",
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="us-profile",
        profile_country="US",
        region="na",
        api_base="https://advertising-api.amazon.com",
      ),
      amazon.AmazonAdsReport(
        report_id="advertised-us-profile",
        report_name="advertised-us",
        status="PENDING",
        report_type_id="spAdvertisedProduct",
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="us-profile",
        profile_country="US",
        region="na",
        api_base="https://advertising-api.amazon.com",
      ),
      amazon.AmazonAdsReport(
        report_id="products-us-profile",
        report_name="products-us",
        status="PENDING",
        report_type_id="spPurchasedProduct",
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="us-profile",
        profile_country="US",
        region="na",
        api_base="https://advertising-api.amazon.com",
      ),
      amazon.AmazonAdsReport(
        report_id="campaigns-uk-profile",
        report_name="campaigns-uk",
        status="PENDING",
        report_type_id="spCampaigns",
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="uk-profile",
        profile_country="UK",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
      ),
      amazon.AmazonAdsReport(
        report_id="advertised-uk-profile",
        report_name="advertised-uk",
        status="PENDING",
        report_type_id="spAdvertisedProduct",
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="uk-profile",
        profile_country="UK",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
      ),
      amazon.AmazonAdsReport(
        report_id="products-uk-profile",
        report_name="products-uk",
        status="PENDING",
        report_type_id="spPurchasedProduct",
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="uk-profile",
        profile_country="UK",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
      ),
    ]
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.list_amazon_ads_reports',
      lambda created_on_or_after: existing_reports,
    )

    def _raise_request(*, profile, start_date, end_date):
      del profile, start_date, end_date
      raise AssertionError("Should not create new reports")

    monkeypatch.setattr(
      'functions.joke_auto_fns.amazon.request_daily_campaign_stats_reports',
      _raise_request)
    monkeypatch.setattr('functions.joke_auto_fns.time.sleep', lambda sec: None)

    status_calls: list[dict[str, object]] = []

    def _mock_get_reports(*, profile_id, region, report_ids):
      status_calls.append({
        "profile_id": profile_id,
        "region": region,
        "report_ids": report_ids,
      })
      return [
        amazon.AmazonAdsReport(
          report_id=report_id,
          report_name=f"{report_id}-name",
          status="COMPLETED",
          report_type_id=("spCampaigns" if "campaigns" in report_id else
                          ("spAdvertisedProduct" if "advertised" in report_id
                           else "spPurchasedProduct")),
          start_date=report_start_date,
          end_date=report_end_date,
          created_at=now_utc,
          updated_at=now_utc,
          profile_id=profile_id,
          region=region,
        ) for report_id in report_ids
      ]

    monkeypatch.setattr('functions.joke_auto_fns.amazon.get_reports',
                        _mock_get_reports)
    monkeypatch.setattr(
      'functions.joke_auto_fns.amazon.get_daily_campaign_stats_from_reports',
      lambda profile, campaigns_report, advertised_products_report,
      purchased_products_report: [
        models.AmazonAdsDailyCampaignStats(
          campaign_id=f"campaign-{profile.profile_id}",
          campaign_name=f"Campaign {profile.profile_id}",
          date=report_end_date,
          spend=10.0,
          impressions=100,
          clicks=10,
          kenp_royalties=1.0,
          total_attributed_sales=20.0,
          total_units_sold=2,
          gross_profit_before_ads=12.0,
          gross_profit=8.0,
          sale_items=[],
        )
      ],
    )
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.upsert_amazon_ads_daily_stats',
      lambda stats: stats,
    )
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.upsert_amazon_ads_report',
      lambda report: report,
    )

    stats = joke_auto_fns._auto_ads_stats_internal(now_utc)
    expected_selected_profiles = [
      profile for profile in profiles
      if profile.country_code in joke_auto_fns._ADS_STATS_TARGET_COUNTRY_CODES
    ]
    expected_report_count_per_profile = len(
      joke_auto_fns._ADS_STATS_REQUIRED_REPORT_TYPES)

    assert stats["reports_requested"] == 0
    assert (stats["reports_fetched"] == len(expected_selected_profiles) *
            expected_report_count_per_profile)
    assert stats["daily_campaign_stats_count"] == len(
      expected_selected_profiles)
    assert len(status_calls) == len(expected_selected_profiles)
    for call in status_calls:
      assert len(cast(list[str],
                      call["report_ids"])) == expected_report_count_per_profile

  def test_ads_stats_fetcher_scheduler_invokes_internal_with_scheduled_time(
      self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time
      return {}

    monkeypatch.setattr('functions.joke_auto_fns._auto_ads_stats_internal',
                        _capture)

    event = MagicMock()
    event.schedule_time = datetime.datetime(2026,
                                            2,
                                            18,
                                            13,
                                            0,
                                            tzinfo=datetime.timezone.utc)

    joke_auto_fns.auto_ads_stats_scheduler.__wrapped__(event)

    assert captured["run_time"] == event.schedule_time

  def test_ads_stats_fetcher_scheduler_falls_back_to_current_time(
      self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time
      return {}

    monkeypatch.setattr('functions.joke_auto_fns._auto_ads_stats_internal',
                        _capture)

    event = MagicMock()
    event.schedule_time = None

    joke_auto_fns.auto_ads_stats_scheduler.__wrapped__(event)

    assert captured["run_time"].tzinfo == datetime.timezone.utc

  def test_ads_stats_fetcher_http_success(self, monkeypatch):
    expected_stats = {
      "report_date":
      "2026-02-17",
      "profiles_considered":
      3,
      "profiles_selected":
      2,
      "reports_requested":
      2,
      "reports_fetched":
      1,
      "daily_campaign_stats_count":
      1,
      "report_metadata": [{
        "key": "report-key",
        "report_id": "campaigns-us-profile",
        "report_name": "campaigns-us-profile-name",
        "status": "IN_PROGRESS",
        "report_type_id": "spCampaigns",
        "start_date": "2026-02-17",
        "end_date": "2026-02-17",
        "created_at": "2026-02-18T05:00:00Z",
        "updated_at": "",
        "profile_id": "us-profile",
        "profile_country": "US",
        "region": "na",
        "api_base": "https://advertising-api.amazon.com",
        "generated_at": "",
        "file_size": None,
        "url": "https://example.com/report.gz",
        "url_expires_at": "",
        "failure_reason": "",
      }],
      "daily_campaign_stats": [{
        "profile_id": "us-profile",
        "profile_country": "US",
        "region": "na",
        "campaign_id": "campaign-id",
        "campaign_name": "Campaign Name",
        "date": "2026-02-17",
        "spend": 10.0,
        "impressions": 100,
        "clicks": 10,
        "kenp_royalties": 1.0,
        "total_attributed_sales": 20.0,
        "total_units_sold": 2,
        "gross_profit_before_ads": 12.0,
        "gross_profit": 8.0,
        "sale_items": [],
      }]
    }
    monkeypatch.setattr('functions.joke_auto_fns._auto_ads_stats_internal',
                        lambda _: expected_stats)

    response = joke_auto_fns.auto_ads_stats_http(Mock())

    html = response.data.decode("utf-8")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Ads Report Metadata" in html
    assert "campaigns-us-profile" in html
    assert "IN_PROGRESS" in html
    assert ">download<" in html
    assert "Daily Campaign Stats" in html
    assert "report_name" in html
    assert "url_expires_at" in html

  def test_ads_stats_fetcher_http_failure(self, monkeypatch):

    def _raise(_):
      raise RuntimeError("ads fetch failed")

    monkeypatch.setattr('functions.joke_auto_fns._auto_ads_stats_internal',
                        _raise)

    response = joke_auto_fns.auto_ads_stats_http(Mock())

    data = response.get_json()["data"]
    assert "ads fetch failed" in data["error"]

  def test_internal_requests_new_reports_when_all_existing_are_processed(
      self, monkeypatch):
    """Test that if existing reports are all processed, we request new ones."""
    now_utc = _create_test_datetime(2026, 2, 18, 5, 30)
    report_end_date = now_utc.date() - datetime.timedelta(days=1)
    report_start_date = report_end_date - datetime.timedelta(
      days=joke_auto_fns._ADS_STATS_REPORT_WINDOW_DAYS)
    profiles = [
      amazon.AmazonAdsProfile(
        profile_id="us-profile",
        region="na",
        api_base="https://advertising-api.amazon.com",
        country_code="US",
      ),
    ]
    monkeypatch.setattr('functions.joke_auto_fns.amazon.get_profiles',
                        lambda region: profiles)

    # Existing reports are COMPLETE and PROCESSED=True
    existing_reports = [
      amazon.AmazonAdsReport(
        report_id=f"{type_id}-us-profile",
        report_name=f"{type_id}-us",
        status="COMPLETED",
        report_type_id=type_id,
        start_date=report_start_date,
        end_date=report_end_date,
        created_at=now_utc,
        updated_at=now_utc,
        profile_id="us-profile",
        profile_country="US",
        region="na",
        api_base="https://advertising-api.amazon.com",
        processed=True,  # Crucial: Marked as processed
      )
      for type_id in [
        "spCampaigns", "spAdvertisedProduct", "spPurchasedProduct"
      ]
    ]
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.list_amazon_ads_reports',
      lambda created_on_or_after: existing_reports,
    )

    request_calls = []

    def _mock_request_reports(*, profile, start_date, end_date):
      request_calls.append(profile.profile_id)
      # Return new reports (unprocessed)
      return amazon.ReportPair(
        campaigns_report=amazon.AmazonAdsReport(
          report_id=f"new-campaigns-{profile.profile_id}",
          status="PENDING",
          report_name="New Campaign report",
          report_type_id="spCampaigns",
          start_date=start_date,
          end_date=end_date,
          created_at=now_utc,
          updated_at=now_utc,
          processed=False,
        ),
        advertised_products_report=amazon.AmazonAdsReport(
          report_id=f"new-advertised-{profile.profile_id}",
          status="PENDING",
          report_name="New Advertised report",
          report_type_id="spAdvertisedProduct",
          start_date=start_date,
          end_date=end_date,
          created_at=now_utc,
          updated_at=now_utc,
          processed=False,
        ),
        purchased_products_report=amazon.AmazonAdsReport(
          report_id=f"new-products-{profile.profile_id}",
          status="PENDING",
          report_name="New Product report",
          report_type_id="spPurchasedProduct",
          start_date=start_date,
          end_date=end_date,
          created_at=now_utc,
          updated_at=now_utc,
          processed=False,
        ),
      )

    monkeypatch.setattr(
      'functions.joke_auto_fns.amazon.request_daily_campaign_stats_reports',
      _mock_request_reports)
    monkeypatch.setattr('functions.joke_auto_fns.time.sleep', lambda sec: None)

    # For status check, just return PENDING for new reports so we don't process them in this test run
    monkeypatch.setattr('functions.joke_auto_fns.amazon.get_reports',
                        lambda **kwargs: [])

    stats = joke_auto_fns._auto_ads_stats_internal(now_utc)

    # Verify that we REQUESTED new reports
    assert stats["reports_requested"] == 1
    assert request_calls == ["us-profile"]


class TestDecayRecentJokeStats:
  """Tests for the recent joke stats decay job."""

  def test_updates_counters_when_last_update_stale_and_syncs(
      self, monkeypatch):
    """Test that stale jokes are updated and synced."""
    now_utc = _create_test_datetime()
    overrides = {
      "num_viewed_users_recent": 100,
      "num_saved_users_recent": 50,
      "num_shared_users_recent": 10,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=22),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }
    doc = _create_mock_joke_doc("joke-1", overrides=overrides)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    mock_sync = Mock()
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(return_value={}))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_viewed_users_recent"] == pytest.approx(90.0)
    assert payload["num_saved_users_recent"] == pytest.approx(45.0)
    assert payload["num_shared_users_recent"] == pytest.approx(9.0)
    assert payload["is_public"] is True
    assert payload[
      "last_recent_stats_update_time"] is firestore.SERVER_TIMESTAMP
    mock_sync.assert_called_once()

  def test_skips_when_recently_updated_and_still_syncs(self, monkeypatch):
    """Test that a recently updated joke is skipped for writes but still syncs search."""
    now_utc = _create_test_datetime()
    overrides = {
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
      "state": models.JokeState.APPROVED.value,
      "is_public": False,
    }
    doc = _create_mock_joke_doc("joke-1", overrides=overrides)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])

    mock_sync = Mock()
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(return_value={}))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)

    mock_batch.update.assert_not_called()
    mock_sync.assert_called_once()

  def test_missing_recent_fields_are_skipped(self, monkeypatch):
    """Test that if recent fields are None, only the timestamp is updated."""
    now_utc = _create_test_datetime()
    overrides = {
      "num_viewed_users_recent": None,
      "num_saved_users_recent": None,
      "num_shared_users_recent": None,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.APPROVED.value,
      "is_public": False,
    }
    doc = _create_mock_joke_doc("joke-1", overrides=overrides)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    _setup_decay_test_mocks(monkeypatch)

    joke_auto_fns._joke_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]

    # The only update should be the timestamp, as decay runs but finds no fields.
    assert payload == {
      "last_recent_stats_update_time": firestore.SERVER_TIMESTAMP
    }

  def test_recent_update_still_updates_is_public_when_mismatch(
      self, monkeypatch):
    now_utc = _create_test_datetime()
    overrides = {
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }
    doc = _create_mock_joke_doc("joke-1", overrides=overrides)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload == {"is_public": True}

  @pytest.mark.parametrize(
    "public_timestamp_offset,initial_is_public,expected_is_public",
    [
      (datetime.timedelta(hours=-1), False, True),  # Past timestamp
      (datetime.timedelta(hours=12), True, False),  # Future timestamp
    ])
  def test_daily_state_sets_is_public_based_on_public_timestamp(
      self, monkeypatch, public_timestamp_offset, initial_is_public,
      expected_is_public):
    now_utc = _create_test_datetime()
    overrides = {
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=1),
      "state": models.JokeState.DAILY.value,
      "public_timestamp": now_utc + public_timestamp_offset,
      "is_public": initial_is_public,
    }
    doc = _create_mock_joke_doc("joke-1", overrides=overrides)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    _setup_decay_test_mocks(monkeypatch)

    joke_auto_fns._joke_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["is_public"] == expected_is_public

  def test_http_endpoint_uses_current_time(self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time

    monkeypatch.setattr('functions.joke_auto_fns._joke_maintenance_internal',
                        _capture)

    joke_auto_fns.auto_joke_hourly_http(Mock())

    assert 'run_time' in captured
    assert captured['run_time'].tzinfo == datetime.timezone.utc

  def test_scheduler_invokes_decay_with_scheduled_time(self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time

    monkeypatch.setattr('functions.joke_auto_fns._joke_maintenance_internal',
                        _capture)

    event = MagicMock()
    event.schedule_time = datetime.datetime(2024,
                                            1,
                                            20,
                                            0,
                                            0,
                                            tzinfo=datetime.timezone.utc)

    joke_auto_fns.auto_joke_hourly_scheduler.__wrapped__(event)

    assert 'run_time' in captured
    assert captured['run_time'] == event.schedule_time

  def test_scheduler_falls_back_to_current_time_when_scheduled_time_none(
      self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time

    monkeypatch.setattr('functions.joke_auto_fns._joke_maintenance_internal',
                        _capture)

    event = MagicMock()
    event.schedule_time = None

    joke_auto_fns.auto_joke_hourly_scheduler.__wrapped__(event)

    assert 'run_time' in captured
    assert captured['run_time'].tzinfo == datetime.timezone.utc

  def test_http_endpoint_success(self, monkeypatch):
    mock_decay = Mock()
    mock_decay.return_value = {
      "jokes_decayed": 5,
      "public_updated": 3,
      "jokes_skipped": 2,
      "categories_processed": 4,
      "categories_updated": 2,
      "categories_emptied": 1,
      "categories_failed": 0
    }
    monkeypatch.setattr('functions.joke_auto_fns._joke_maintenance_internal',
                        mock_decay)

    response = joke_auto_fns.auto_joke_hourly_http(Mock())

    mock_decay.assert_called_once()
    data = response.get_json()["data"]
    assert data["message"] == "Daily maintenance completed successfully"
    assert "stats" in data
    assert data["stats"]["jokes_decayed"] == 5

  def test_http_endpoint_failure(self, monkeypatch):

    def _raise(run_time_utc):
      raise RuntimeError("boom")

    monkeypatch.setattr('functions.joke_auto_fns._joke_maintenance_internal',
                        _raise)

    response = joke_auto_fns.auto_joke_hourly_http(Mock())

    data = response.get_json()["data"]
    assert "boom" in data["error"]

  @pytest.mark.parametrize(
    "joke_docs,expected_joke_ids,should_be_called",
    [
      # Test with two PUBLISHED jokes
      ([
        ("joke1", models.JokeState.PUBLISHED, True, None),
        ("joke2", models.JokeState.PUBLISHED, True, None),
      ], {"joke1", "joke2"}, True),
      # Test with no public jokes (DRAFT)
      ([
        ("joke1", models.JokeState.DRAFT, False, None),
      ], set(), False),
      # Test with DAILY joke with past timestamp (should be included)
      (
        [
          ("daily-joke", models.JokeState.DAILY, False, -1),  # -1 hour
        ],
        {"daily-joke"},
        True),
      # Test with DAILY joke with future timestamp (should be excluded)
      (
        [
          ("future-daily-joke", models.JokeState.DAILY, False, 1),  # +1 hour
        ],
        set(),
        False),
      # Test with mixed public jokes (PUBLISHED + DAILY with past timestamp)
      (
        [
          ("published-joke", models.JokeState.PUBLISHED, True, None),
          ("daily-joke", models.JokeState.DAILY, False, -1),  # -1 hour
          ("draft-joke", models.JokeState.DRAFT, False,
           None),  # Should be excluded
        ],
        {"published-joke", "daily-joke"},
        True),
    ])
  def test_update_joke_feed_behavior(self, monkeypatch, joke_docs,
                                     expected_joke_ids, should_be_called):
    """Test update_joke_feed behavior for various joke states."""
    now_utc = _create_test_datetime()
    docs = []
    for joke_id, state, is_public, timestamp_offset_hours in joke_docs:
      doc = MagicMock()
      doc.exists = True
      doc.id = joke_id
      doc.reference = MagicMock()
      doc_data = {
        "setup_text": f"Setup for {joke_id}",
        "punchline_text": f"Punchline for {joke_id}",
        "state": state.value,
        "is_public": is_public,
        "book_id": None,
        "num_saved_users_fraction": 0.5,
        "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      }
      if timestamp_offset_hours is not None:
        doc_data["public_timestamp"] = now_utc + datetime.timedelta(
          hours=timestamp_offset_hours)
      doc.to_dict.return_value = doc_data
      docs.append(doc)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, docs)
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    mock_update_joke_feed = Mock()
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        mock_update_joke_feed)

    joke_auto_fns._joke_maintenance_internal(now_utc)  # pylint: disable=protected-access

    if should_be_called:
      mock_update_joke_feed.assert_called_once()
      # Verify the call was made with a list of minimal joke data
      call_args = mock_update_joke_feed.call_args[0][0]
      assert isinstance(call_args, list)
      # Extract joke IDs from the minimal joke data
      actual_joke_ids = {joke_data["key"] for joke_data in call_args}
      assert actual_joke_ids == expected_joke_ids
      # Verify each joke has minimal data structure
      for joke_data in call_args:
        assert "key" in joke_data
        assert "setup_text" in joke_data
        assert "punchline_text" in joke_data
        assert "setup_image_url" in joke_data
        assert "punchline_image_url" in joke_data
    else:
      mock_update_joke_feed.assert_not_called()

  def test_update_joke_feed_sorts_by_fraction(self, monkeypatch):
    """Test that update_joke_feed receives jokes sorted by num_saved_users_fraction in descending order."""
    now_utc = _create_test_datetime()

    # Create jokes with different fractions
    doc1 = MagicMock()
    doc1.exists = True
    doc1.id = "joke1"
    doc1.reference = MagicMock()
    doc1.to_dict.return_value = {
      "setup_text": "Setup 1",
      "punchline_text": "Punchline 1",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "book_id": None,
      "num_saved_users_fraction": 0.3,  # Lowest
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
    }

    doc2 = MagicMock()
    doc2.exists = True
    doc2.id = "joke2"
    doc2.reference = MagicMock()
    doc2.to_dict.return_value = {
      "setup_text": "Setup 2",
      "punchline_text": "Punchline 2",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "book_id": None,
      "num_saved_users_fraction": 0.7,  # Highest
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
    }

    doc3 = MagicMock()
    doc3.exists = True
    doc3.id = "joke3"
    doc3.reference = MagicMock()
    doc3.to_dict.return_value = {
      "setup_text": "Setup 3",
      "punchline_text": "Punchline 3",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "book_id": None,
      "num_saved_users_fraction": 0.5,  # Middle
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc1, doc2, doc3])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    mock_update_joke_feed = Mock()
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        mock_update_joke_feed)

    joke_auto_fns._joke_maintenance_internal(now_utc)  # pylint: disable=protected-access

    # Verify update_joke_feed was called
    mock_update_joke_feed.assert_called_once()
    call_args = mock_update_joke_feed.call_args[0][0]
    assert len(call_args) == 3

    # Verify jokes are sorted by fraction in descending order
    # joke2 (0.7) should be first, joke3 (0.5) second, joke1 (0.3) third
    assert call_args[0]["key"] == "joke2"
    assert call_args[1]["key"] == "joke3"
    assert call_args[2]["key"] == "joke1"

  @pytest.mark.parametrize(
    "update_type,doc_data,expected_is_public,expected_fraction",
    [
      # Test with is_public update
      (
        "is_public_update",
        {
          "is_public": False,  # Will be updated to True
          "num_viewed_users": 100,
          "num_saved_users": 50,
          "num_shared_users": 30,
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.3,
          "popularity_score": 64.0,
          "last_recent_stats_update_time": -22,  # hours
        },
        True,
        None),
      # Test without updates
      (
        "no_updates",
        {
          "is_public": True,  # Already correct
          "num_viewed_users": 100,
          "num_saved_users": 50,
          "num_shared_users": 30,
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.3,
          "popularity_score": 64.0,
          "last_recent_stats_update_time": -4,  # hours - recent
        },
        True,
        None),
      # Test with decay
      (
        "decay",
        {
          "is_public": True,
          "num_viewed_users": 100,
          "num_saved_users": 50,
          "num_shared_users": 30,
          "num_viewed_users_recent": 100.0,
          "num_saved_users_recent": 50.0,
          "num_shared_users_recent": 30.0,
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.3,
          "popularity_score": 64.0,
          "last_recent_stats_update_time": -22,  # hours
        },
        True,
        0.5),
    ])
  def test_syncs_joke_to_search_collection(self, monkeypatch, update_type,
                                           doc_data, expected_is_public,
                                           expected_fraction):
    """Test that jokes are synced to search collection with appropriate merged data."""
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.id = "joke1"
    doc.reference = MagicMock()

    # Build doc data with setup fields
    full_doc_data = {
      "setup_text": "Test setup",
      "punchline_text": "Test punchline",
      "state": models.JokeState.PUBLISHED.value,
      "category_id": "_uncategorized",
      "book_id": None,
      "public_timestamp": now_utc - datetime.timedelta(days=1),
    }
    full_doc_data.update(doc_data)

    # Convert hours offset to timedelta
    if "last_recent_stats_update_time" in full_doc_data:
      hours_offset = full_doc_data.pop("last_recent_stats_update_time")
      full_doc_data["last_recent_stats_update_time"] = (
        now_utc + datetime.timedelta(hours=hours_offset))

    doc.to_dict.return_value = full_doc_data

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    mock_sync = Mock()
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_sync.assert_called_once()
    call_args = mock_sync.call_args
    joke = call_args.kwargs['joke']
    new_embedding = call_args.kwargs['new_embedding']

    # Verify joke data
    assert joke.key == "joke1"
    assert joke.is_public == expected_is_public
    assert new_embedding is None

    # Verify fraction if specified
    if expected_fraction is not None:
      assert joke.num_saved_users_fraction == pytest.approx(expected_fraction)

  def test_syncs_multiple_jokes_with_different_updates(self, monkeypatch):
    """Test that jokes are synced even when only some are updated."""
    now_utc = _create_test_datetime()

    # Joke 1: Has updates (decay)
    doc1 = MagicMock()
    doc1.exists = True
    doc1.id = "joke1"
    doc1.reference = MagicMock()
    doc1.to_dict.return_value = {
      "setup_text": "Test setup 1",
      "punchline_text": "Test punchline 1",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "category_id": "_uncategorized",
      "book_id": None,
      "num_viewed_users_recent": 10.0,
      "public_timestamp": now_utc - datetime.timedelta(days=1),
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=22),
    }

    # Joke 2: No updates (is_public correct, recently updated, and above view threshold)
    doc2 = MagicMock()
    doc2.exists = True
    doc2.id = "joke2"
    doc2.reference = MagicMock()
    doc2.to_dict.return_value = {
      "setup_text": "Test setup 2",
      "punchline_text": "Test punchline 2",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "category_id": "_uncategorized",
      "book_id": None,
      "public_timestamp": now_utc - datetime.timedelta(days=1),
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc1, doc2])
    mock_sync = Mock()
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)

    # Verify sync was called for both jokes
    assert mock_sync.call_count == 2
    synced_ids = {call.kwargs['joke'].key for call in mock_sync.call_args_list}
    assert synced_ids == {"joke1", "joke2"}

  def test_sync_handles_errors_gracefully(self, monkeypatch):
    """Test that sync errors don't crash the maintenance job."""
    now_utc = _create_test_datetime()

    doc = MagicMock()
    doc.exists = True
    doc.id = "joke1"
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "setup_text": "Test setup",
      "punchline_text": "Test punchline",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
      "book_id": None,
      "public_timestamp": now_utc - datetime.timedelta(days=1),
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=22),
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])

    # Mock sync to raise an exception
    mock_sync = Mock(side_effect=Exception("Sync failed"))
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    # Should not raise exception
    joke_auto_fns._joke_maintenance_internal(now_utc)

    # Verify sync was called
    mock_sync.assert_called_once()
    # Verify error was logged by checking the mocked logger
    mock_logger = joke_auto_fns.logger
    mock_logger.warn.assert_called()
    warn_call = str(mock_logger.warn.call_args)
    assert "Failed to sync joke joke1" in warn_call
    assert "Sync failed" in warn_call


class TestBookIdEnsurer:
  """Tests for syncing book_id based on joke_books."""

  def test_sets_book_id_from_books(self, monkeypatch):
    now_utc = _create_test_datetime()
    doc = _create_mock_joke_doc(
      "joke-1",
      overrides={
        "is_public": True,
        "state": models.JokeState.PUBLISHED.value,
        "category_id": "cat-1",
        "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
      },
    )
    book_doc = _create_mock_book_doc("book-1", ["joke-1"])

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc], [book_doc])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(return_value={}))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload == {"book_id": "book-1"}

  def test_clears_book_id_when_missing_from_books(self, monkeypatch):
    now_utc = _create_test_datetime()
    doc = _create_mock_joke_doc(
      "joke-1",
      overrides={
        "book_id": "book-1",
        "is_public": True,
        "state": models.JokeState.PUBLISHED.value,
        "category_id": "cat-1",
        "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
      },
    )

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc], [])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr('functions.joke_auto_fns.firestore.update_joke_feed',
                        Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(return_value={}))
    monkeypatch.setattr(
      'common.joke_category_operations.rebuild_joke_categories_index',
      Mock(return_value={}))

    joke_auto_fns._joke_maintenance_internal(now_utc)

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload == {"book_id": None}


def _create_joke(key: str,
                 fraction: float,
                 views: int | None = None) -> MagicMock:
  """Helper to create a mock PunnyJoke for feed building tests."""
  joke = MagicMock(spec=models.PunnyJoke)
  joke.key = key
  joke.num_saved_users_fraction = fraction
  joke.num_viewed_users = views if views is not None else 0
  joke.__repr__ = lambda self: f"Joke(id='{self.key}', f={self.num_saved_users_fraction})"
  return joke


class TestBuildJokeFeed:
  """Tests for the build_joke_feed function."""

  def test_returns_empty_list_for_empty_input(self):
    """Test that an empty list of jokes results in an empty feed."""
    assert joke_auto_fns.build_joke_feed([]) == []

  def test_returns_sorted_list_for_fewer_than_10_jokes(self):
    """Test with fewer than 10 jokes; should just be sorted."""
    jokes = [
      _create_joke("a", 0.1),
      _create_joke("c", 0.3),
      _create_joke("b", 0.2),
    ]
    result = joke_auto_fns.build_joke_feed(jokes)
    assert [j.key for j in result] == ["c", "b", "a"]

  def test_returns_sorted_list_for_exactly_10_jokes(self):
    """Test with exactly 10 jokes; should just be sorted."""
    jokes = [_create_joke(str(i), i / 10.0) for i in range(10)]
    random.shuffle(jokes)
    result = joke_auto_fns.build_joke_feed(jokes)
    expected_order = [str(i) for i in range(9, -1, -1)]
    assert [j.key for j in result] == expected_order

  def test_alternating_logic_for_15_jokes(self):
    """Test the alternating logic for more than 10 jokes (15 total)."""
    jokes = [_create_joke(f"j{i}", i / 10.0, views=i) for i in range(15)]

    result = joke_auto_fns.build_joke_feed(jokes)
    result_keys = [j.key for j in result]

    # 1. Check the top 10 (j14 down to j5)
    expected_top_10 = [f"j{i}" for i in range(14, 4, -1)]
    assert result_keys[:10] == expected_top_10

    # 2. Check the alternating part
    # Initial remaining sorted list: [j4, j3, j2, j1, j0]
    #
    # Iteration 1:
    # - Sorted pick: j4. Remaining: [j3, j2, j1, j0]
    # - Lowest viewed pick: j0. Remaining: [j3, j2, j1]
    #
    # Iteration 2:
    # - Sorted pick: j3. Remaining: [j2, j1]
    # - Lowest viewed pick: j1. Remaining: [j2]
    #
    # Iteration 3:
    # - Sorted pick: j2. Remaining: []
    #
    # Expected alternating part: [j4, j0, j3, j1, j2]
    alternating_part = result_keys[10:]
    assert alternating_part == ["j4", "j0", "j3", "j1", "j2"]

    # 3. Check total length and no duplicates
    assert len(result_keys) == 15
    assert len(set(result_keys)) == 15

  def test_alternating_logic_for_14_jokes(self):
    """Test the alternating logic for an even number of remaining jokes (14 total)."""
    jokes = [_create_joke(f"j{i}", i / 10.0, views=i) for i in range(14)]

    result = joke_auto_fns.build_joke_feed(jokes)
    result_keys = [j.key for j in result]

    # 1. Check the top 10 (j13 down to j4)
    expected_top_10 = [f"j{i}" for i in range(13, 3, -1)]
    assert result_keys[:10] == expected_top_10

    # 2. Check the alternating part
    # Initial remaining sorted list: [j3, j2, j1, j0]
    #
    # Iteration 1:
    # - Sorted pick: j3. Remaining: [j2, j1, j0]
    # - Lowest viewed pick: j0. Remaining: [j2, j1]
    #
    # Iteration 2:
    # - Sorted pick: j2. Remaining: [j1]
    # - Lowest viewed pick: j1. Remaining: []
    #
    # Expected alternating part: [j3, j0, j2, j1]
    alternating_part = result_keys[10:]
    assert alternating_part == ["j3", "j0", "j2", "j1"]

    # 3. Check total length and no duplicates
    assert len(result_keys) == 14
    assert len(set(result_keys)) == 14

  def test_handles_odd_number_of_remaining_jokes(self):
    """Test that the last item is handled correctly if the remaining list has an odd number of items (11 total)."""
    jokes = [_create_joke(f"j{i}", i / 10.0, views=i) for i in range(11)]

    result = joke_auto_fns.build_joke_feed(jokes)
    result_keys = [j.key for j in result]

    expected_top_10 = [f"j{i}" for i in range(10, 0, -1)]
    assert result_keys[:10] == expected_top_10

    # The last item should be the highest remaining, which is j0
    assert result_keys[10] == "j0"
    assert len(result_keys) == 11
