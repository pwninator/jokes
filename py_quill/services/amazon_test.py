"""Tests for Amazon Ads client helpers."""

from __future__ import annotations

import datetime

import pytest
from services import amazon


def test_get_profiles_queries_all_regions(monkeypatch):
  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")

  calls: list[tuple[str, str, str]] = []

  def _fake_list_profiles_for_region(*, api_base, access_token, region):
    calls.append((api_base, access_token, region))
    if region == "na":
      return [
        amazon.AmazonAdsProfile(
          profile_id="na-2",
          region="na",
          api_base=api_base,
          country_code="CA",
        ),
        amazon.AmazonAdsProfile(
          profile_id="na-1",
          region="na",
          api_base=api_base,
          country_code="US",
        ),
      ]
    if region == "eu":
      return [
        amazon.AmazonAdsProfile(
          profile_id="eu-1",
          region="eu",
          api_base=api_base,
          country_code="GB",
        ),
      ]
    return []

  monkeypatch.setattr(amazon, "_list_profiles_for_region",
                      _fake_list_profiles_for_region)

  profiles = amazon.get_profiles(region="all")

  assert len(profiles) == 3
  assert [profile.region for profile in profiles] == ["eu", "na", "na"]
  assert [profile.profile_id for profile in profiles] == ["eu-1", "na-2", "na-1"]
  assert calls[0] == ("https://advertising-api.amazon.com", "access-token", "na")
  assert calls[1] == (
    "https://advertising-api-eu.amazon.com",
    "access-token",
    "eu",
  )
  assert calls[2] == (
    "https://advertising-api-fe.amazon.com",
    "access-token",
    "fe",
  )


def test_get_profiles_invalid_region_raises_value_error(monkeypatch):
  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")

  with pytest.raises(ValueError):
    amazon.get_profiles(region="bad-region")


def test_request_daily_campaign_stats_reports_requests_two_reports(monkeypatch):
  calls: list[dict] = []

  def _fake_create_report(*, api_base, access_token, profile_id, payload):
    calls.append({
      "api_base": api_base,
      "access_token": access_token,
      "profile_id": profile_id,
      "payload": payload,
    })
    report_type = payload["configuration"]["reportTypeId"]
    if report_type == "spCampaigns":
      return "campaigns-report-id"
    if report_type == "spPurchasedProduct":
      return "products-report-id"
    raise AssertionError(f"Unexpected report type: {report_type}")

  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")
  monkeypatch.setattr(amazon, "_create_report", _fake_create_report)

  result = amazon.request_daily_campaign_stats_reports(
    profile_id="profile-1",
    start_date=datetime.date(2026, 2, 10),
    end_date=datetime.date(2026, 2, 17),
    region="na",
  )

  assert result == amazon.ReportIdPair(
    campaigns_report_id="campaigns-report-id",
    purchased_products_report_id="products-report-id",
  )
  assert len(calls) == 2
  assert calls[0]["api_base"] == "https://advertising-api.amazon.com"
  assert calls[0]["profile_id"] == "profile-1"
  assert calls[0]["access_token"] == "access-token"
  assert calls[0]["payload"]["configuration"]["reportTypeId"] == "spCampaigns"
  assert calls[1]["payload"]["configuration"][
    "reportTypeId"] == "spPurchasedProduct"


def test_get_report_statuses_returns_status_for_each_report(monkeypatch):

  def _fake_fetch_status(*, api_base, access_token, profile_id, report_id):
    return amazon.ReportStatus(
      report_id=report_id,
      status="COMPLETED",
      url=f"https://example.com/{report_id}.json.gz",
    )

  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")
  monkeypatch.setattr(amazon, "_fetch_report_status", _fake_fetch_status)

  statuses = amazon.get_report_statuses(
    profile_id="profile-1",
    report_ids=["r1", "r2"],
    region="eu",
  )

  assert [status.report_id for status in statuses] == ["r1", "r2"]
  assert all(status.status == "COMPLETED" for status in statuses)
  assert statuses[0].url == "https://example.com/r1.json.gz"


def test_get_daily_campaign_stats_from_report_ids_merges_rows(monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign A",
    "date": "2026-02-14",
    "cost": 5.0,
    "impressions": 100,
    "clicks": 10,
    "attributedKindleEditionNormalizedPagesRoyalties14d": 1.0,
  }]
  product_rows = [
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "purchasedAsin": "B09XYZ",
      "attributedSales14d": 20.0,
      "attributedUnitsOrdered14d": 2,
    },
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "purchasedAsin": "B000UNKNOWN",
      "attributedSales14d": 10.0,
      "attributedUnitsOrdered14d": 1,
    },
  ]

  statuses = {
    "campaigns-id":
    amazon.ReportStatus(
      report_id="campaigns-id",
      status="COMPLETED",
      url="https://example.com/campaigns.gz",
    ),
    "products-id":
    amazon.ReportStatus(
      report_id="products-id",
      status="COMPLETED",
      url="https://example.com/products.gz",
    ),
  }

  def _fake_wait_for_completion(
      *,
      api_base,
      access_token,
      profile_id,
      report_id,
      poll_interval_sec,
      poll_timeout_sec,
  ):
    del api_base, access_token, profile_id, poll_interval_sec, poll_timeout_sec
    return statuses[report_id]

  def _fake_download(status: amazon.ReportStatus):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "products-id":
      return product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")
  monkeypatch.setattr(amazon, "_wait_for_report_completion",
                      _fake_wait_for_completion)
  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_report_ids(
    profile_id="profile-1",
    campaigns_report_id="campaigns-id",
    purchased_products_report_id="products-id",
    region="na",
    poll_interval_sec=1,
    poll_timeout_sec=10,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.campaign_id == "123"
  assert daily.campaign_name == "Campaign A"
  assert daily.date == datetime.date(2026, 2, 14)
  assert daily.spend == 5.0
  assert daily.impressions == 100
  assert daily.clicks == 10
  assert daily.kenp_royalties == 1.0
  assert daily.total_attributed_sales == 30.0
  assert daily.total_units_sold == 3
  # 2 * 4.50 margin for B09XYZ + 0 for unknown + 1.0 KENP
  assert daily.gross_profit == 10.0
  assert [item.asin for item in daily.sale_items] == ["B000UNKNOWN", "B09XYZ"]
