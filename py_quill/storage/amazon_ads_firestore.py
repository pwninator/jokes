"""Firestore helpers for Amazon Ads campaign and insights stats."""

from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import cast

from google.cloud.firestore import DocumentSnapshot, FieldFilter, Query
from models import amazon_ads_models
from services import firestore

AMAZON_ADS_SEARCH_TERM_DAILY_STATS_COLLECTION = (
  "amazon_ads_search_term_daily_stats")
AMAZON_ADS_PLACEMENT_DAILY_STATS_COLLECTION = "amazon_ads_placement_daily_stats"
AMAZON_CAMPAIGNS_COLLECTION = "amazon_campaigns"


def upsert_amazon_ads_search_term_daily_stats(
  stats: list[amazon_ads_models.AmazonAdsSearchTermDailyStat],
) -> list[amazon_ads_models.AmazonAdsSearchTermDailyStat]:
  """Batch upsert search-term daily stats keyed by deterministic identity."""
  if not stats:
    return []

  db_client = firestore.db()
  batch = db_client.batch()
  collection_ref = db_client.collection(
    AMAZON_ADS_SEARCH_TERM_DAILY_STATS_COLLECTION)
  for stat in stats:
    key = stat.ensure_key()
    payload = stat.to_dict(include_key=False)
    batch.set(
      collection_ref.document(key),
      payload,
      merge=True,
    )
  batch.commit()  # pyright: ignore[reportUnusedCallResult]
  return stats


def upsert_amazon_ads_placement_daily_stats(
  stats: list[amazon_ads_models.AmazonAdsPlacementDailyStat],
) -> list[amazon_ads_models.AmazonAdsPlacementDailyStat]:
  """Batch upsert placement daily stats keyed by deterministic identity."""
  if not stats:
    return []

  db_client = firestore.db()
  batch = db_client.batch()
  collection_ref = db_client.collection(
    AMAZON_ADS_PLACEMENT_DAILY_STATS_COLLECTION)
  for stat in stats:
    key = stat.ensure_key()
    payload = stat.to_dict(include_key=False)
    batch.set(
      collection_ref.document(key),
      payload,
      merge=True,
    )
  batch.commit()  # pyright: ignore[reportUnusedCallResult]
  return stats


def upsert_amazon_campaigns(
  campaigns: list[amazon_ads_models.AmazonCampaign],
) -> list[amazon_ads_models.AmazonCampaign]:
  """Batch upsert latest-known campaign metadata keyed by campaign identity."""
  if not campaigns:
    return []

  db_client = firestore.db()
  batch = db_client.batch()
  collection_ref = db_client.collection(AMAZON_CAMPAIGNS_COLLECTION)
  for campaign in campaigns:
    key = campaign.ensure_key()
    payload = campaign.to_dict(include_key=False)
    batch.set(
      collection_ref.document(key),
      payload,
      merge=True,
    )
  batch.commit()  # pyright: ignore[reportUnusedCallResult]
  return campaigns


def list_amazon_ads_search_term_daily_stats(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> list[amazon_ads_models.AmazonAdsSearchTermDailyStat]:
  """List search-term daily stats with Firestore-side date filtering."""
  if end_date < start_date:
    raise ValueError("end_date must be on or after start_date")

  query = firestore.db().collection(
    AMAZON_ADS_SEARCH_TERM_DAILY_STATS_COLLECTION).where(filter=FieldFilter(
      "date", ">=", start_date.isoformat()), ).where(filter=FieldFilter(
        "date", "<=", end_date.isoformat()), ).order_by(
          "date",
          direction=Query.ASCENDING,
        )
  docs = cast(Iterable[DocumentSnapshot], query.stream())
  result: list[amazon_ads_models.AmazonAdsSearchTermDailyStat] = []
  for doc in docs:
    if not doc.exists:
      continue
    data = doc.to_dict()
    if data is None:
      continue
    result.append(
      amazon_ads_models.AmazonAdsSearchTermDailyStat.from_firestore_dict(
        data,
        key=cast(str, doc.id),
      ))
  return result


def list_amazon_ads_placement_daily_stats(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> list[amazon_ads_models.AmazonAdsPlacementDailyStat]:
  """List placement daily stats with Firestore-side date filtering."""
  if end_date < start_date:
    raise ValueError("end_date must be on or after start_date")

  query = firestore.db().collection(
    AMAZON_ADS_PLACEMENT_DAILY_STATS_COLLECTION).where(filter=FieldFilter(
      "date", ">=", start_date.isoformat()), ).where(filter=FieldFilter(
        "date", "<=", end_date.isoformat()), ).order_by(
          "date",
          direction=Query.ASCENDING,
        )
  docs = cast(Iterable[DocumentSnapshot], query.stream())
  result: list[amazon_ads_models.AmazonAdsPlacementDailyStat] = []
  for doc in docs:
    if not doc.exists:
      continue
    data = doc.to_dict()
    if data is None:
      continue
    result.append(
      amazon_ads_models.AmazonAdsPlacementDailyStat.from_firestore_dict(
        data,
        key=cast(str, doc.id),
      ))
  return result


def list_amazon_campaigns() -> list[amazon_ads_models.AmazonCampaign]:
  """List latest-known Amazon campaign metadata rows."""
  docs = cast(
    Iterable[DocumentSnapshot],
    firestore.db().collection(AMAZON_CAMPAIGNS_COLLECTION).stream(),
  )
  result: list[amazon_ads_models.AmazonCampaign] = []
  for doc in docs:
    if not doc.exists:
      continue
    data = doc.to_dict()
    if data is None:
      continue
    result.append(
      amazon_ads_models.AmazonCampaign.from_firestore_dict(
        data,
        key=cast(str, doc.id),
      ))
  return sorted(
    result,
    key=lambda campaign: (
      campaign.profile_id,
      campaign.campaign_name,
      campaign.campaign_id,
    ),
  )
