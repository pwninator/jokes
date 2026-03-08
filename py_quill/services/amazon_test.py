"""Tests for Amazon Ads client helpers."""

from __future__ import annotations

import datetime
import gzip
import json

import pytest
from common import models
from services import amazon


@pytest.fixture(autouse=True)
def _stub_kdp_price_candidates(monkeypatch):
  monkeypatch.setattr(
    amazon,
    "_load_kdp_price_candidates_by_country_asin",
    lambda *, start_date, end_date: {},
  )


def _report_status(
  report_id: str,
  status: str,
  **kwargs,
) -> models.AmazonAdsReport:
  return models.AmazonAdsReport(
    report_id=report_id,
    status=status,
    report_name=kwargs.get("report_name", "Report"),
    report_type_id=kwargs.get("report_type_id", "spCampaigns"),
    report_key=kwargs.get("report_key"),
    start_date=kwargs.get("start_date", datetime.date(2026, 2, 14)),
    end_date=kwargs.get("end_date", datetime.date(2026, 2, 14)),
    created_at=kwargs.get(
      "created_at",
      datetime.datetime(2026, 2, 14, 0, 0, tzinfo=datetime.timezone.utc),
    ),
    updated_at=kwargs.get(
      "updated_at",
      datetime.datetime(2026, 2, 14, 0, 0, tzinfo=datetime.timezone.utc),
    ),
    generated_at=kwargs.get("generated_at"),
    file_size=kwargs.get("file_size"),
    url=kwargs.get("url"),
    url_expires_at=kwargs.get("url_expires_at"),
    failure_reason=kwargs.get("failure_reason"),
    profile_id=kwargs.get("profile_id"),
    profile_country=kwargs.get("profile_country"),
    region=kwargs.get("region"),
    api_base=kwargs.get("api_base"),
  )


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
  assert [profile.profile_id
          for profile in profiles] == ["eu-1", "na-2", "na-1"]
  assert calls[0] == ("https://advertising-api.amazon.com", "access-token",
                      "na")
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


def test_create_report_sets_canonical_report_name_and_profile_context(
    monkeypatch):
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  captured: dict[str, object] = {}

  def _fake_request_json(method, url, **kwargs):
    captured["method"] = method
    captured["url"] = url
    captured["headers"] = kwargs.get("headers")
    captured["json_payload"] = kwargs.get("json_payload")
    json_payload = kwargs["json_payload"]
    return {
      "reportId": "report-1",
      "name": json_payload["name"],
      "status": "PENDING",
      "startDate": "2026-02-18",
      "endDate": "2026-02-18",
      "createdAt": "2026-02-19T06:00:00Z",
      "updatedAt": "2026-02-19T06:00:00Z",
      "configuration": {
        "reportTypeId": "spCampaigns"
      },
    }

  monkeypatch.setattr(
    amazon,
    "_build_report_name",
    lambda report_key, profile_country:
    f"fixed_{report_key.value}_{profile_country}",
  )
  monkeypatch.setattr(amazon, "_request_json", _fake_request_json)

  report = amazon._create_report(
    api_base="https://advertising-api.amazon.com",
    access_token="access-token",
    profile=profile,
    report_key=models.AmazonAdsReportKey.SP_CAMPAIGNS,
    payload=amazon._build_sp_campaigns_report_payload(
      start_date=datetime.date(2026, 2, 18),
      end_date=datetime.date(2026, 2, 18),
    ),
  )

  assert isinstance(captured["json_payload"], dict)
  assert captured["json_payload"]["name"] == "fixed_spCampaigns_US"
  assert captured["method"] == "POST"
  assert captured[
    "url"] == "https://advertising-api.amazon.com/reporting/reports"
  assert report.report_name == "fixed_spCampaigns_US"
  assert report.profile_id == "profile-1"
  assert report.profile_country == "US"
  assert report.region == "na"
  assert report.api_base == "https://advertising-api.amazon.com"
  assert report.report_key == models.AmazonAdsReportKey.SP_CAMPAIGNS


def test_build_report_name_uses_los_angeles_local_time(monkeypatch):
  """Report names should use Los Angeles local time instead of UTC."""

  class _FixedDateTime(datetime.datetime):

    @classmethod
    def now(cls, tz=None):
      utc_now = cls(2026, 2, 27, 7, 30, 12, tzinfo=datetime.timezone.utc)
      if tz is None:
        return utc_now.replace(tzinfo=None)
      return utc_now.astimezone(tz)

  monkeypatch.setattr(amazon.datetime, "datetime", _FixedDateTime)

  report_name = amazon._build_report_name(
    report_key=models.AmazonAdsReportKey.SP_CAMPAIGNS,
    profile_country="us",
  )

  assert report_name == "20260226_233012_spCampaigns_US"


def test_request_daily_campaign_stats_reports_requests_four_reports(
    monkeypatch):
  calls: list[dict] = []
  upserted_report_ids: list[str] = []
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )

  def _fake_create_report(*, api_base, access_token, profile, report_key, payload):
    calls.append({
      "api_base": api_base,
      "access_token": access_token,
      "profile_id": profile.profile_id,
      "profile_country": profile.country_code,
      "report_key": report_key,
      "payload": payload,
    })
    if report_key == models.AmazonAdsReportKey.SP_CAMPAIGNS:
      return _report_status(
        report_id="campaigns-report-id",
        status="PENDING",
        report_type_id="spCampaigns",
        report_key=report_key,
        report_name="20260210_010203_spCampaigns_US",
      )
    if report_key == models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT:
      return _report_status(
        report_id="advertised-report-id",
        status="PENDING",
        report_type_id="spAdvertisedProduct",
        report_key=report_key,
        report_name="20260210_010203_spAdvertisedProduct_US",
      )
    if report_key == models.AmazonAdsReportKey.SP_SEARCH_TERM:
      return _report_status(
        report_id="search-term-report-id",
        status="PENDING",
        report_type_id="spSearchTerm",
        report_key=report_key,
        report_name="20260210_010203_spSearchTerm_US",
      )
    if report_key == models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT:
      return _report_status(
        report_id="placement-report-id",
        status="PENDING",
        report_type_id="spCampaigns",
        report_key=report_key,
        report_name="20260210_010203_spCampaignsPlacement_US",
      )
    raise AssertionError(f"Unexpected report key: {report_key}")

  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")
  monkeypatch.setattr(amazon, "_create_report", _fake_create_report)
  monkeypatch.setattr(
    amazon.firestore,
    "upsert_amazon_ads_report",
    lambda report: _upsert_report(report, upserted_report_ids),
  )

  result = amazon.request_daily_campaign_stats_reports(
    profile=profile,
    start_date=datetime.date(2026, 2, 10),
    end_date=datetime.date(2026, 2, 17),
  )

  assert result.campaigns_report.report_id == "campaigns-report-id"
  assert result.campaigns_report.key == "campaigns-report-id-key"
  assert result.campaigns_report.report_type_id == "spCampaigns"
  assert result.advertised_products_report.report_id == "advertised-report-id"
  assert result.advertised_products_report.key == "advertised-report-id-key"
  assert (
    result.advertised_products_report.report_type_id == "spAdvertisedProduct")
  assert result.search_term_report is not None
  assert result.search_term_report.report_id == "search-term-report-id"
  assert result.search_term_report.key == "search-term-report-id-key"
  assert result.search_term_report.report_type_id == "spSearchTerm"
  assert result.placement_report is not None
  assert result.placement_report.report_id == "placement-report-id"
  assert result.placement_report.key == "placement-report-id-key"
  assert result.placement_report.report_type_id == "spCampaigns"
  assert len(calls) == 4
  assert upserted_report_ids == [
    "campaigns-report-id",
    "advertised-report-id",
    "search-term-report-id",
    "placement-report-id",
  ]
  assert calls[0]["api_base"] == "https://advertising-api.amazon.com"
  assert calls[0]["profile_id"] == "profile-1"
  assert calls[0]["profile_country"] == "US"
  assert calls[0]["access_token"] == "access-token"
  assert calls[0]["payload"]["configuration"]["reportTypeId"] == "spCampaigns"
  assert calls[1]["payload"]["configuration"][
    "reportTypeId"] == "spAdvertisedProduct"
  assert calls[2]["payload"]["configuration"]["reportTypeId"] == "spSearchTerm"
  assert calls[3]["report_key"] == models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT
  assert calls[3]["payload"]["configuration"]["reportTypeId"] == "spCampaigns"
  assert calls[3]["payload"]["configuration"]["groupBy"] == ["campaignPlacement"]


def test_get_reports_returns_report_for_each_report_id(monkeypatch):
  upserted_report_ids: list[str] = []

  def _fake_fetch_status(*,
                         api_base,
                         access_token,
                         profile_id,
                         report_id,
                         report_key=None):
    del report_key
    return _report_status(
      report_id=report_id,
      status="COMPLETED",
      url=f"https://example.com/{report_id}.json.gz",
    )

  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")
  monkeypatch.setattr(amazon, "_fetch_report", _fake_fetch_status)
  monkeypatch.setattr(
    amazon.firestore,
    "upsert_amazon_ads_report",
    lambda report: _upsert_report(report, upserted_report_ids),
  )

  statuses = amazon.get_reports(
    profile_id="profile-1",
    report_ids=["r1", "r2"],
    region="eu",
  )

  assert [status.report_id for status in statuses] == ["r1", "r2"]
  assert all(status.status == "COMPLETED" for status in statuses)
  assert upserted_report_ids == ["r1", "r2"]
  assert statuses[0].key == "r1-key"
  assert statuses[0].url == "https://example.com/r1.json.gz"


def test_build_sp_search_term_report_payload_includes_keyword_type_filter():
  payload = amazon._build_sp_search_term_report_payload(
    start_date=datetime.date(2026, 2, 10),
    end_date=datetime.date(2026, 2, 17),
  )
  config = payload["configuration"]

  assert config["reportTypeId"] == "spSearchTerm"
  assert config["groupBy"] == ["searchTerm"]
  assert "keywordType" in [f["field"] for f in config["filters"]]


def test_build_sp_campaign_placement_report_payload_uses_campaign_placement():
  payload = amazon._build_sp_campaign_placement_report_payload(
    start_date=datetime.date(2026, 2, 10),
    end_date=datetime.date(2026, 2, 17),
  )
  config = payload["configuration"]

  assert config["reportTypeId"] == "spCampaigns"
  assert config["groupBy"] == ["campaignPlacement"]
  assert "placementClassification" in config["columns"]
  assert "topOfSearchImpressionShare" in config["columns"]


def test_get_reports_with_empty_ids_returns_empty(monkeypatch):
  monkeypatch.setattr(amazon, "_get_access_token", lambda: "access-token")

  statuses = amazon.get_reports(
    profile_id="profile-1",
    report_ids=[],
    region="na",
  )

  assert statuses == []


def test_download_report_rows_sets_raw_report_text(monkeypatch):
  report = _report_status(
    report_id="report-1",
    status="COMPLETED",
    report_name="report-name",
    url="https://example.com/report-1.json.gz",
  )
  raw_text = json.dumps([{
    "campaignId": "123",
    "date": "2026-02-14",
  }])
  compressed_bytes = gzip.compress(raw_text.encode("utf-8"))

  class _DummyResponse:

    def __init__(self, content: bytes):
      self.content = content

    def raise_for_status(self):
      return None

  monkeypatch.setattr(
    amazon.requests,
    "get",
    lambda url, timeout: _DummyResponse(compressed_bytes),
  )

  rows = amazon._download_report_rows(report)

  assert rows == [{
    "campaignId": "123",
    "date": "2026-02-14",
  }]
  assert report.raw_report_text == raw_text


def _upsert_report(report: models.AmazonAdsReport,
                   upserted_report_ids: list[str]) -> models.AmazonAdsReport:
  upserted_report_ids.append(report.report_id)
  report.key = f"{report.report_id}-key"
  return report


def test_get_search_term_daily_stats_from_report_parses_and_converts(monkeypatch):
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="CA",
  )
  report = _report_status(
    report_id="search-report-id",
    status="COMPLETED",
    report_name="search-report-name",
    report_type_id="spSearchTerm",
    url="https://example.com/search.gz",
    profile_id="profile-1",
  )
  monkeypatch.setattr(
    amazon,
    "_download_report_rows",
    lambda _report: [{
      "date": "2026-02-20",
      "campaignId": "c1",
      "campaignName": "Campaign 1",
      "adGroupId": "ag1",
      "adGroupName": "Ad Group 1",
      "searchTerm": "dad jokes",
      "keywordId": "k1",
      "keyword": "dad joke",
      "keywordType": "EXACT",
      "matchType": "EXACT",
      "impressions": 100,
      "clicks": 10,
      "cost": 20.0,
      "sales14d": 50.0,
      "purchases14d": 3,
      "unitsSoldClicks14d": 3,
      "kindleEditionNormalizedPagesRead14d": 12,
      "kindleEditionNormalizedPagesRoyalties14d": 5.0,
      "campaignBudgetCurrencyCode": "CAD",
    }],
  )

  rows = amazon.get_search_term_daily_stats_from_report(
    profile=profile,
    search_term_report=report,
  )

  assert len(rows) == 1
  assert rows[0].date == datetime.date(2026, 2, 20)
  assert rows[0].search_term == "dad jokes"
  assert rows[0].clicks == 10
  assert rows[0].cost_usd == pytest.approx(14.64, rel=1e-6)
  assert rows[0].sales14d_usd == pytest.approx(36.6, rel=1e-6)
  assert rows[0].kenp_royalties14d_usd == pytest.approx(3.66, rel=1e-6)
  assert rows[0].source_report_id == "search-report-id"
  assert rows[0].key


def test_get_placement_daily_stats_from_report_parses_and_converts(monkeypatch):
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="CA",
  )
  report = _report_status(
    report_id="placement-report-id",
    status="COMPLETED",
    report_name="20260220_010203_spCampaignsPlacement_CA",
    report_type_id="spCampaigns",
    url="https://example.com/placement.gz",
    profile_id="profile-1",
  )
  monkeypatch.setattr(
    amazon,
    "_download_report_rows",
    lambda _report: [{
      "date": "2026-02-20",
      "campaignId": "c1",
      "campaignName": "Campaign 1",
      "placementClassification": "PLACEMENT_TOP",
      "impressions": 100,
      "clicks": 10,
      "cost": 20.0,
      "sales14d": 50.0,
      "purchases14d": 3,
      "unitsSoldClicks14d": 3,
      "kindleEditionNormalizedPagesRead14d": 12,
      "kindleEditionNormalizedPagesRoyalties14d": 5.0,
      "campaignBudgetCurrencyCode": "CAD",
      "topOfSearchImpressionShare": 0.42,
    }],
  )

  rows = amazon.get_placement_daily_stats_from_report(
    profile=profile,
    placement_report=report,
  )

  assert len(rows) == 1
  assert rows[0].date == datetime.date(2026, 2, 20)
  assert rows[0].campaign_id == "c1"
  assert rows[0].placement_classification == "PLACEMENT_TOP"
  assert rows[0].clicks == 10
  assert rows[0].cost_usd == pytest.approx(14.64, rel=1e-6)
  assert rows[0].sales14d_usd == pytest.approx(36.6, rel=1e-6)
  assert rows[0].kenp_royalties14d_usd == pytest.approx(3.66, rel=1e-6)
  assert rows[0].top_of_search_impression_share == pytest.approx(0.42, rel=1e-6)
  assert rows[0].source_report_id == "placement-report-id"
  assert rows[0].key


def test_get_daily_campaign_stats_from_reports_merges_rows(monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign A",
    "date": "2026-02-14",
    "cost": 5.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 14.98,
    "unitsSoldClicks14d": 2,
    "kindleEditionNormalizedPagesRoyalties14d": 1.0,
  }]
  advertised_product_rows = [
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "advertisedAsin": "B0G9765J19",
      "attributedSalesSameSku14d": 2.99,
      "unitsSoldSameSku14d": 1,
    },
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "advertisedAsin": "B0GNHFKQ8W",
      "attributedSalesSameSku14d": 11.99,
      "unitsSoldSameSku14d": 1,
    },
  ]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)
  monkeypatch.setattr(
    amazon,
    "_load_kdp_price_candidates_by_country_asin",
    lambda *, start_date, end_date: {
      ("US", "B0G9765J19"): (2.99, ),
      ("US", "B0GNHFKQ8W"): (11.99, ),
    },
  )

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.campaign_id == "123"
  assert daily.campaign_name == "Campaign A"
  assert daily.date == datetime.date(2026, 2, 14)
  assert daily.spend == 5.0
  assert daily.impressions == 100
  assert daily.clicks == 10
  assert daily.kenp_pages_read == 0
  assert daily.kenp_royalties_usd == 1.0
  assert daily.total_attributed_sales_usd == 14.98
  assert daily.total_units_sold == 2
  assert daily.gross_profit_before_ads_usd == pytest.approx(6.3305, rel=1e-6)
  assert daily.gross_profit_usd == pytest.approx(1.3305, rel=1e-6)
  by_asin = {item.asin: item for item in daily.sale_items}
  assert set(by_asin.keys()) == {"B0G9765J19", "B0GNHFKQ8W"}
  assert by_asin["B0G9765J19"].units_sold == 1
  assert by_asin["B0G9765J19"].total_sales_usd == pytest.approx(2.99, rel=1e-6)
  assert by_asin["B0GNHFKQ8W"].units_sold == 1
  assert by_asin["B0GNHFKQ8W"].total_sales_usd == pytest.approx(11.99,
                                                                rel=1e-6)


def test_get_daily_campaign_stats_from_reports_converts_cad_to_usd(
    monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign CAD",
    "campaignBudgetCurrencyCode": "CAD",
    "date": "2026-02-14",
    "cost": 10.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 20.0,
    "unitsSoldClicks14d": 1,
    "kindleEditionNormalizedPagesRoyalties14d": 1.0,
  }]
  advertised_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "advertisedAsin": "B0G9765J19",
    "attributedSalesSameSku14d": 10.0,
    "unitsSoldSameSku14d": 1,
  }]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="CA",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.spend == pytest.approx(7.32, rel=1e-6)
  assert daily.total_attributed_sales_usd == pytest.approx(14.64, rel=1e-6)
  assert daily.kenp_pages_read == 0
  assert daily.kenp_royalties_usd == pytest.approx(0.732, rel=1e-6)
  assert daily.gross_profit_before_ads_usd == pytest.approx(2.214, rel=1e-6)
  assert daily.gross_profit_usd == pytest.approx(-5.106, rel=1e-6)
  assert daily.sale_items[0].asin == "B0GNHFKQ8W"
  assert daily.sale_items[0].total_sales_usd == pytest.approx(7.32, rel=1e-6)


def test_get_daily_campaign_stats_from_reports_decomposes_asin_using_kdp_prices(
    monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign A",
    "date": "2026-02-14",
    "cost": 0.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 14.98,
    "unitsSoldClicks14d": 2,
    "kindleEditionNormalizedPagesRoyalties14d": 0.0,
  }]
  advertised_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "advertisedAsin": "B0G9765J19",
    "attributedSalesSameSku14d": 14.98,
    "unitsSoldSameSku14d": 2,
  }]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)
  monkeypatch.setattr(
    amazon,
    "_load_kdp_price_candidates_by_country_asin",
    lambda *, start_date, end_date: {
      ("US", "B0G9765J19"): (2.99, ),
      ("US", "B0GNHFKQ8W"): (11.99, ),
    },
  )

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  by_asin = {item.asin: item for item in daily.sale_items}
  assert by_asin["B0G9765J19"].units_sold == 1
  assert by_asin["B0G9765J19"].total_sales_usd == pytest.approx(2.99, rel=1e-6)
  assert by_asin["B0GNHFKQ8W"].units_sold == 1
  assert by_asin["B0GNHFKQ8W"].total_sales_usd == pytest.approx(11.99,
                                                                rel=1e-6)


def test_get_daily_campaign_stats_from_reports_remaps_paperback_ads_kenp_to_ebook_asin(
    monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign A",
    "date": "2026-02-14",
    "cost": 5.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 10.0,
    "unitsSoldClicks14d": 1,
    "kindleEditionNormalizedPagesRead14d": 12,
    "kindleEditionNormalizedPagesRoyalties14d": 1.5,
  }]
  advertised_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "advertisedAsin": "B0GNHFKQ8W",
    "attributedSalesSameSku14d": 0.0,
    "unitsSoldSameSku14d": 0,
    "kindleEditionNormalizedPagesRead14d": 12,
    "kindleEditionNormalizedPagesRoyalties14d": 1.5,
  }]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.kenp_pages_read == 12
  by_asin = {item.asin: item for item in daily.sale_items}
  assert by_asin["B0G9765J19"].kenp_pages_read == 12
  assert by_asin["B0G9765J19"].kenp_royalties_usd == pytest.approx(1.5,
                                                                   rel=1e-6)
  assert by_asin["B0GNHFKQ8W"].kenp_pages_read == 0


def test_get_daily_campaign_stats_from_reports_uses_profile_currency_fallback(
    monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign GBP",
    "date": "2026-02-14",
    "cost": 2.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 4.0,
    "unitsSoldClicks14d": 1,
    "kindleEditionNormalizedPagesRoyalties14d": 0.0,
  }]
  advertised_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "advertisedAsin": "B0G9765J19",
    "attributedSalesSameSku14d": 2.0,
    "unitsSoldSameSku14d": 1,
  }]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="eu",
    api_base="https://advertising-api-eu.amazon.com",
    country_code="GB",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.spend == pytest.approx(2.7138, rel=1e-6)
  assert daily.total_attributed_sales_usd == pytest.approx(5.4276, rel=1e-6)
  assert daily.kenp_pages_read == 0
  assert daily.gross_profit_before_ads_usd == pytest.approx(0.94983, rel=1e-6)
  assert daily.gross_profit_usd == pytest.approx(-1.76397, rel=1e-6)
  assert daily.sale_items[0].total_sales_usd == pytest.approx(2.7138, rel=1e-6)


def test_get_daily_campaign_stats_from_reports_ignores_total_advertised_fallback_fields(
    monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign A",
    "date": "2026-02-14",
    "cost": 0.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 11.99,
    "unitsSoldClicks14d": 1,
    "kindleEditionNormalizedPagesRoyalties14d": 0.0,
  }]
  advertised_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "advertisedAsin": "B0G9765J19",
    # Missing same-SKU direct metrics; totals must not be used as fallback.
    "attributedSalesSameSku14d": 0.0,
    "unitsSoldSameSku14d": 0,
    "sales14d": 11.99,
    "unitsSoldClicks14d": 1,
  }]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.total_attributed_sales_usd == 11.99
  assert daily.total_units_sold == 1
  assert daily.gross_profit_before_ads_usd == 0.0
  assert daily.gross_profit_usd == 0.0
  assert len(daily.sale_items) == 1
  assert daily.sale_items[0].asin == "B0G9765J19"
  assert daily.sale_items[0].units_sold == 0
  assert daily.sale_items[0].total_sales_usd == 0.0
  assert daily.sale_items[0].total_profit_usd == 0.0


def test_sp_advertised_product_columns_include_kenp_fields():
  assert "kindleEditionNormalizedPagesRead14d" in (
    amazon._SP_ADVERTISED_PRODUCT_COLUMNS)
  assert "kindleEditionNormalizedPagesRoyalties14d" in (
    amazon._SP_ADVERTISED_PRODUCT_COLUMNS)


def test_get_daily_campaign_stats_from_reports_raises_on_unknown_asin(
    monkeypatch):
  campaign_rows = [{
    "campaignId": "123",
    "campaignName": "Campaign A",
    "date": "2026-02-14",
    "cost": 5.0,
    "impressions": 100,
    "clicks": 10,
    "sales14d": 99.0,
    "unitsSoldClicks14d": 9,
    "kindleEditionNormalizedPagesRoyalties14d": 1.0,
  }]
  advertised_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "advertisedAsin": "B000UNKNOWN",
    "attributedSalesSameSku14d": 10.0,
    "unitsSoldSameSku14d": 1,
  }]

  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  with pytest.raises(amazon.AmazonAdsError, match="Unknown ASIN"):
    amazon.get_daily_campaign_stats_from_reports(
      profile=profile,
      campaigns_report=campaigns_report,
      advertised_products_report=advertised_products_report,
    )


def test_get_daily_campaign_stats_from_reports_raises_when_not_completed():
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="IN_PROGRESS",
    url=None,
    profile_id="profile-1",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  with pytest.raises(amazon.AmazonAdsError, match="is not completed yet"):
    amazon.get_daily_campaign_stats_from_reports(
      profile=profile,
      campaigns_report=campaigns_report,
      advertised_products_report=advertised_products_report,
    )


def test_get_daily_campaign_stats_from_reports_raises_on_profile_mismatch():
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  campaigns_report = _report_status(
    report_id="campaigns-id",
    status="COMPLETED",
    url="https://example.com/campaigns.gz",
    profile_id="different-profile",
  )
  advertised_products_report = _report_status(
    report_id="advertised-id",
    status="COMPLETED",
    url="https://example.com/advertised.gz",
    profile_id="profile-1",
  )

  with pytest.raises(ValueError, match="belongs to profile"):
    amazon.get_daily_campaign_stats_from_reports(
      profile=profile,
      campaigns_report=campaigns_report,
      advertised_products_report=advertised_products_report,
    )


def test_fetch_ads_stats_reports_triggers_sales_reconciliation(monkeypatch):
  run_time_utc = datetime.datetime(2026, 2, 26, tzinfo=datetime.timezone.utc)
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  monkeypatch.setattr(amazon.time, "sleep", lambda _seconds: None)
  monkeypatch.setattr(
    amazon,
    "get_ads_stats_context",
    lambda _run_time: amazon.AdsStatsContext(
      selected_profiles=[profile],
      reports_by_expected_key={},
      report_start_date=datetime.date(2026, 1, 1),
      report_end_date=datetime.date(2026, 1, 31),
      profiles_considered=1,
    ),
  )
  monkeypatch.setattr(
    amazon,
    "_collect_expected_reports_for_profile",
    lambda *, profile_id, reports_by_expected_key: {
      models.AmazonAdsReportKey.SP_CAMPAIGNS: _report_status(
        report_id="r1",
        status="PENDING",
        report_name="20260226_010100_spCampaigns_US",
        report_type_id="spCampaigns",
        report_key=models.AmazonAdsReportKey.SP_CAMPAIGNS,
        profile_id=profile_id,
      ),
      models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT: _report_status(
        report_id="r2",
        status="PENDING",
        report_name="20260226_010100_spAdvertisedProduct_US",
        report_type_id="spAdvertisedProduct",
        report_key=models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT,
        profile_id=profile_id,
      ),
      models.AmazonAdsReportKey.SP_SEARCH_TERM: _report_status(
        report_id="r3",
        status="PENDING",
        report_name="20260226_010100_spSearchTerm_US",
        report_type_id="spSearchTerm",
        report_key=models.AmazonAdsReportKey.SP_SEARCH_TERM,
        profile_id=profile_id,
      ),
      models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT: _report_status(
        report_id="r4",
        status="PENDING",
        report_name="20260226_010100_spCampaignsPlacement_US",
        report_type_id="spCampaigns",
        report_key=models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT,
        profile_id=profile_id,
      ),
    },
  )
  monkeypatch.setattr(
    amazon,
    "get_reports",
    lambda *, profile_id, report_ids, region, report_keys_by_id=None: [
      _report_status(
        report_id="r1",
        status="COMPLETED",
        report_name="20260226_010100_spCampaigns_US",
        report_type_id="spCampaigns",
        report_key=models.AmazonAdsReportKey.SP_CAMPAIGNS,
        profile_id=profile_id,
      ),
      _report_status(
        report_id="r2",
        status="COMPLETED",
        report_name="20260226_010100_spAdvertisedProduct_US",
        report_type_id="spAdvertisedProduct",
        report_key=models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT,
        profile_id=profile_id,
      ),
      _report_status(
        report_id="r3",
        status="COMPLETED",
        report_name="20260226_010100_spSearchTerm_US",
        report_type_id="spSearchTerm",
        report_key=models.AmazonAdsReportKey.SP_SEARCH_TERM,
        profile_id=profile_id,
      ),
      _report_status(
        report_id="r4",
        status="COMPLETED",
        report_name="20260226_010100_spCampaignsPlacement_US",
        report_type_id="spCampaigns",
        report_key=models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT,
        profile_id=profile_id,
      ),
    ],
  )
  monkeypatch.setattr(
    amazon,
    "_are_reports_complete",
    lambda campaigns_report, advertised_products_report, search_term_report, placement_report: True,
  )
  monkeypatch.setattr(
    amazon,
    "get_daily_campaign_stats_from_reports",
    lambda **kwargs: [
      models.AmazonAdsDailyCampaignStats(
        campaign_id="campaign-1",
        campaign_name="Campaign 1",
        date=datetime.date(2026, 2, 20),
        total_units_sold=1,
        sale_items_by_asin_country={
          "B0G9765J19": {
            "US":
            models.AmazonProductStats(
              asin="B0G9765J19",
              units_sold=1,
              total_sales_usd=10.0,
              total_profit_usd=4.0,
            )
          }
        },
      )
    ],
  )
  monkeypatch.setattr(
    amazon,
    "get_search_term_daily_stats_from_report",
    lambda **kwargs: [],
  )
  monkeypatch.setattr(
    amazon,
    "get_placement_daily_stats_from_report",
    lambda **kwargs: [],
  )
  monkeypatch.setattr(
    amazon.firestore,
    "upsert_amazon_ads_daily_stats",
    lambda stats: stats,
  )
  monkeypatch.setattr(
    amazon.amazon_ads_firestore,
    "upsert_amazon_ads_search_term_daily_stats",
    lambda stats: stats,
  )
  monkeypatch.setattr(
    amazon.amazon_ads_firestore,
    "upsert_amazon_ads_placement_daily_stats",
    lambda stats: stats,
  )
  monkeypatch.setattr(
    amazon.firestore,
    "upsert_amazon_ads_report",
    lambda report: report,
  )

  captured_reconciliation: list[dict[str, object]] = []

  def _capture_reconciliation(*, earliest_changed_date, run_time_utc):
    captured_reconciliation.append({
      "earliest_changed_date": earliest_changed_date,
      "run_time_utc": run_time_utc,
    })

  monkeypatch.setattr(
    amazon.amazon_sales_reconciliation,
    "reconcile_daily_sales",
    _capture_reconciliation,
  )

  _ = amazon.fetch_ads_stats_reports(run_time_utc)

  assert len(captured_reconciliation) == 1
  assert captured_reconciliation[0]["earliest_changed_date"] == datetime.date(
    2026,
    2,
    20,
  )
  assert captured_reconciliation[0]["run_time_utc"] == run_time_utc


def test_get_latest_ads_reports_by_profile_type_picks_latest_window_and_rows():
  reports = [
    _report_status(
      report_id="old-campaigns",
      report_name="old-campaigns",
      status="COMPLETED",
      report_type_id="spCampaigns",
      start_date=datetime.date(2026, 1, 28),
      end_date=datetime.date(2026, 2, 27),
      created_at=datetime.datetime(2026,
                                   2,
                                   27,
                                   20,
                                   1,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   2,
                                   27,
                                   20,
                                   2,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="older-window-campaigns",
      report_name="older-window-campaigns",
      status="COMPLETED",
      report_type_id="spCampaigns",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   30,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   31,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="older-window-advertised",
      report_name="older-window-advertised",
      status="COMPLETED",
      report_type_id="spAdvertisedProduct",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   30,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   31,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="older-window-search",
      report_name="20260301_053000_spSearchTerm_US",
      status="COMPLETED",
      report_type_id="spSearchTerm",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   30,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   31,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="older-window-placement",
      report_name="20260301_053000_spCampaignsPlacement_US",
      status="COMPLETED",
      report_type_id="spCampaigns",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   30,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   5,
                                   31,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="latest-window-campaigns",
      report_name="20260301_070100_spCampaigns_US",
      status="PENDING",
      report_type_id="spCampaigns",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   1,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   2,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="latest-window-advertised",
      report_name="20260301_070100_spAdvertisedProduct_US",
      status="PENDING",
      report_type_id="spAdvertisedProduct",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   1,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   2,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="latest-window-search",
      report_name="20260301_070100_spSearchTerm_US",
      status="PENDING",
      report_type_id="spSearchTerm",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   1,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   2,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
    _report_status(
      report_id="latest-window-placement",
      report_name="20260301_070100_spCampaignsPlacement_US",
      status="PENDING",
      report_type_id="spCampaigns",
      start_date=datetime.date(2026, 1, 29),
      end_date=datetime.date(2026, 2, 28),
      created_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   1,
                                   tzinfo=datetime.timezone.utc),
      updated_at=datetime.datetime(2026,
                                   3,
                                   1,
                                   7,
                                   2,
                                   tzinfo=datetime.timezone.utc),
      profile_id="profile-1",
    ),
  ]

  selected = amazon.get_latest_ads_reports_by_profile_type(reports=reports)

  assert set(selected.keys()) == {
    ("profile-1", models.AmazonAdsReportKey.SP_CAMPAIGNS),
    ("profile-1", models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT),
    ("profile-1", models.AmazonAdsReportKey.SP_SEARCH_TERM),
    ("profile-1", models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT),
  }
  assert selected[("profile-1",
                   models.AmazonAdsReportKey.SP_CAMPAIGNS)].report_id == ("latest-window-campaigns")
  assert selected[("profile-1", models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT)].report_id == (
    "latest-window-advertised")
  assert selected[("profile-1", models.AmazonAdsReportKey.SP_SEARCH_TERM)].report_id == (
    "latest-window-search")
  assert selected[("profile-1", models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT)].report_id == (
    "latest-window-placement")


def test_get_ads_stats_context_uses_latest_available_reports(monkeypatch):
  run_time_utc = datetime.datetime(2026,
                                   3,
                                   1,
                                   8,
                                   30,
                                   tzinfo=datetime.timezone.utc)
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )
  monkeypatch.setattr(amazon,
                      "get_profiles",
                      lambda *, region="all": [profile])
  monkeypatch.setattr(
    amazon.firestore,
    "list_amazon_ads_reports",
    lambda *, created_on_or_after: [
      _report_status(
        report_id="campaigns-id",
        report_name="20260301_040100_spCampaigns_US",
        status="PENDING",
        report_type_id="spCampaigns",
        start_date=datetime.date(2026, 1, 29),
        end_date=datetime.date(2026, 2, 28),
        created_at=datetime.datetime(
          2026, 3, 1, 4, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(
          2026, 3, 1, 4, 2, tzinfo=datetime.timezone.utc),
        profile_id="profile-1",
      ),
      _report_status(
        report_id="advertised-id",
        report_name="20260301_040100_spAdvertisedProduct_US",
        status="PENDING",
        report_type_id="spAdvertisedProduct",
        start_date=datetime.date(2026, 1, 29),
        end_date=datetime.date(2026, 2, 28),
        created_at=datetime.datetime(
          2026, 3, 1, 4, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(
          2026, 3, 1, 4, 2, tzinfo=datetime.timezone.utc),
        profile_id="profile-1",
      ),
      _report_status(
        report_id="search-id",
        report_name="20260301_040100_spSearchTerm_US",
        status="PENDING",
        report_type_id="spSearchTerm",
        start_date=datetime.date(2026, 1, 29),
        end_date=datetime.date(2026, 2, 28),
        created_at=datetime.datetime(
          2026, 3, 1, 4, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(
          2026, 3, 1, 4, 2, tzinfo=datetime.timezone.utc),
        profile_id="profile-1",
      ),
      _report_status(
        report_id="placement-id",
        report_name="20260301_040100_spCampaignsPlacement_US",
        status="PENDING",
        report_type_id="spCampaigns",
        start_date=datetime.date(2026, 1, 29),
        end_date=datetime.date(2026, 2, 28),
        created_at=datetime.datetime(
          2026, 3, 1, 4, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(
          2026, 3, 1, 4, 2, tzinfo=datetime.timezone.utc),
        profile_id="profile-1",
      ),
    ],
  )

  context = amazon.get_ads_stats_context(run_time_utc)

  assert context.report_end_date == datetime.date(2026, 3, 1)
  assert context.report_start_date == datetime.date(2026, 1, 30)
  assert context.reports_by_expected_key[(
    "profile-1",
    models.AmazonAdsReportKey.SP_CAMPAIGNS,
  )].report_id == "campaigns-id"
  assert context.reports_by_expected_key[(
    "profile-1",
    models.AmazonAdsReportKey.SP_ADVERTISED_PRODUCT,
  )].report_id == "advertised-id"
  assert context.reports_by_expected_key[(
    "profile-1",
    models.AmazonAdsReportKey.SP_SEARCH_TERM,
  )].report_id == "search-id"
  assert context.reports_by_expected_key[(
    "profile-1",
    models.AmazonAdsReportKey.SP_CAMPAIGNS_PLACEMENT,
  )].report_id == "placement-id"
