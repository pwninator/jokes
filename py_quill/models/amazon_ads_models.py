"""Amazon Ads model classes used by storage and admin reporting."""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
from dataclasses import dataclass
from typing import Any


def build_search_term_stat_key(
  *,
  date: datetime.date,
  profile_id: str,
  campaign_id: str,
  ad_group_id: str,
  search_term: str,
  keyword_type: str,
  match_type: str,
  keyword_id: str,
  keyword: str,
  targeting: str,
) -> str:
  """Build a deterministic Firestore doc id for one search-term daily row."""
  identity = "|".join([
    date.isoformat(),
    profile_id.strip(),
    campaign_id.strip(),
    ad_group_id.strip(),
    search_term.strip().lower(),
    keyword_type.strip().upper(),
    match_type.strip().upper(),
    keyword_id.strip(),
    keyword.strip().lower(),
    targeting.strip().lower(),
  ])
  digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:24]
  return f"{date.isoformat()}__{profile_id.strip()}__{digest}"


@dataclass(kw_only=True)
class AmazonAdsSearchTermDailyStat:
  """One normalized sponsored-products search-term row for one day."""

  key: str | None = None
  date: datetime.date
  profile_id: str
  profile_country: str
  region: str
  campaign_id: str
  campaign_name: str
  ad_group_id: str
  ad_group_name: str
  search_term: str
  keyword_id: str
  keyword: str
  targeting: str
  keyword_type: str
  match_type: str
  ad_keyword_status: str
  impressions: int = 0
  clicks: int = 0
  cost_usd: float = 0.0
  sales14d_usd: float = 0.0
  purchases14d: int = 0
  units_sold_clicks14d: int = 0
  kenp_pages_read14d: int = 0
  kenp_royalties14d_usd: float = 0.0
  currency_code: str = "USD"
  source_report_id: str = ""
  source_report_name: str = ""
  created_at: datetime.datetime | None = None
  updated_at: datetime.datetime | None = None

  def ensure_key(self) -> str:
    """Assign and return a deterministic Firestore document key."""
    if self.key:
      return self.key
    self.key = build_search_term_stat_key(
      date=self.date,
      profile_id=self.profile_id,
      campaign_id=self.campaign_id,
      ad_group_id=self.ad_group_id,
      search_term=self.search_term,
      keyword_type=self.keyword_type,
      match_type=self.match_type,
      keyword_id=self.keyword_id,
      keyword=self.keyword,
      targeting=self.targeting,
    )
    return self.key

  def to_dict(self, include_key: bool = False) -> dict[str, Any]:
    """Serialize for Firestore storage."""
    data: dict[str, Any] = {
      "date": self.date.isoformat(),
      "profile_id": self.profile_id,
      "profile_country": self.profile_country,
      "region": self.region,
      "campaign_id": self.campaign_id,
      "campaign_name": self.campaign_name,
      "ad_group_id": self.ad_group_id,
      "ad_group_name": self.ad_group_name,
      "search_term": self.search_term,
      "keyword_id": self.keyword_id,
      "keyword": self.keyword,
      "targeting": self.targeting,
      "keyword_type": self.keyword_type,
      "match_type": self.match_type,
      "ad_keyword_status": self.ad_keyword_status,
      "impressions": self.impressions,
      "clicks": self.clicks,
      "cost_usd": self.cost_usd,
      "sales14d_usd": self.sales14d_usd,
      "purchases14d": self.purchases14d,
      "units_sold_clicks14d": self.units_sold_clicks14d,
      "kenp_pages_read14d": self.kenp_pages_read14d,
      "kenp_royalties14d_usd": self.kenp_royalties14d_usd,
      "currency_code": self.currency_code,
      "source_report_id": self.source_report_id,
      "source_report_name": self.source_report_name,
      "created_at": self.created_at,
      "updated_at": self.updated_at,
    }
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    *,
    key: str | None = None,
  ) -> AmazonAdsSearchTermDailyStat:
    """Deserialize from snake_case dictionaries."""
    if not data:
      data = {}
    else:
      data = dict(data)

    profile_id = _as_str(data.get("profile_id"))
    campaign_id = _as_str(data.get("campaign_id"))
    ad_group_id = _as_str(data.get("ad_group_id"))
    search_term = _as_str(data.get("search_term"))
    keyword_type = _as_str(data.get("keyword_type"))
    if not profile_id:
      raise ValueError("AmazonAdsSearchTermDailyStat.profile_id is required")
    if not campaign_id:
      raise ValueError("AmazonAdsSearchTermDailyStat.campaign_id is required")
    if not ad_group_id:
      raise ValueError("AmazonAdsSearchTermDailyStat.ad_group_id is required")
    if not search_term:
      raise ValueError("AmazonAdsSearchTermDailyStat.search_term is required")
    if not keyword_type:
      raise ValueError("AmazonAdsSearchTermDailyStat.keyword_type is required")

    stat = cls(
      key=key,
      date=_parse_date(
        data.get("date"),
        field_name="AmazonAdsSearchTermDailyStat.date",
      ),
      profile_id=profile_id,
      profile_country=_as_str(data.get("profile_country")),
      region=_as_str(data.get("region")),
      campaign_id=campaign_id,
      campaign_name=_as_str(data.get("campaign_name")),
      ad_group_id=ad_group_id,
      ad_group_name=_as_str(data.get("ad_group_name")),
      search_term=search_term,
      keyword_id=_as_str(data.get("keyword_id")),
      keyword=_as_str(data.get("keyword")),
      targeting=_as_str(data.get("targeting")),
      keyword_type=keyword_type,
      match_type=_as_str(data.get("match_type")),
      ad_keyword_status=_as_str(data.get("ad_keyword_status")),
      impressions=_as_int(data.get("impressions")),
      clicks=_as_int(data.get("clicks")),
      cost_usd=_as_float(data.get("cost_usd")),
      sales14d_usd=_as_float(data.get("sales14d_usd")),
      purchases14d=_as_int(data.get("purchases14d")),
      units_sold_clicks14d=_as_int(data.get("units_sold_clicks14d")),
      kenp_pages_read14d=_as_int(data.get("kenp_pages_read14d")),
      kenp_royalties14d_usd=_as_float(data.get("kenp_royalties14d_usd")),
      currency_code=_as_str(data.get("currency_code")) or "USD",
      source_report_id=_as_str(data.get("source_report_id")),
      source_report_name=_as_str(data.get("source_report_name")),
      created_at=_parse_optional_datetime(data.get("created_at")),
      updated_at=_parse_optional_datetime(data.get("updated_at")),
    )
    _ = stat.ensure_key()
    return stat

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    *,
    key: str,
  ) -> AmazonAdsSearchTermDailyStat:
    """Deserialize from Firestore dictionaries."""
    return cls.from_dict(data, key=key)


def to_serializable_dicts(
  stats: list[AmazonAdsSearchTermDailyStat], ) -> list[dict[str, Any]]:
  """Serialize a list of stats, always including key."""
  return [dataclasses.asdict(stat) for stat in stats]


def _as_int(value: Any) -> int:
  """Best-effort integer conversion with safe fallback to zero."""
  if value is None:
    return 0
  if isinstance(value, bool):
    return int(value)
  if isinstance(value, int):
    return value
  if isinstance(value, float):
    return int(value)
  try:
    return int(str(value).strip())
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


def _as_str(value: Any) -> str:
  """Best-effort string conversion with whitespace trimming."""
  if value is None:
    return ""
  return str(value).strip()


def _parse_date(value: Any, *, field_name: str) -> datetime.date:
  """Parse a required date value from Firestore or API payloads."""
  if isinstance(value, datetime.datetime):
    return value.date()
  if isinstance(value, datetime.date):
    return value
  if isinstance(value, str):
    stripped = value.strip()
    if stripped:
      return datetime.date.fromisoformat(stripped)
  raise ValueError(f"{field_name} is required")


def _parse_optional_datetime(value: Any) -> datetime.datetime | None:
  """Parse optional datetimes from Firestore payloads."""
  if value is None:
    return None
  if isinstance(value, datetime.datetime):
    if value.tzinfo is None:
      return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)
  if isinstance(value, str):
    stripped = value.strip()
    if not stripped:
      return None
    normalized = stripped[:-1] + "+00:00" if stripped.endswith(
      "Z") else stripped
    parsed = datetime.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
      return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)
  raise ValueError("Invalid datetime value")
