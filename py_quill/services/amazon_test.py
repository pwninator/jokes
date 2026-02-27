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
    "_load_kdp_price_candidates_by_market_currency_asin",
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
    lambda report_type_id, profile_country:
    f"fixed_{report_type_id}_{profile_country}",
  )
  monkeypatch.setattr(amazon, "_request_json", _fake_request_json)

  report = amazon._create_report(
    api_base="https://advertising-api.amazon.com",
    access_token="access-token",
    profile=profile,
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


def test_request_daily_campaign_stats_reports_requests_three_reports(
    monkeypatch):
  calls: list[dict] = []
  upserted_report_ids: list[str] = []
  profile = amazon.AmazonAdsProfile(
    profile_id="profile-1",
    region="na",
    api_base="https://advertising-api.amazon.com",
    country_code="US",
  )

  def _fake_create_report(*, api_base, access_token, profile, payload):
    calls.append({
      "api_base": api_base,
      "access_token": access_token,
      "profile_id": profile.profile_id,
      "profile_country": profile.country_code,
      "payload": payload,
    })
    report_type = payload["configuration"]["reportTypeId"]
    if report_type == "spCampaigns":
      return _report_status(
        report_id="campaigns-report-id",
        status="PENDING",
        report_type_id="spCampaigns",
      )
    if report_type == "spAdvertisedProduct":
      return _report_status(
        report_id="advertised-report-id",
        status="PENDING",
        report_type_id="spAdvertisedProduct",
      )
    if report_type == "spPurchasedProduct":
      return _report_status(
        report_id="products-report-id",
        status="PENDING",
        report_type_id="spPurchasedProduct",
      )
    raise AssertionError(f"Unexpected report type: {report_type}")

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
  assert result.purchased_products_report.report_id == "products-report-id"
  assert result.purchased_products_report.key == "products-report-id-key"
  assert result.purchased_products_report.report_type_id == "spPurchasedProduct"
  assert len(calls) == 3
  assert upserted_report_ids == [
    "campaigns-report-id",
    "advertised-report-id",
    "products-report-id",
  ]
  assert calls[0]["api_base"] == "https://advertising-api.amazon.com"
  assert calls[0]["profile_id"] == "profile-1"
  assert calls[0]["profile_country"] == "US"
  assert calls[0]["access_token"] == "access-token"
  assert calls[0]["payload"]["configuration"]["reportTypeId"] == "spCampaigns"
  assert calls[1]["payload"]["configuration"][
    "reportTypeId"] == "spAdvertisedProduct"
  assert calls[2]["payload"]["configuration"][
    "reportTypeId"] == "spPurchasedProduct"


def test_get_reports_returns_report_for_each_report_id(monkeypatch):
  upserted_report_ids: list[str] = []

  def _fake_fetch_status(*, api_base, access_token, profile_id, report_id):
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


def test_get_daily_campaign_stats_from_reports_merges_rows(monkeypatch):
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
  advertised_product_rows = [
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "advertisedAsin": "B0GNHFKQ8W",
      "attributedSalesSameSku14d": 20.0,
      "unitsSoldSameSku14d": 2,
    },
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "advertisedAsin": "B0G9765J19",
      "attributedSalesSameSku14d": 10.0,
      "unitsSoldSameSku14d": 1,
    },
  ]
  purchased_product_rows = [
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "purchasedAsin": "B0GNHFKQ8W",
      "salesOtherSku14d": 5.0,
      "unitsSoldOtherSku14d": 1,
    },
    {
      "campaignId": "123",
      "date": "2026-02-14",
      "purchasedAsin": "B0G9765J19",
      "salesOtherSku14d": 7.0,
      "unitsSoldOtherSku14d": 2,
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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
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
  assert daily.total_attributed_sales_usd == 99.0
  assert daily.total_units_sold == 9
  # Decomposition remaps high-priced "ebook" attributed rows into paperback.
  assert daily.gross_profit_before_ads_usd == pytest.approx(
    14.667368421052629,
    rel=1e-6,
  )
  assert daily.gross_profit_usd == pytest.approx(9.667368421052629, rel=1e-6)
  assert [item.asin
          for item in daily.sale_items] == ["B0G9765J19", "B0GNHFKQ8W"]
  ebook_item = next(item for item in daily.sale_items
                    if item.asin == "B0G9765J19")
  paperback_item = next(item for item in daily.sale_items
                        if item.asin == "B0GNHFKQ8W")
  assert ebook_item.units_sold == 3
  assert ebook_item.total_sales_usd == pytest.approx(11.210526315789473,
                                                      rel=1e-6)
  assert paperback_item.units_sold == 3
  assert paperback_item.total_sales_usd == pytest.approx(30.789473684210527,
                                                          rel=1e-6)
  assert paperback_item.kenp_pages_read == 0


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
  purchased_product_rows = []

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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
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
  purchased_product_rows = []

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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)
  monkeypatch.setattr(
    amazon,
    "_load_kdp_price_candidates_by_market_currency_asin",
    lambda *, start_date, end_date: {
      ("US", "USD", "B0G9765J19"): (2.99, ),
      ("US", "USD", "B0GNHFKQ8W"): (11.99, ),
    },
  )

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  by_asin = {item.asin: item for item in daily.sale_items}
  assert by_asin["B0G9765J19"].units_sold == 1
  assert by_asin["B0G9765J19"].total_sales_usd == pytest.approx(2.99, rel=1e-6)
  assert by_asin["B0GNHFKQ8W"].units_sold == 1
  assert by_asin["B0GNHFKQ8W"].total_sales_usd == pytest.approx(11.99,
                                                                rel=1e-6)


def test_get_daily_campaign_stats_from_reports_persists_ads_kenp_pages_by_asin(
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
  advertised_product_rows = []
  purchased_product_rows = [{
    "campaignId": "123",
    "date": "2026-02-14",
    "purchasedAsin": "B0G9765J19",
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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
  )

  assert len(output) == 1
  daily = output[0]
  assert daily.kenp_pages_read == 12
  assert daily.sale_items[0].kenp_pages_read == 12
  assert daily.sale_items[0].kenp_royalties_usd == pytest.approx(1.5, rel=1e-6)


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
  purchased_product_rows = []

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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
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
  purchased_product_rows = []

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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  output = amazon.get_daily_campaign_stats_from_reports(
    profile=profile,
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
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


def test_sp_advertised_product_columns_include_campaign_budget_currency_code():
  assert "campaignBudgetCurrencyCode" in amazon._SP_ADVERTISED_PRODUCT_COLUMNS


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
  purchased_product_rows = []

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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
  )

  def _fake_download(status: models.AmazonAdsReport):
    if status.report_id == "campaigns-id":
      return campaign_rows
    if status.report_id == "advertised-id":
      return advertised_product_rows
    if status.report_id == "products-id":
      return purchased_product_rows
    raise AssertionError(f"Unexpected status: {status}")

  monkeypatch.setattr(amazon, "_download_report_rows", _fake_download)

  with pytest.raises(amazon.AmazonAdsError, match="Unknown ASIN"):
    amazon.get_daily_campaign_stats_from_reports(
      profile=profile,
      campaigns_report=campaigns_report,
      advertised_products_report=advertised_products_report,
      purchased_products_report=purchased_products_report,
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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
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
      purchased_products_report=purchased_products_report,
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
  purchased_products_report = _report_status(
    report_id="products-id",
    status="COMPLETED",
    url="https://example.com/products.gz",
    profile_id="profile-1",
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
      purchased_products_report=purchased_products_report,
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
    "_collect_expected_report_ids_for_profile",
    lambda *, profile_id, reports_by_expected_key: ["r1", "r2", "r3"],
  )
  monkeypatch.setattr(
    amazon,
    "get_reports",
    lambda *, profile_id, report_ids, region: [
      _report_status(
        report_id="r1",
        status="COMPLETED",
        report_type_id="spCampaigns",
        profile_id=profile_id,
      ),
      _report_status(
        report_id="r2",
        status="COMPLETED",
        report_type_id="spAdvertisedProduct",
        profile_id=profile_id,
      ),
      _report_status(
        report_id="r3",
        status="COMPLETED",
        report_type_id="spPurchasedProduct",
        profile_id=profile_id,
      ),
    ],
  )
  monkeypatch.setattr(
    amazon,
    "_are_reports_complete",
    lambda campaigns_report, advertised_products_report,
    purchased_products_report: True,
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
        sale_items=[
          models.AmazonProductStats(
            asin="B0G9765J19",
            units_sold=1,
            total_sales_usd=10.0,
            total_profit_usd=4.0,
          )
        ],
      )
    ],
  )
  monkeypatch.setattr(
    amazon.firestore,
    "upsert_amazon_ads_daily_stats",
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
