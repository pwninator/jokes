"""Firestore helpers for Amazon Ads search-term stats."""

from __future__ import annotations

import datetime

from google.cloud.firestore import FieldFilter, Query
from models import amazon_ads_models
from services import firestore

AMAZON_ADS_SEARCH_TERM_DAILY_STATS_COLLECTION = (
  "amazon_ads_search_term_daily_stats")


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
  _ = batch.commit()
  return stats


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
  docs = query.stream()
  return [
    amazon_ads_models.AmazonAdsSearchTermDailyStat.from_firestore_dict(
      doc.to_dict(),
      key=doc.id,
    ) for doc in docs if doc.exists and doc.to_dict() is not None
  ]
