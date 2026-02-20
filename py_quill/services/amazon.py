"""Amazon Ads API helpers for daily campaign profitability statistics."""

from __future__ import annotations

import dataclasses
import datetime
import gzip
import json
from dataclasses import dataclass
from typing import Any, cast

import requests
from common import config, models
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

# Temporary static profit margins used during report merge.
_ASIN_PROFIT_MARGINS_USD: dict[str, float] = {
  "B09XYZ": 4.50,
}


class AmazonAdsError(Exception):
  """Raised when an Amazon Ads request or report operation fails."""


AmazonAdsReport = models.AmazonAdsReport
AmazonAdsDailyCampaignStats = models.AmazonAdsDailyCampaignStats
AmazonAdsProductStats = models.AmazonAdsProductStats


@dataclass(frozen=True, kw_only=True)
class AmazonAdsProfile:
  """Amazon Ads profile identity used for profile-scoped API calls."""

  profile_id: str
  region: str
  api_base: str
  country_code: str


@dataclass(frozen=True, kw_only=True)
class ReportPair:
  """Pair of report objects required for daily campaign stat computation."""

  campaigns_report: models.AmazonAdsReport
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
  """Kick off the two DAILY reports needed for campaign profit stats."""
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
  purchased_products_report = firestore.upsert_amazon_ads_report(
    purchased_products_report)

  return ReportPair(
    campaigns_report=campaigns_report,
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


def get_daily_campaign_stats_from_report_ids(
  *,
  profile_id: str,
  campaigns_report_id: str,
  purchased_products_report_id: str,
  region: str = "na",
) -> list[models.AmazonAdsDailyCampaignStats]:
  """Fetch, merge, and return daily campaign stats from two completed reports."""
  access_token = _get_access_token()
  api_base = _resolve_region_api_base(region)

  campaigns_status = _fetch_report(
    api_base=api_base,
    access_token=access_token,
    profile_id=profile_id,
    report_id=campaigns_report_id,
  )
  purchased_products_status = _fetch_report(
    api_base=api_base,
    access_token=access_token,
    profile_id=profile_id,
    report_id=purchased_products_report_id,
  )
  _raise_if_report_not_completed(campaigns_status)
  _raise_if_report_not_completed(purchased_products_status)

  campaign_rows = _download_report_rows(campaigns_status)
  product_rows = _download_report_rows(purchased_products_status)
  return _merge_report_rows(campaign_rows=campaign_rows,
                            product_rows=product_rows)


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
      "adProduct":
      "SPONSORED_PRODUCTS",
      "groupBy": ["campaign"],
      "columns": [
        "campaignId",
        "campaignName",
        "date",
        "cost",
        "clicks",
        "impressions",
        "kindleEditionNormalizedPagesRoyalties14d",
      ],
      "reportTypeId":
      "spCampaigns",
      "timeUnit":
      _DAILY_TIME_UNIT,
      "format":
      _GZIP_JSON_FORMAT,
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
      "adProduct":
      "SPONSORED_PRODUCTS",
      "groupBy": ["asin"],
      "columns": [
        "campaignId",
        "date",
        "purchasedAsin",
        "sales14d",
        "purchases14d",
      ],
      "reportTypeId":
      "spPurchasedProduct",
      "timeUnit":
      _DAILY_TIME_UNIT,
      "format":
      _GZIP_JSON_FORMAT,
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


def _download_report_rows(
  status: models.AmazonAdsReport, ) -> list[dict[str, Any]]:
  """Download and decompress a completed report into raw row dictionaries."""
  if not status.url:
    raise AmazonAdsError(
      f"Report {status.report_id} is completed but missing download URL")

  response = requests.get(status.url, timeout=_REQUEST_TIMEOUT_SEC)
  response.raise_for_status()
  compressed_data = response.content

  try:
    decoded_text = gzip.decompress(compressed_data).decode("utf-8")
  except OSError as exc:
    raise AmazonAdsError(
      f"Failed to decompress report {status.report_id}: {exc}") from exc

  return _parse_report_rows_text(decoded_text)


def _parse_report_rows_text(text: str) -> list[dict[str, Any]]:
  """Parse report text that may be JSON array/object or JSON-lines."""
  stripped = text.strip()
  if not stripped:
    return []

  try:
    parsed_raw = json.loads(stripped)
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
  product_rows: list[dict[str, Any]],
) -> list[models.AmazonAdsDailyCampaignStats]:
  """Merge campaign and purchased-product rows into daily campaign stats."""
  products_by_campaign_date: dict[tuple[str, datetime.date],
                                  list[dict[str, Any]]] = {}
  for row in product_rows:
    campaign_id = _required_str(row.get("campaignId"))
    date_value = _parse_report_date(row.get("date"))
    if not campaign_id or date_value is None:
      continue
    key = (campaign_id, date_value)
    products_by_campaign_date.setdefault(key, []).append(row)

  output: list[models.AmazonAdsDailyCampaignStats] = []
  for campaign_row in campaign_rows:
    campaign_id = _required_str(campaign_row.get("campaignId"))
    date_value = _parse_report_date(campaign_row.get("date"))
    if not campaign_id or date_value is None:
      continue

    campaign_name = _required_str(campaign_row.get("campaignName"))
    if not campaign_name:
      campaign_name = _required_str(campaign_row.get("name"))

    spend = _as_float(campaign_row.get("cost"))
    impressions = _as_int(campaign_row.get("impressions"))
    clicks = _as_int(campaign_row.get("clicks"))
    kenp_royalties = _as_float(
      campaign_row.get("kindleEditionNormalizedPagesRoyalties14d"))
    if kenp_royalties == 0.0:
      kenp_royalties = _as_float(
        campaign_row.get("attributedKindleEditionNormalizedPagesRoyalties14d"))

    sale_items: list[models.AmazonAdsProductStats] = []
    total_attributed_sales = 0.0
    total_units_sold = 0
    product_profit_total = 0.0

    matching_products = products_by_campaign_date.get(
      (campaign_id, date_value), [])
    for product_row in matching_products:
      sale_item = _build_product_stats(product_row)
      sale_items.append(sale_item)
      total_attributed_sales += sale_item.sales_amount
      total_units_sold += sale_item.units_sold
      product_profit_total += sale_item.total_profit

    gross_profit = product_profit_total + kenp_royalties
    output.append(
      models.AmazonAdsDailyCampaignStats(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        date=date_value,
        spend=spend,
        impressions=impressions,
        clicks=clicks,
        kenp_royalties=kenp_royalties,
        total_attributed_sales=total_attributed_sales,
        total_units_sold=total_units_sold,
        gross_profit=gross_profit,
        sale_items=sorted(sale_items, key=lambda item: item.asin),
      ))

  return sorted(output, key=lambda stat: (stat.date, stat.campaign_id))


def _build_product_stats(
  product_row: dict[str, Any], ) -> models.AmazonAdsProductStats:
  """Convert one purchased-product report row into `ProductStats`."""
  asin = _required_str(product_row.get("purchasedAsin"))
  units_sold = _as_int(product_row.get("purchases14d"))
  if units_sold == 0:
    units_sold = _as_int(product_row.get("attributedUnitsOrdered14d"))

  sales_amount = _as_float(product_row.get("sales14d"))
  if sales_amount == 0.0:
    sales_amount = _as_float(product_row.get("attributedSales14d"))
  profit_margin = _ASIN_PROFIT_MARGINS_USD.get(asin, 0.0)
  total_profit = units_sold * profit_margin

  return models.AmazonAdsProductStats(
    asin=asin,
    units_sold=units_sold,
    sales_amount=sales_amount,
    total_profit=total_profit,
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
    "Amazon Ads request",
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
