"""Amazon Ads API helpers for daily campaign profitability statistics."""

from __future__ import annotations

import dataclasses
import datetime
import gzip
import json
import pprint
import time
from dataclasses import dataclass
from typing import Any, cast

import requests
from common import book_defs, config, models
from firebase_functions import logger
from services import amazon_sales_reconciliation, firestore

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

# Ads stats report orchestration
ADS_STATS_TARGET_COUNTRY_CODES = frozenset({"US", "CA", "UK", "GB"})
ADS_STATS_REPORT_WINDOW_DAYS = 30
ADS_STATS_REPORT_METADATA_WAIT_SEC = 5
ADS_STATS_REQUIRED_REPORT_TYPES = (
  "spCampaigns",
  "spAdvertisedProduct",
  "spPurchasedProduct",
)
_KDP_PRICE_CANDIDATE_LOOKBACK_DAYS = 180
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
_COUNTRY_CODE_TO_MARKET_CODE: dict[str, str] = {
  "US": "US",
  "CA": "CA",
  "GB": "GB",
  "UK": "GB",
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


@dataclass(frozen=True, kw_only=True)
class _DecomposedSaleAllocation:
  """One inferred ASIN allocation for an advertised-product row."""

  asin: str
  units_sold: int
  total_sales_usd: float


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

  kdp_price_candidates_by_market_currency_asin = (
    _load_kdp_price_candidates_by_market_currency_asin(
      start_date=campaigns_report.start_date -
      datetime.timedelta(days=_KDP_PRICE_CANDIDATE_LOOKBACK_DAYS),
      end_date=campaigns_report.end_date,
    ))

  campaign_rows = _download_report_rows(campaigns_report)
  advertised_product_rows = _download_report_rows(advertised_products_report)
  purchased_product_rows = _download_report_rows(purchased_products_report)
  merged_stats = _merge_report_rows(
    campaign_rows=campaign_rows,
    advertised_product_rows=advertised_product_rows,
    purchased_product_rows=purchased_product_rows,
    profile_country_code=profile.country_code,
    kdp_price_candidates_by_market_currency_asin=(
      kdp_price_candidates_by_market_currency_asin),
  )
  return merged_stats


@dataclasses.dataclass
class AdsStatsContext:
  """Shared context for ads stats request and fetch phases."""

  selected_profiles: list[AmazonAdsProfile]
  reports_by_expected_key: dict[tuple[str, str], models.AmazonAdsReport]
  report_end_date: datetime.date
  report_start_date: datetime.date
  profiles_considered: int


def get_ads_stats_context(run_time_utc: datetime.datetime) -> AdsStatsContext:
  """Build shared context: profiles, report window, and existing reports."""
  report_end_date = run_time_utc.date()
  report_start_date = report_end_date - datetime.timedelta(
    days=ADS_STATS_REPORT_WINDOW_DAYS)
  today_utc = run_time_utc.date()
  profiles = get_profiles(region="all")
  existing_reports = firestore.list_amazon_ads_reports(
    created_on_or_after=today_utc - datetime.timedelta(days=2))

  selected_profiles = sorted(
    [
      profile for profile in profiles
      if profile.country_code.upper() in ADS_STATS_TARGET_COUNTRY_CODES
    ],
    key=lambda profile:
    (profile.country_code, profile.region, profile.profile_id),
  )

  reports_by_expected_key = _select_today_reports_for_window(
    reports=existing_reports,
    today_utc=today_utc,
    report_start_date=report_start_date,
    report_end_date=report_end_date,
  )

  return AdsStatsContext(
    selected_profiles=selected_profiles,
    reports_by_expected_key=reports_by_expected_key,
    report_end_date=report_end_date,
    report_start_date=report_start_date,
    profiles_considered=len(profiles),
  )


@dataclasses.dataclass(frozen=True)
class AdsStatsRequestResult:
  """Result of requesting ads stats reports."""

  selected_profiles: list[AmazonAdsProfile]
  reports_by_expected_key: dict[tuple[str, str], models.AmazonAdsReport]
  report_requests: list[dict[str, str]]
  report_end_date: datetime.date
  report_start_date: datetime.date
  profiles_considered: int


def request_ads_stats_reports(
    run_time_utc: datetime.datetime) -> AdsStatsRequestResult:
  """Request ads reports for target profiles if there are no pending ones."""
  ctx = get_ads_stats_context(run_time_utc)

  report_requests: list[dict[str, str]] = []
  for profile in ctx.selected_profiles:
    if _has_all_required_reports(
        profile_id=profile.profile_id,
        reports_by_expected_key=ctx.reports_by_expected_key,
    ) and not _are_all_reports_processed(
        profile_id=profile.profile_id,
        reports_by_expected_key=ctx.reports_by_expected_key,
    ):
      continue

    report_pair = request_daily_campaign_stats_reports(
      profile=profile,
      start_date=ctx.report_start_date,
      end_date=ctx.report_end_date,
    )
    ctx.reports_by_expected_key[(profile.profile_id,
                                 report_pair.campaigns_report.report_type_id
                                 )] = report_pair.campaigns_report
    ctx.reports_by_expected_key[(
      profile.profile_id, report_pair.advertised_products_report.report_type_id
    )] = report_pair.advertised_products_report
    ctx.reports_by_expected_key[(
      profile.profile_id, report_pair.purchased_products_report.report_type_id
    )] = report_pair.purchased_products_report
    report_requests.append({
      "profile_id":
      profile.profile_id,
      "country_code":
      profile.country_code,
      "region":
      profile.region,
      "campaigns_report_id":
      report_pair.campaigns_report.report_id,
      "advertised_products_report_id":
      report_pair.advertised_products_report.report_id,
      "purchased_products_report_id":
      report_pair.purchased_products_report.report_id,
    })

  return AdsStatsRequestResult(
    selected_profiles=ctx.selected_profiles,
    reports_by_expected_key=ctx.reports_by_expected_key,
    report_requests=report_requests,
    report_end_date=ctx.report_end_date,
    report_start_date=ctx.report_start_date,
    profiles_considered=ctx.profiles_considered,
  )


def fetch_ads_stats_reports(
  run_time_utc: datetime.datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  """Get report status and, if ready and unprocessed, fetch and process them."""
  ctx = get_ads_stats_context(run_time_utc)
  time.sleep(ADS_STATS_REPORT_METADATA_WAIT_SEC)
  report_metadata: list[dict[str, Any]] = []
  daily_campaign_stats_rows: list[dict[str, Any]] = []
  earliest_reconciled_date: datetime.date | None = None

  for profile in ctx.selected_profiles:
    report_ids = _collect_expected_report_ids_for_profile(
      profile_id=profile.profile_id,
      reports_by_expected_key=ctx.reports_by_expected_key,
    )
    if not report_ids:
      continue
    statuses = get_reports(
      profile_id=profile.profile_id,
      report_ids=report_ids,
      region=profile.region,
    )
    for status in statuses:
      status_row = status.to_dict(include_key=True)
      if not status_row.get("profile_country"):
        status_row["profile_country"] = profile.country_code
      if not status_row.get("region"):
        status_row["region"] = profile.region
      if not status_row.get("api_base"):
        status_row["api_base"] = profile.api_base
      report_metadata.append(status_row)

    reports_by_type = {report.report_type_id: report for report in statuses}
    campaigns_report = reports_by_type.get("spCampaigns")
    advertised_products_report = reports_by_type.get("spAdvertisedProduct")
    purchased_products_report = reports_by_type.get("spPurchasedProduct")
    if (campaigns_report and advertised_products_report
        and purchased_products_report and _are_reports_complete(
          campaigns_report,
          advertised_products_report,
          purchased_products_report,
        )):
      if (not campaigns_report.processed
          or not advertised_products_report.processed
          or not purchased_products_report.processed):

        daily_campaign_stats = get_daily_campaign_stats_from_reports(
          profile=profile,
          campaigns_report=campaigns_report,
          advertised_products_report=advertised_products_report,
          purchased_products_report=purchased_products_report,
        )

        # Aggregate stats by date
        stats_by_date: dict[datetime.date, models.AmazonAdsDailyStats] = {}
        for campaign_stat in daily_campaign_stats:
          if campaign_stat.date not in stats_by_date:
            stats_by_date[campaign_stat.date] = models.AmazonAdsDailyStats(
              date=campaign_stat.date, )

          daily_stat = stats_by_date[campaign_stat.date]
          daily_stat.campaigns_by_id[campaign_stat.campaign_id] = campaign_stat

          # Aggregate metrics
          daily_stat.spend += campaign_stat.spend
          daily_stat.impressions += campaign_stat.impressions
          daily_stat.clicks += campaign_stat.clicks
          daily_stat.kenp_pages_read += campaign_stat.kenp_pages_read
          daily_stat.kenp_royalties_usd += campaign_stat.kenp_royalties_usd
          daily_stat.total_attributed_sales_usd += campaign_stat.total_attributed_sales_usd
          daily_stat.total_units_sold += campaign_stat.total_units_sold
          daily_stat.gross_profit_before_ads_usd += campaign_stat.gross_profit_before_ads_usd
          daily_stat.gross_profit_usd += campaign_stat.gross_profit_usd

        # Upsert aggregated stats
        daily_stats_list = list(stats_by_date.values())
        _ = firestore.upsert_amazon_ads_daily_stats(daily_stats_list)
        if daily_stats_list:
          current_min_date = min(stat.date for stat in daily_stats_list)
          if (earliest_reconciled_date is None
              or current_min_date < earliest_reconciled_date):
            earliest_reconciled_date = current_min_date

        # Mark reports as processed
        campaigns_report.processed = True
        advertised_products_report.processed = True
        purchased_products_report.processed = True
        _ = firestore.upsert_amazon_ads_report(campaigns_report)
        _ = firestore.upsert_amazon_ads_report(advertised_products_report)
        _ = firestore.upsert_amazon_ads_report(purchased_products_report)

        # Flatten for logging and debugging response (keeping original format)
        for daily_stat in daily_stats_list:
          for campaign_stat in daily_stat.campaigns_by_id.values():
            stat_row = campaign_stat.to_dict(include_key=True)
            stat_row["profile_id"] = profile.profile_id
            stat_row["profile_country"] = profile.country_code
            stat_row["region"] = profile.region
            daily_campaign_stats_rows.append(stat_row)
      else:
        logger.info(
          f"Reports already processed for profile {profile.profile_id}")
    else:
      logger.info(f"Reports not complete for profile {profile.profile_id}")

  if earliest_reconciled_date is not None:
    _ = amazon_sales_reconciliation.reconcile_daily_sales(
      earliest_changed_date=earliest_reconciled_date,
      run_time_utc=run_time_utc,
    )

  return report_metadata, daily_campaign_stats_rows


def _select_today_reports_for_window(
  *,
  reports: list[models.AmazonAdsReport],
  today_utc: datetime.date,
  report_start_date: datetime.date,
  report_end_date: datetime.date,
) -> dict[tuple[str, str], models.AmazonAdsReport]:
  """Pick most recent report per profile/type created today for the target window."""
  selected: dict[tuple[str, str], models.AmazonAdsReport] = {}
  for report in reports:
    profile_id = report.profile_id or ""
    if not profile_id:
      continue
    if report.report_type_id not in ADS_STATS_REQUIRED_REPORT_TYPES:
      continue
    if (report.start_date != report_start_date
        or report.end_date != report_end_date):
      continue
    if report.created_at.date() != today_utc:
      continue

    key = (profile_id, report.report_type_id)
    existing = selected.get(key)
    if existing is None:
      selected[key] = report
      continue

    if report.created_at > existing.created_at:
      selected[key] = report
      continue
    if (report.created_at == existing.created_at
        and report.updated_at > existing.updated_at):
      selected[key] = report
  return selected


def _has_all_required_reports(
  *,
  profile_id: str,
  reports_by_expected_key: dict[tuple[str, str], models.AmazonAdsReport],
) -> bool:
  """Return whether all required report types exist for the profile."""
  return all((profile_id, report_type) in reports_by_expected_key
             for report_type in ADS_STATS_REQUIRED_REPORT_TYPES)


def _are_all_reports_processed(
  *,
  profile_id: str,
  reports_by_expected_key: dict[tuple[str, str], models.AmazonAdsReport],
) -> bool:
  """Return whether all required report types for the profile are processed."""
  for report_type in ADS_STATS_REQUIRED_REPORT_TYPES:
    report = reports_by_expected_key.get((profile_id, report_type))
    if not report or not report.processed:
      return False
  return True


def _collect_expected_report_ids_for_profile(
  *,
  profile_id: str,
  reports_by_expected_key: dict[tuple[str, str], models.AmazonAdsReport],
) -> list[str]:
  """Collect report IDs in required report-type order for a profile."""
  report_ids: list[str] = []
  for report_type in ADS_STATS_REQUIRED_REPORT_TYPES:
    report = reports_by_expected_key.get((profile_id, report_type))
    if not report:
      continue
    report_ids.append(report.report_id)
  return report_ids


def _are_reports_complete(*reports: models.AmazonAdsReport) -> bool:
  """Return True when all provided reports are complete."""
  return all(report.status.upper() in _REPORT_STATUS_COMPLETED
             for report in reports)


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

  # Persist exact unzipped payload text for debugging/replay in Firestore.
  report.raw_report_text = decoded_text
  return parse_report_rows_text(report.report_name, decoded_text)


def parse_report_rows_text(
  report_name: str,
  text: str,
  *,
  enable_logging: bool = True,
) -> list[dict[str, Any]]:
  """Parse report text that may be JSON array/object or JSON-lines."""
  stripped = text.strip()
  if not stripped:
    return []

  if enable_logging:
    logger.info(f"Parsing text for report {report_name}: {stripped}")
  try:
    parsed_raw = json.loads(stripped)
    if enable_logging:
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
  kdp_price_candidates_by_market_currency_asin: dict[tuple[str, str, str],
                                                     tuple[float, ...]],
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
    market_code = _normalize_market_code(profile_country_code)
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
    kenp_pages_read = _as_int(
      campaign_row.get("kindleEditionNormalizedPagesRead14d"))
    if kenp_pages_read == 0:
      kenp_pages_read = _as_int(
        campaign_row.get("attributedKindleEditionNormalizedPagesRead14d"))
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
      market_code=market_code,
      currency_code=currency_code,
      kdp_price_candidates_by_market_currency_asin=(
        kdp_price_candidates_by_market_currency_asin),
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
        kenp_pages_read=kenp_pages_read,
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
  market_code: str,
  currency_code: str,
  kdp_price_candidates_by_market_currency_asin: dict[tuple[str, str, str],
                                                     tuple[float, ...]],
) -> list[models.AmazonProductStats]:
  """Build merged ASIN sale items by combining direct and halo sources."""
  merged_totals_by_asin: dict[str, models.AmazonProductStats] = {}
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
    allocations = _decompose_advertised_row_allocations(
      advertised_asin=asin,
      market_code=market_code,
      currency_code=currency_code,
      units_sold=direct_units,
      total_sales_usd=direct_sales,
      kdp_price_candidates_by_market_currency_asin=(
        kdp_price_candidates_by_market_currency_asin),
    )
    for allocation in allocations:
      _accumulate_asin_totals(
        merged_totals_by_asin,
        allocation.asin,
        units_sold=allocation.units_sold,
        sales_amount=allocation.total_sales_usd,
      )

  for row in purchased_by_campaign_date.get(key, []):
    asin = _required_str(row.get("purchasedAsin"))
    if not asin:
      continue
    canonical_asin = _canonical_book_variant_asin(asin)
    if not canonical_asin:
      continue
    halo_units = _as_int(row.get("unitsSoldOtherSku14d"))
    halo_sales = _convert_amount_to_usd(
      _as_float(row.get("salesOtherSku14d")),
      currency_code=currency_code,
    )
    kenp_pages_read = _as_int(row.get("kindleEditionNormalizedPagesRead14d"))
    kenp_royalties_usd = _convert_amount_to_usd(
      _as_float(row.get("kindleEditionNormalizedPagesRoyalties14d")),
      currency_code=currency_code,
    )
    _accumulate_asin_totals(
      merged_totals_by_asin,
      canonical_asin,
      units_sold=halo_units,
      sales_amount=halo_sales,
      kenp_pages_read=kenp_pages_read,
      kenp_royalties_usd=kenp_royalties_usd,
    )

  sale_items: list[models.AmazonProductStats] = []
  for asin in sorted(merged_totals_by_asin.keys()):
    sale_items.append(_build_product_stats(merged_totals_by_asin[asin]))
  return sale_items


def _extract_direct_sales_amount(advertised_row: dict[str, Any]) -> float:
  """Return same-SKU direct sales from an advertised-product row.

  Do not fall back to total sales fields (for example `sales14d`), because those
  can include cross-SKU purchases and misattribute revenue to `advertisedAsin`.
  """
  return _as_float(advertised_row.get("attributedSalesSameSku14d"))


def _extract_direct_units_sold(advertised_row: dict[str, Any]) -> int:
  """Return same-SKU direct units from an advertised-product row.

  We intentionally ignore fallback click-level totals (for example
  `unitsSoldClicks14d` / `purchases14d`) to avoid cross-SKU ASIN misattribution.
  """
  return _as_int(advertised_row.get("unitsSoldSameSku14d"))


def _load_kdp_price_candidates_by_market_currency_asin(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> dict[tuple[str, str, str], tuple[float, ...]]:
  """Build `(market, currency, asin) -> candidate per-unit USD prices`."""
  if end_date < start_date:
    return {}

  try:
    kdp_rows = firestore.list_amazon_kdp_daily_stats(
      start_date=start_date,
      end_date=end_date,
    )
  except Exception as exc:  # pylint: disable=broad-exception-caught
    logger.warn(f"Failed to load KDP price candidates: {exc}")
    return {}

  candidates: dict[tuple[str, str, str], set[float]] = {}
  for daily_stat in kdp_rows:
    for market_stats in daily_stat.market_currency_stats_by_key.values():
      _add_kdp_candidates_from_market_stats(candidates, market_stats)

    # Backward compatibility for historical docs without market/currency buckets.
    for sale_item in daily_stat.sale_items:
      units = _as_int(sale_item.units_sold)
      if units <= 0:
        continue
      canonical_asin = _safe_canonical_book_variant_asin(sale_item.asin)
      if not canonical_asin:
        continue
      key = ("ANY", _USD_CURRENCY_CODE, canonical_asin)
      _add_price_candidate(
        candidates,
        key,
        _as_float(sale_item.total_sales_usd) / units,
      )

  return {
    key: tuple(sorted(prices))
    for key, prices in candidates.items() if prices
  }


def _add_kdp_candidates_from_market_stats(
  candidates: dict[tuple[str, str, str], set[float]],
  market_stats: models.AmazonKdpMarketCurrencyStats,
) -> None:
  """Merge one KDP market/currency bucket into the price candidate map."""
  market_code = _normalize_market_code(market_stats.market)
  currency_code = _required_str(market_stats.currency_code).upper()
  if not currency_code:
    currency_code = _USD_CURRENCY_CODE

  for asin, prices in market_stats.avg_offer_price_usd_candidates_by_asin.items(
  ):
    canonical_asin = _safe_canonical_book_variant_asin(asin)
    if not canonical_asin:
      continue
    key = (market_code, currency_code, canonical_asin)
    for price in prices:
      _add_price_candidate(candidates, key, price)

  for sale_item in market_stats.sale_items:
    units = _as_int(sale_item.units_sold)
    if units <= 0:
      continue
    canonical_asin = _safe_canonical_book_variant_asin(sale_item.asin)
    if not canonical_asin:
      continue
    key = (market_code, currency_code, canonical_asin)
    _add_price_candidate(
      candidates,
      key,
      _as_float(sale_item.total_sales_usd) / units,
    )


def _add_price_candidate(
  candidates: dict[tuple[str, str, str], set[float]],
  key: tuple[str, str, str],
  price: float,
) -> None:
  """Add one positive per-unit price to the candidate map."""
  if price <= 0:
    return
  candidates.setdefault(key, set()).add(round(price, 6))


def _decompose_advertised_row_allocations(
  *,
  advertised_asin: str,
  market_code: str,
  currency_code: str,
  units_sold: int,
  total_sales_usd: float,
  kdp_price_candidates_by_market_currency_asin: dict[tuple[str, str, str],
                                                     tuple[float, ...]],
) -> list[_DecomposedSaleAllocation]:
  """Infer per-ASIN unit/sales allocations from one advertised-product row."""
  canonical_advertised_asin = _canonical_book_variant_asin(advertised_asin)
  if not canonical_advertised_asin:
    return []

  normalized_units = max(0, units_sold)
  book = book_defs.find_book(advertised_asin)
  if book is None:
    return [
      _DecomposedSaleAllocation(
        asin=canonical_advertised_asin,
        units_sold=normalized_units,
        total_sales_usd=total_sales_usd,
      )
    ]

  variants = sorted(book.variants.values(), key=lambda variant: variant.asin)
  if normalized_units <= 0:
    return [
      _DecomposedSaleAllocation(
        asin=canonical_advertised_asin,
        units_sold=0,
        total_sales_usd=total_sales_usd,
      )
    ]

  candidate_prices_by_asin: dict[str, tuple[float, ...]] = {}
  for variant in variants:
    candidate_prices_by_asin[
      variant.asin] = _resolve_candidate_prices_for_variant(
        variant=variant,
        market_code=market_code,
        currency_code=currency_code,
        kdp_price_candidates_by_market_currency_asin=(
          kdp_price_candidates_by_market_currency_asin),
      )

  best_score: tuple[float, int, int, tuple[int, ...]] | None = None
  best_units_by_index: tuple[int, ...] | None = None
  best_prices_by_index: tuple[float, ...] | None = None
  advertised_index = next(
    (index for index, variant in enumerate(variants)
     if variant.asin == canonical_advertised_asin),
    0,
  )

  for units_by_index in _enumerate_unit_allocations(normalized_units,
                                                    len(variants)):
    active_indices = [
      index for index, unit_count in enumerate(units_by_index)
      if unit_count > 0
    ]
    if not active_indices:
      continue

    candidate_prices_by_index = {
      index: candidate_prices_by_asin[variants[index].asin]
      for index in active_indices
    }
    for prices_by_index in _enumerate_price_combinations(
        candidate_prices_by_index):
      base_total_sales = sum(units_by_index[index] * prices_by_index[index]
                             for index in active_indices)
      sales_delta_abs = abs(total_sales_usd - base_total_sales)
      score = (
        sales_delta_abs,
        len(active_indices),
        -units_by_index[advertised_index],
        units_by_index,
      )
      if best_score is None or score < best_score:
        best_score = score
        best_units_by_index = units_by_index
        best_prices_by_index = tuple(
          prices_by_index.get(index, 0.0) for index in range(len(variants)))

  if best_units_by_index is None or best_prices_by_index is None:
    return [
      _DecomposedSaleAllocation(
        asin=canonical_advertised_asin,
        units_sold=normalized_units,
        total_sales_usd=total_sales_usd,
      )
    ]

  base_sales_by_index = [
    best_units_by_index[index] * best_prices_by_index[index]
    for index in range(len(variants))
  ]
  base_total_sales = sum(base_sales_by_index)
  residual_delta = total_sales_usd - base_total_sales

  weighted_indices = [
    index for index, units in enumerate(best_units_by_index) if units > 0
  ]
  weights: dict[int, float] = {}
  for index in weighted_indices:
    weights[index] = base_sales_by_index[index]
  weight_total = sum(weights.values())
  if weight_total <= 0:
    weights = {
      index: float(best_units_by_index[index])
      for index in weighted_indices
    }
    weight_total = sum(weights.values())

  adjusted_sales_by_index = list(base_sales_by_index)
  allocated_delta = 0.0
  for index in weighted_indices[:-1]:
    ratio = (weights[index] / weight_total) if weight_total > 0 else 0.0
    delta_component = residual_delta * ratio
    adjusted_sales_by_index[index] += delta_component
    allocated_delta += delta_component
  if weighted_indices:
    last_index = weighted_indices[-1]
    adjusted_sales_by_index[last_index] += residual_delta - allocated_delta

  allocations = [
    _DecomposedSaleAllocation(
      asin=variants[index].asin,
      units_sold=best_units_by_index[index],
      total_sales_usd=adjusted_sales_by_index[index],
    ) for index in range(len(variants)) if best_units_by_index[index] > 0
    or abs(adjusted_sales_by_index[index]) > 1e-9
  ]
  if allocations:
    return allocations

  return [
    _DecomposedSaleAllocation(
      asin=canonical_advertised_asin,
      units_sold=0,
      total_sales_usd=0.0,
    )
  ]


def _resolve_candidate_prices_for_variant(
  *,
  variant: book_defs.BookVariant,
  market_code: str,
  currency_code: str,
  kdp_price_candidates_by_market_currency_asin: dict[tuple[str, str, str],
                                                     tuple[float, ...]],
) -> tuple[float, ...]:
  """Return sorted candidate per-unit USD prices for one ASIN."""
  candidate_prices: set[float] = set()
  exact_key = (market_code, currency_code, variant.asin)
  candidate_prices.update(
    kdp_price_candidates_by_market_currency_asin.get(exact_key, ()))

  for (candidate_market, _candidate_currency, candidate_asin
       ), prices in kdp_price_candidates_by_market_currency_asin.items():
    if candidate_market == market_code and candidate_asin == variant.asin:
      candidate_prices.update(prices)

  candidate_prices.update(
    kdp_price_candidates_by_market_currency_asin.get(
      ("ANY", _USD_CURRENCY_CODE, variant.asin), ()))

  if variant.min_price_usd is not None:
    candidate_prices = {
      price
      for price in candidate_prices if price >= variant.min_price_usd
    }
  if variant.max_price_usd is not None:
    candidate_prices = {
      price
      for price in candidate_prices if price <= variant.max_price_usd
    }

  if not candidate_prices:
    fallback_prices: list[float] = []
    if variant.min_price_usd is not None:
      fallback_prices.append(variant.min_price_usd)
    if variant.max_price_usd is not None:
      fallback_prices.append(variant.max_price_usd)
    if (variant.min_price_usd is not None
        and variant.max_price_usd is not None):
      fallback_prices.append(
        (variant.min_price_usd + variant.max_price_usd) / 2.0)
    if fallback_prices:
      candidate_prices.update(price for price in fallback_prices if price >= 0)

  if not candidate_prices:
    return (0.0, )

  return tuple(sorted(candidate_prices))


def _enumerate_unit_allocations(total_units: int,
                                variant_count: int) -> list[tuple[int, ...]]:
  """Return all non-negative integer splits that sum to `total_units`."""
  if variant_count <= 0:
    return []

  output: list[tuple[int, ...]] = []

  def _recurse(
    index: int,
    units_remaining: int,
    current: list[int],
  ) -> None:
    if index == variant_count - 1:
      output.append(tuple(current + [units_remaining]))
      return
    for units_here in range(units_remaining + 1):
      _recurse(index + 1, units_remaining - units_here, current + [units_here])

  _recurse(0, total_units, [])
  return output


def _enumerate_price_combinations(
  candidate_prices_by_index: dict[int, tuple[float, ...]],
) -> list[dict[int, float]]:
  """Return cartesian combinations of candidate prices by variant index."""
  indices = sorted(candidate_prices_by_index.keys())
  if not indices:
    return [{}]

  output: list[dict[int, float]] = []

  def _recurse(position: int, current: dict[int, float]) -> None:
    if position >= len(indices):
      output.append(dict(current))
      return
    index = indices[position]
    for price in candidate_prices_by_index.get(index, (0.0, )):
      current[index] = price
      _recurse(position + 1, current)

  _recurse(0, {})
  return output


def _accumulate_asin_totals(
  merged_totals_by_asin: dict[str, models.AmazonProductStats],
  asin: str,
  *,
  units_sold: int = 0,
  sales_amount: float = 0.0,
  kenp_pages_read: int = 0,
  kenp_royalties_usd: float = 0.0,
) -> None:
  """Add sales totals into an ASIN accumulator, merging repeated rows."""
  existing = merged_totals_by_asin.setdefault(
    asin,
    models.AmazonProductStats(asin=asin),
  )
  existing.units_sold += units_sold
  existing.total_sales_usd += sales_amount
  existing.kenp_pages_read += kenp_pages_read
  existing.kenp_royalties_usd += kenp_royalties_usd


def _build_product_stats(
  product_totals: models.AmazonProductStats, ) -> models.AmazonProductStats:
  """Build a normalized `ProductStats` object from merged ASIN totals."""
  asin = product_totals.asin
  book_variant = book_defs.BOOK_VARIANTS_BY_ASIN.get(asin)
  if not book_variant:
    raise AmazonAdsError(f"Unknown ASIN: {asin}")

  total_profit_usd = (product_totals.total_sales_usd *
                      book_variant.royalty_rate) - (product_totals.units_sold *
                                                    book_variant.print_cost)

  return models.AmazonProductStats(
    asin=asin,
    units_sold=product_totals.units_sold,
    kenp_pages_read=product_totals.kenp_pages_read,
    total_sales_usd=product_totals.total_sales_usd,
    total_profit_usd=total_profit_usd,
    kenp_royalties_usd=product_totals.kenp_royalties_usd,
  )


def _safe_canonical_book_variant_asin(identifier: str) -> str | None:
  """Best-effort canonical ASIN lookup without raising on unknown IDs."""
  raw_identifier = (identifier or "").strip()
  if not raw_identifier:
    return None
  book_variant = book_defs.find_book_variant(raw_identifier)
  if book_variant is None:
    return None
  return book_variant.asin


def _canonical_book_variant_asin(identifier: str) -> str | None:
  """Normalize an ASIN or ISBN identifier to the canonical book-variant ASIN."""
  raw_identifier = (identifier or "").strip()
  if not raw_identifier:
    return None
  book_variant = book_defs.find_book_variant(raw_identifier)
  if book_variant is None:
    raise AmazonAdsError(f"Unknown ASIN: {raw_identifier}")
  return book_variant.asin


def _normalize_market_code(country_code: str) -> str:
  """Normalize profile/report country codes to market keys used by KDP stats."""
  normalized = country_code.strip().upper()
  return _COUNTRY_CODE_TO_MARKET_CODE.get(normalized, normalized)


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
