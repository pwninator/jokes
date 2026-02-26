"""Amazon Ads API helpers for daily campaign profitability statistics."""

from __future__ import annotations

import dataclasses
import datetime
import gzip
import json
import pprint
from dataclasses import dataclass
from typing import Any, cast

import requests
from common import book_defs, config, models
from firebase_functions import logger
from services import firestore

_AMAZON_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
_AMAZON_ADS_API_BY_REGION = {
  "na": "https://advertising-api.amazon.com",
  "eu": "https://advertising-api-eu.amazon.com",
  "fe": "https://advertising-api-fe.amazon.com",
}
_GZIP_JSON_FORMAT = "GZIP_JSON"
_DAILY_TIME_UNIT = "DAILY"
_CREATE_REPORT_CONTENT_TYPE = "application/vnd.createasyncreportrequest.v3+json"
_REPORT_STATUS_COMPLETED = {"COMPLETED", "SUCCESS"}
_REPORT_STATUS_FAILED = {"FAILED", "CANCELLED"}
_REQUEST_TIMEOUT_SEC = 30
_USD_CURRENCY_CODE = "USD"

# Hard-coded FX rates to normalize all monetary values to USD.
# Updated: 2026-02-26
# Source: https://www.currency-converter.org.uk/currency-rates-today.html
_CURRENCY_CODE_TO_USD_RATE: dict[str, float] = {
  "USD": 1.0,
  "CAD": 0.7320,
  "GBP": 1.3569,
}
_COUNTRY_CODE_TO_CURRENCY_CODE: dict[str, str] = {
  "US": "USD",
  "CA": "CAD",
  "GB": "GBP",
  "UK": "GBP",
}

# Valid columns for Sponsored Products campaigns report
# https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/report-types/campaign
_SP_CAMPAIGNS_COLUMNS: list[str] = [
  "attributedSalesSameSku1d",
  "date",
  "campaignBiddingStrategy",
  "roasClicks14d",
  "unitsSoldClicks1d",
  "attributedSalesSameSku7d",
  "attributedSalesSameSku14d",
  "royaltyQualifiedBorrows",
  "sales1d",
  "sales7d",
  "addToList",
  "attributedSalesSameSku30d",
  "purchasesSameSku14d",
  "kindleEditionNormalizedPagesRoyalties14d",
  "purchasesSameSku1d",
  "spend",
  "unitsSoldSameSku1d",
  "purchases1d",
  "purchasesSameSku7d",
  "unitsSoldSameSku7d",
  "purchases7d",
  "unitsSoldSameSku30d",
  "cost",
  "costPerClick",
  "unitsSoldClicks14d",
  "retailer",
  "sales14d",
  "sales30d",
  "clickThroughRate",
  "impressions",
  "kindleEditionNormalizedPagesRead14d",
  "purchasesSameSku30d",
  "purchases14d",
  "unitsSoldClicks30d",
  "qualifiedBorrows",
  "acosClicks14d",
  "purchases30d",
  "clicks",
  "unitsSoldClicks7d",
  "unitsSoldSameSku14d",
  "campaignRuleBasedBudgetAmount",
  "campaignBudgetCurrencyCode",
  "campaignId",
  "campaignApplicableBudgetRuleId",
  "campaignBudgetType",
  "topOfSearchImpressionShare",
  "campaignStatus",
  "campaignName",
  "campaignApplicableBudgetRuleName",
  "campaignBudgetAmount",
]

# Valid columns for Sponsored Products purchased products report
# https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/report-types/purchased-product
_SP_PURCHASED_PRODUCT_COLUMNS: list[str] = [
  "date",
  "purchasesOtherSku7d",
  "unitsSoldClicks1d",
  "matchType",
  "unitsSoldOtherSku14d",
  "unitsSoldOtherSku30d",
  "sales7d",
  "salesOtherSku14d",
  "kindleEditionNormalizedPagesRoyalties14d",
  "salesOtherSku30d",
  "advertisedSku",
  "keyword",
  "salesOtherSku7d",
  "purchases7d",
  "targetId",
  "unitsSoldClicks14d",
  "adGroupName",
  "campaignId",
  "kindleEditionNormalizedPagesRead14d",
  "unitsSoldClicks30d",
  "qualifiedBorrows",
  "purchasesOtherSku30d",
  "portfolioId",
  "campaignBudgetCurrencyCode",
  "purchasesOtherSku14d",
  "purchasedAsin",
  "unitsSoldClicks7d",
  "keywordId",
  "royaltyQualifiedBorrows",
  "sales1d",
  "adGroupId",
  "addToList",
  "targeting",
  "unitsSoldOtherSku7d",
  "salesOtherSku1d",
  "keywordType",
  "advertisedAsin",
  "purchases1d",
  "purchasesOtherSku1d",
  "retailer",
  "sales14d",
  "sales30d",
  "unitsSoldOtherSku1d",
  "targetingExpression",
  "purchases14d",
  "purchases30d",
  "campaignName",
]

# Valid columns for Sponsored Products advertised products report
# https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/report-types/advertised-product
_SP_ADVERTISED_PRODUCT_COLUMNS: list[str] = [
  "campaignId",
  "campaignBudgetCurrencyCode",
  "date",
  "advertisedAsin",
  "attributedSalesSameSku14d",
  "unitsSoldSameSku14d",
  "sales14d",
  "unitsSoldClicks14d",
  "purchasesSameSku14d",
  "purchases14d",
]


class AmazonAdsError(Exception):
  """Raised when an Amazon Ads request or report operation fails."""


@dataclass(frozen=True, kw_only=True)
class AmazonAdsProfile:
  """Amazon Ads profile identity used for profile-scoped API calls."""

  profile_id: str
  region: str
  api_base: str
  country_code: str


@dataclass(frozen=True, kw_only=True)
class ReportPair:
  """Set of reports required for daily campaign stat computation."""

  campaigns_report: models.AmazonAdsReport
  advertised_products_report: models.AmazonAdsReport
  purchased_products_report: models.AmazonAdsReport


def get_profiles(*, region: str = "all") -> list[AmazonAdsProfile]:
  """Return Amazon Ads profiles for one region or all regions."""
  try:
    access_token = _get_access_token()
    region_api_bases = _resolve_region_api_bases(region)

    profiles: list[AmazonAdsProfile] = []
    for region_name, api_base in region_api_bases:
      profiles.extend(
        _list_profiles_for_region(
          api_base=api_base,
          access_token=access_token,
          region=region_name,
        ))
    return sorted(
      profiles,
      key=lambda profile:
      (profile.region, profile.country_code, profile.profile_id),
    )
  except requests.RequestException as exc:
    raise AmazonAdsError(f"Amazon Ads API request failed: {exc}") from exc


def request_daily_campaign_stats_reports(
  *,
  profile: AmazonAdsProfile,
  start_date: datetime.date,
  end_date: datetime.date,
) -> ReportPair:
  """Kick off the three DAILY reports needed for campaign profit stats."""
  _validate_report_date_range(start_date=start_date, end_date=end_date)

  access_token = _get_access_token()
  api_base = profile.api_base or _resolve_region_api_base(profile.region)

  campaigns_report = _create_report(
    api_base=api_base,
    access_token=access_token,
    profile=profile,
    payload=_build_sp_campaigns_report_payload(
      start_date=start_date,
      end_date=end_date,
    ),
  )
  advertised_products_report = _create_report(
    api_base=api_base,
    access_token=access_token,
    profile=profile,
    payload=_build_sp_advertised_product_report_payload(
      start_date=start_date,
      end_date=end_date,
    ),
  )
  purchased_products_report = _create_report(
    api_base=api_base,
    access_token=access_token,
    profile=profile,
    payload=_build_sp_purchased_product_report_payload(
      start_date=start_date,
      end_date=end_date,
    ),
  )
  campaigns_report = firestore.upsert_amazon_ads_report(campaigns_report)
  advertised_products_report = firestore.upsert_amazon_ads_report(
    advertised_products_report)
  purchased_products_report = firestore.upsert_amazon_ads_report(
    purchased_products_report)

  return ReportPair(
    campaigns_report=campaigns_report,
    advertised_products_report=advertised_products_report,
    purchased_products_report=purchased_products_report,
  )


def get_reports(
  *,
  profile_id: str,
  report_ids: list[str],
  region: str = "na",
) -> list[models.AmazonAdsReport]:
  """Fetch reports by report IDs for a profile."""

  access_token = _get_access_token()
  api_base = _resolve_region_api_base(region)

  if not report_ids:
    return []

  statuses: list[models.AmazonAdsReport] = []
  for report_id in report_ids:
    if not report_id.strip():
      continue
    status = _fetch_report(
      api_base=api_base,
      access_token=access_token,
      profile_id=profile_id,
      report_id=report_id.strip(),
    )
    statuses.append(firestore.upsert_amazon_ads_report(status))
  return statuses


def get_daily_campaign_stats_from_reports(
  *,
  profile: AmazonAdsProfile,
  campaigns_report: models.AmazonAdsReport,
  advertised_products_report: models.AmazonAdsReport,
  purchased_products_report: models.AmazonAdsReport,
) -> list[models.AmazonAdsDailyCampaignStats]:
  """Merge daily campaign stats from three completed report objects."""
  _validate_report_profile_match(profile=profile, report=campaigns_report)
  _validate_report_profile_match(profile=profile,
                                 report=advertised_products_report)
  _validate_report_profile_match(profile=profile,
                                 report=purchased_products_report)
  _raise_if_report_not_completed(campaigns_report)
  _raise_if_report_not_completed(advertised_products_report)
  _raise_if_report_not_completed(purchased_products_report)

  campaign_rows = _download_report_rows(campaigns_report)
  advertised_product_rows = _download_report_rows(advertised_products_report)
  purchased_product_rows = _download_report_rows(purchased_products_report)
  merged_stats = _merge_report_rows(
    campaign_rows=campaign_rows,
    advertised_product_rows=advertised_product_rows,
    purchased_product_rows=purchased_product_rows,
    profile_country_code=profile.country_code,
  )
  return merged_stats


def _validate_report_date_range(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> None:
  """Validate that the requested report window is chronologically valid."""
  if end_date < start_date:
    raise ValueError("end_date must be on or after start_date")


def _resolve_region_api_base(region: str) -> str:
  """Resolve an Amazon Ads API base URL from a region key."""
  api_base = _AMAZON_ADS_API_BY_REGION.get(region.strip().lower())
  if not api_base:
    allowed = ", ".join(sorted(_AMAZON_ADS_API_BY_REGION.keys()))
    raise ValueError(f"Invalid region '{region}'. Allowed values: {allowed}")
  return api_base


def _resolve_region_api_bases(region: str) -> list[tuple[str, str]]:
  """Resolve one or many region API hosts from a region selector."""
  normalized_region = region.strip().lower()
  if normalized_region == "all":
    return list(_AMAZON_ADS_API_BY_REGION.items())
  return [(normalized_region, _resolve_region_api_base(normalized_region))]


def _get_access_token() -> str:
  """Exchange the configured refresh token for an LWA access token."""
  payload = _request_json(
    "POST",
    _AMAZON_TOKEN_URL,
    data={
      "grant_type": "refresh_token",
      "refresh_token": config.get_amazon_api_refresh_token(),
      "client_id": config.AMAZON_API_CLIENT_ID,
      "client_secret": config.get_amazon_api_client_secret(),
    },
  )
  access_token = str(payload.get("access_token", "")).strip()
  if not access_token:
    raise AmazonAdsError("Amazon LWA response did not include access_token")
  return access_token


def _build_ads_headers(
  *,
  access_token: str,
  profile_id: str,
  content_type: str | None = None,
) -> dict[str, str]:
  """Build standard Amazon Ads headers for a profile-scoped request."""
  headers = {
    "Amazon-Advertising-API-ClientId": config.AMAZON_API_CLIENT_ID,
    "Amazon-Advertising-API-Scope": profile_id,
    "Authorization": f"Bearer {access_token}",
  }
  if content_type:
    headers["Content-Type"] = content_type
  return headers


def _list_profiles_for_region(
  *,
  api_base: str,
  access_token: str,
  region: str,
) -> list[AmazonAdsProfile]:
  """Fetch and normalize all profiles from one regional Amazon Ads host."""
  response = requests.get(
    f"{api_base}/v2/profiles",
    headers={
      "Amazon-Advertising-API-ClientId": config.AMAZON_API_CLIENT_ID,
      "Authorization": f"Bearer {access_token}",
    },
    timeout=_REQUEST_TIMEOUT_SEC,
  )
  response.raise_for_status()

  try:
    payload_raw = response.json()
  except ValueError as exc:
    raise AmazonAdsError(
      f"Invalid JSON profile list response from {api_base}/v2/profiles"
    ) from exc
  if not isinstance(payload_raw, list):
    raise AmazonAdsError(
      f"Expected profile list response from {api_base}/v2/profiles: {payload_raw}"
    )

  profiles: list[AmazonAdsProfile] = []
  for item in cast(list[Any], payload_raw):
    if not isinstance(item, dict):
      continue
    item_dict = cast(dict[str, Any], item)
    profile_id = _required_str(item_dict.get("profileId"))
    if not profile_id:
      continue
    profiles.append(
      AmazonAdsProfile(
        profile_id=profile_id,
        region=region,
        api_base=api_base,
        country_code=_required_str(item_dict.get("countryCode")).upper(),
      ))
  return profiles


def _build_sp_campaigns_report_payload(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> dict[str, Any]:
  """Construct the report payload for daily Sponsored Products campaigns."""
  return {
    "name": f"spCampaigns {start_date.isoformat()} to {end_date.isoformat()}",
    "startDate": start_date.isoformat(),
    "endDate": end_date.isoformat(),
    "configuration": {
      "adProduct": "SPONSORED_PRODUCTS",
      "groupBy": ["campaign"],
      "columns": _SP_CAMPAIGNS_COLUMNS,
      "reportTypeId": "spCampaigns",
      "timeUnit": _DAILY_TIME_UNIT,
      "format": _GZIP_JSON_FORMAT,
    },
  }


def _build_sp_purchased_product_report_payload(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> dict[str, Any]:
  """Construct the report payload for daily Sponsored Products purchases."""
  return {
    "name":
    f"spPurchasedProduct {start_date.isoformat()} to {end_date.isoformat()}",
    "startDate": start_date.isoformat(),
    "endDate": end_date.isoformat(),
    "configuration": {
      "adProduct": "SPONSORED_PRODUCTS",
      "groupBy": ["asin"],
      "columns": _SP_PURCHASED_PRODUCT_COLUMNS,
      "reportTypeId": "spPurchasedProduct",
      "timeUnit": _DAILY_TIME_UNIT,
      "format": _GZIP_JSON_FORMAT,
    },
  }


def _build_sp_advertised_product_report_payload(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> dict[str, Any]:
  """Construct the report payload for daily Sponsored Products advertised ASINs."""
  return {
    "name":
    f"spAdvertisedProduct {start_date.isoformat()} to {end_date.isoformat()}",
    "startDate": start_date.isoformat(),
    "endDate": end_date.isoformat(),
    "configuration": {
      "adProduct": "SPONSORED_PRODUCTS",
      "groupBy": ["advertiser"],
      "columns": _SP_ADVERTISED_PRODUCT_COLUMNS,
      "reportTypeId": "spAdvertisedProduct",
      "timeUnit": _DAILY_TIME_UNIT,
      "format": _GZIP_JSON_FORMAT,
    },
  }


def _create_report(
  *,
  api_base: str,
  access_token: str,
  profile: AmazonAdsProfile,
  payload: dict[str, Any],
) -> models.AmazonAdsReport:
  """Create a report and return the full Amazon report metadata."""
  report_type_id = _extract_report_type_id(payload)
  payload_with_name = dict(payload)
  payload_with_name["name"] = _build_report_name(
    report_type_id=report_type_id,
    profile_country=profile.country_code,
  )
  response = _request_json(
    "POST",
    f"{api_base}/reporting/reports",
    headers=_build_ads_headers(
      access_token=access_token,
      profile_id=profile.profile_id,
      content_type=_CREATE_REPORT_CONTENT_TYPE,
    ),
    json_payload=payload_with_name,
  )
  parsed = _parse_report_status_payload(response)
  return dataclasses.replace(
    parsed,
    profile_id=profile.profile_id,
    profile_country=profile.country_code,
    region=profile.region,
    api_base=api_base,
  )


def _fetch_report(
  *,
  api_base: str,
  access_token: str,
  profile_id: str,
  report_id: str,
) -> models.AmazonAdsReport:
  """Fetch details for a single report ID."""
  response = _request_json(
    "GET",
    f"{api_base}/reporting/reports/{report_id}",
    headers=_build_ads_headers(access_token=access_token,
                               profile_id=profile_id),
  )
  parsed = _parse_report_status_payload(response)
  parsed_with_context = dataclasses.replace(
    parsed,
    profile_id=profile_id,
    region=_region_from_api_base(api_base),
    api_base=api_base,
  )
  if parsed.report_id != report_id:
    return dataclasses.replace(
      parsed_with_context,
      report_id=report_id,
    )
  return parsed_with_context


def _parse_report_status_payload(
  payload: dict[str, Any], ) -> models.AmazonAdsReport:
  """Parse a report status payload from the Amazon Ads API."""
  try:
    return models.AmazonAdsReport.from_amazon_payload(payload)
  except ValueError as exc:
    raise AmazonAdsError(
      f"Invalid report status payload: {exc}. payload={payload}") from exc


def _raise_if_report_not_completed(status: models.AmazonAdsReport) -> None:
  """Raise if a report is failed or still processing instead of completed."""
  normalized_status = status.status.upper()
  if normalized_status in _REPORT_STATUS_COMPLETED:
    return
  if normalized_status in _REPORT_STATUS_FAILED:
    raise AmazonAdsError(
      f"Report {status.report_id} failed with status={status.status} "
      f"reason={status.failure_reason}")
  raise AmazonAdsError(f"Report {status.report_id} is not completed yet. "
                       f"Current status: {status.status}")


def _validate_report_profile_match(
  *,
  profile: AmazonAdsProfile,
  report: models.AmazonAdsReport,
) -> None:
  """Validate report.profile_id matches the provided profile when present."""
  report_profile_id = (report.profile_id or "").strip()
  if not report_profile_id:
    return
  if report_profile_id != profile.profile_id:
    raise ValueError(
      f"Report {report.report_id} belongs to profile {report_profile_id}, "
      f"but expected {profile.profile_id}")


def _download_report_rows(
  report: models.AmazonAdsReport, ) -> list[dict[str, Any]]:
  """Download and decompress a completed report into raw row dictionaries."""
  if not report.url:
    raise AmazonAdsError(
      f"Report {report.report_id} is completed but missing download URL")

  logger.info(f"Downloading report {report.report_id} from {report.url}")
  response = requests.get(report.url, timeout=_REQUEST_TIMEOUT_SEC)
  response.raise_for_status()
  compressed_data = response.content

  try:
    decoded_text = gzip.decompress(compressed_data).decode("utf-8")
  except OSError as exc:
    raise AmazonAdsError(
      f"Failed to decompress report {report.report_id}: {exc}") from exc

  return _parse_report_rows_text(report.report_name, decoded_text)


def _parse_report_rows_text(report_name: str,
                            text: str) -> list[dict[str, Any]]:
  """Parse report text that may be JSON array/object or JSON-lines."""
  stripped = text.strip()
  if not stripped:
    return []

  logger.info(f"Parsing text for report {report_name}: {stripped}")
  try:
    parsed_raw = json.loads(stripped)
    logger.info(f"Parsed report {report_name}: {pprint.pformat(parsed_raw)}")
    if isinstance(parsed_raw, list):
      rows_from_list: list[dict[str, Any]] = []
      for row in cast(list[Any], parsed_raw):
        if isinstance(row, dict):
          rows_from_list.append(cast(dict[str, Any], row))
      return rows_from_list
    if isinstance(parsed_raw, dict):
      return [cast(dict[str, Any], parsed_raw)]
  except json.JSONDecodeError:
    pass

  rows: list[dict[str, Any]] = []
  for line in stripped.splitlines():
    line = line.strip()
    if not line:
      continue
    try:
      parsed_line = json.loads(line)
    except json.JSONDecodeError:
      continue
    if isinstance(parsed_line, dict):
      rows.append(cast(dict[str, Any], parsed_line))
  return rows


def _merge_report_rows(
  *,
  campaign_rows: list[dict[str, Any]],
  advertised_product_rows: list[dict[str, Any]],
  purchased_product_rows: list[dict[str, Any]],
  profile_country_code: str,
) -> list[models.AmazonAdsDailyCampaignStats]:
  """Merge report rows by day and normalize all monetary fields to USD."""
  advertised_by_campaign_date = _index_rows_by_campaign_and_date(
    advertised_product_rows)
  purchased_by_campaign_date = _index_rows_by_campaign_and_date(
    purchased_product_rows)

  output: list[models.AmazonAdsDailyCampaignStats] = []
  for campaign_row in campaign_rows:
    campaign_id = _required_str(campaign_row.get("campaignId"))
    date_value = _parse_report_date(campaign_row.get("date"))
    if not campaign_id or date_value is None:
      continue

    campaign_name = _required_str(campaign_row.get("campaignName"))
    if not campaign_name:
      campaign_name = _required_str(campaign_row.get("name"))

    currency_code = _resolve_currency_code(
      campaign_row=campaign_row,
      profile_country_code=profile_country_code,
    )
    spend = _convert_amount_to_usd(
      _as_float(campaign_row.get("cost")),
      currency_code=currency_code,
    )
    impressions = _as_int(campaign_row.get("impressions"))
    clicks = _as_int(campaign_row.get("clicks"))
    total_attributed_sales_usd = _convert_amount_to_usd(
      _as_float(campaign_row.get("sales14d")),
      currency_code=currency_code,
    )
    total_units_sold = _as_int(campaign_row.get("unitsSoldClicks14d"))
    kenp_royalties_usd = _as_float(
      campaign_row.get("kindleEditionNormalizedPagesRoyalties14d"))
    if kenp_royalties_usd == 0.0:
      kenp_royalties_usd = _as_float(
        campaign_row.get("attributedKindleEditionNormalizedPagesRoyalties14d"))
    kenp_royalties_usd = _convert_amount_to_usd(
      kenp_royalties_usd,
      currency_code=currency_code,
    )

    sale_items = _build_merged_sale_items_for_campaign_day(
      campaign_id=campaign_id,
      date_value=date_value,
      advertised_by_campaign_date=advertised_by_campaign_date,
      purchased_by_campaign_date=purchased_by_campaign_date,
      currency_code=currency_code,
    )
    product_profit_total = sum(item.total_profit_usd for item in sale_items)

    gross_profit_before_ads_usd = product_profit_total + kenp_royalties_usd
    gross_profit_usd = gross_profit_before_ads_usd - spend
    output.append(
      models.AmazonAdsDailyCampaignStats(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        date=date_value,
        spend=spend,
        impressions=impressions,
        clicks=clicks,
        kenp_royalties_usd=kenp_royalties_usd,
        total_attributed_sales_usd=total_attributed_sales_usd,
        total_units_sold=total_units_sold,
        gross_profit_before_ads_usd=gross_profit_before_ads_usd,
        gross_profit_usd=gross_profit_usd,
        sale_items=sale_items,
      ))

  return sorted(output, key=lambda stat: (stat.date, stat.campaign_id))


def _index_rows_by_campaign_and_date(
  rows: list[dict[str, Any]],
) -> dict[tuple[str, datetime.date], list[dict[str, Any]]]:
  """Index report rows by `(campaign_id, date)`."""
  rows_by_campaign_date: dict[tuple[str, datetime.date], list[dict[str,
                                                                   Any]]] = {}
  for row in rows:
    campaign_id = _required_str(row.get("campaignId"))
    date_value = _parse_report_date(row.get("date"))
    if not campaign_id or date_value is None:
      continue
    rows_by_campaign_date.setdefault((campaign_id, date_value), []).append(row)
  return rows_by_campaign_date


def _build_merged_sale_items_for_campaign_day(
  *,
  campaign_id: str,
  date_value: datetime.date,
  advertised_by_campaign_date: dict[tuple[str, datetime.date],
                                    list[dict[str, Any]]],
  purchased_by_campaign_date: dict[tuple[str, datetime.date], list[dict[str,
                                                                        Any]]],
  currency_code: str,
) -> list[models.AmazonProductStats]:
  """Build merged ASIN sale items by combining direct and halo sources."""
  merged_totals_by_asin: dict[str, tuple[int, float]] = {}
  key = (campaign_id, date_value)

  for row in advertised_by_campaign_date.get(key, []):
    asin = _required_str(row.get("advertisedAsin"))
    if not asin:
      continue
    direct_units = _extract_direct_units_sold(row)
    direct_sales = _convert_amount_to_usd(
      _extract_direct_sales_amount(row),
      currency_code=currency_code,
    )
    _accumulate_asin_totals(merged_totals_by_asin, asin, direct_units,
                            direct_sales)

  for row in purchased_by_campaign_date.get(key, []):
    asin = _required_str(row.get("purchasedAsin"))
    if not asin:
      continue
    halo_units = _as_int(row.get("unitsSoldOtherSku14d"))
    halo_sales = _convert_amount_to_usd(
      _as_float(row.get("salesOtherSku14d")),
      currency_code=currency_code,
    )
    _accumulate_asin_totals(merged_totals_by_asin, asin, halo_units,
                            halo_sales)

  sale_items: list[models.AmazonProductStats] = []
  for asin, (units_sold,
             sales_amount) in sorted(merged_totals_by_asin.items()):
    sale_items.append(
      _build_product_stats(
        asin=asin,
        units_sold=units_sold,
        total_sales_usd=sales_amount,
      ))
  return sale_items


def _extract_direct_sales_amount(advertised_row: dict[str, Any]) -> float:
  """Return direct sales amount from an advertised-product row."""
  sales_amount = _as_float(advertised_row.get("attributedSalesSameSku14d"))
  if sales_amount != 0.0:
    return sales_amount
  return _as_float(advertised_row.get("sales14d"))


def _extract_direct_units_sold(advertised_row: dict[str, Any]) -> int:
  """Return direct unit count from an advertised-product row."""
  units_sold = _as_int(advertised_row.get("unitsSoldSameSku14d"))
  if units_sold != 0:
    return units_sold
  units_sold = _as_int(advertised_row.get("unitsSoldClicks14d"))
  if units_sold != 0:
    return units_sold
  units_sold = _as_int(advertised_row.get("purchasesSameSku14d"))
  if units_sold != 0:
    return units_sold
  return _as_int(advertised_row.get("purchases14d"))


def _accumulate_asin_totals(
  merged_totals_by_asin: dict[str, tuple[int, float]],
  asin: str,
  units_sold: int,
  sales_amount: float,
) -> None:
  """Add sales totals into an ASIN accumulator, merging repeated rows."""
  existing_units, existing_sales = merged_totals_by_asin.get(asin, (0, 0.0))
  merged_totals_by_asin[asin] = (
    existing_units + units_sold,
    existing_sales + sales_amount,
  )


def _build_product_stats(
  *,
  asin: str,
  units_sold: int,
  total_sales_usd: float,
) -> models.AmazonProductStats:
  """Build a normalized `ProductStats` object from merged ASIN totals."""
  book_variant = book_defs.BOOK_VARIANTS_BY_ASIN.get(asin)
  if not book_variant:
    raise AmazonAdsError(f"Unknown ASIN: {asin}")

  total_profit_usd = (total_sales_usd * book_variant.royalty_rate) - (
    units_sold * book_variant.print_cost)

  return models.AmazonProductStats(
    asin=asin,
    units_sold=units_sold,
    total_sales_usd=total_sales_usd,
    total_profit_usd=total_profit_usd,
  )


def _extract_report_type_id(payload: dict[str, Any]) -> str:
  """Extract reportTypeId from a create-report payload."""
  configuration_raw = payload.get("configuration")
  if not isinstance(configuration_raw, dict):
    raise AmazonAdsError(
      f"Report payload missing configuration object: {payload}")
  configuration = cast(dict[str, Any], configuration_raw)
  report_type_id = _required_str(configuration.get("reportTypeId"))
  if not report_type_id:
    raise AmazonAdsError(
      f"Report payload missing configuration.reportTypeId: {payload}")
  return report_type_id


def _build_report_name(
  *,
  report_type_id: str,
  profile_country: str,
) -> str:
  """Build canonical report name `YYYYMMDD_HHMMSS_[reportTypeId]_[country]`."""
  timestamp_utc = datetime.datetime.now(
    datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
  country_code = _required_str(profile_country).upper() or "UNKNOWN"
  return f"{timestamp_utc}_{report_type_id}_{country_code}"


def _region_from_api_base(api_base: str) -> str | None:
  """Return a region key matching the provided API base URL."""
  for region_name, candidate in _AMAZON_ADS_API_BY_REGION.items():
    if candidate == api_base:
      return region_name
  return None


def _request_json(  # pylint: disable=too-many-arguments
  method: str,
  url: str,
  *,
  headers: dict[str, str] | None = None,
  params: dict[str, Any] | None = None,
  data: dict[str, Any] | None = None,
  json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Execute an HTTP request and return a validated JSON object payload."""
  logger.info(
    f"Amazon Ads request: {method} {url}",
    extra={"json_fields": {
      "method": method,
      "url": url
    }},
  )
  response = requests.request(
    method=method,
    url=url,
    headers=headers,
    params=params,
    data=data,
    json=json_payload,
    timeout=_REQUEST_TIMEOUT_SEC,
  )

  try:
    payload_raw: Any = response.json()
  except ValueError:
    payload_raw = {"message": response.text}

  if not 200 <= response.status_code < 300:
    raise AmazonAdsError(
      f"Amazon Ads request failed {response.status_code}: {payload_raw}")

  if not isinstance(payload_raw, dict):
    raise AmazonAdsError(
      f"Expected JSON object response from {url}: {payload_raw}")
  return cast(dict[str, Any], payload_raw)


def _parse_report_date(value: Any) -> datetime.date | None:
  """Parse Amazon date strings in `YYYY-MM-DD` or `YYYYMMDD` format."""
  raw = _required_str(value)
  if not raw:
    return None

  for fmt in ("%Y-%m-%d", "%Y%m%d"):
    try:
      return datetime.datetime.strptime(raw, fmt).date()
    except ValueError:
      continue
  return None


def _required_str(value: Any) -> str:
  """Normalize a value to a stripped string, defaulting missing values to empty."""
  if value is None:
    return ""
  return str(value).strip()


def _as_int(value: Any) -> int:
  """Best-effort integer conversion with safe fallback to zero."""
  if value is None:
    return 0
  if isinstance(value, bool):
    return int(value)
  if isinstance(value, int):
    return value
  try:
    return int(float(str(value).strip()))
  except (TypeError, ValueError):
    return 0


def _as_float(value: Any) -> float:
  """Best-effort float conversion with safe fallback to zero."""
  if value is None:
    return 0.0
  if isinstance(value, (int, float)) and not isinstance(value, bool):
    return float(value)
  try:
    return float(str(value).strip())
  except (TypeError, ValueError):
    return 0.0


def _resolve_currency_code(
  *,
  campaign_row: dict[str, Any],
  profile_country_code: str,
) -> str:
  """Resolve row currency from report payload with profile-country fallback."""
  row_currency_code = _required_str(
    campaign_row.get("campaignBudgetCurrencyCode")).upper()
  if row_currency_code:
    return row_currency_code

  profile_currency_code = _COUNTRY_CODE_TO_CURRENCY_CODE.get(
    profile_country_code.strip().upper(), "")
  if profile_currency_code:
    return profile_currency_code
  return _USD_CURRENCY_CODE


def _convert_amount_to_usd(amount: float, *, currency_code: str) -> float:
  """Convert a monetary amount from a supported currency into USD."""
  rate = _CURRENCY_CODE_TO_USD_RATE.get(currency_code.upper())
  if rate is None:
    raise AmazonAdsError(f"Unsupported currency code for USD conversion: "
                         f"{currency_code}")
  return amount * rate
