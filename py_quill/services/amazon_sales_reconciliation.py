"""Reconcile KDP ship-date sales against ads purchase-date attribution."""

from __future__ import annotations

import datetime
from collections import defaultdict, deque

from common import models
from firebase_functions import logger
from services import firestore

_MATCH_LOOKBACK_DAYS = 14


def reconcile_daily_sales(
  *,
  earliest_changed_date: datetime.date,
  run_time_utc: datetime.datetime | None = None,
) -> dict[str, object]:
  """Recompute reconciled daily sales from a rolling 14-day lookback start."""
  if run_time_utc is None:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
  elif run_time_utc.tzinfo is None:
    run_time_utc = run_time_utc.replace(tzinfo=datetime.timezone.utc)
  else:
    run_time_utc = run_time_utc.astimezone(datetime.timezone.utc)

  ads_bounds = _get_collection_date_bounds(
    firestore.AMAZON_ADS_DAILY_STATS_COLLECTION)
  kdp_bounds = _get_collection_date_bounds(
    firestore.AMAZON_KDP_DAILY_STATS_COLLECTION)
  if ads_bounds is None or kdp_bounds is None:
    logger.info(
      "Skipping sales reconciliation: missing ads or KDP source data.")
    skipped_stats: dict[str, object] = {
      "reconciled_days": 0,
      "skipped": True,
      "reason": "missing_source_data",
    }
    return skipped_stats

  ads_min_date, ads_max_date = ads_bounds
  kdp_min_date, kdp_max_date = kdp_bounds
  earliest_raw_date = min(ads_min_date, kdp_min_date)
  latest_common_source_date = min(ads_max_date, kdp_max_date)

  recompute_start = earliest_changed_date - datetime.timedelta(
    days=_MATCH_LOOKBACK_DAYS)
  recompute_start = max(recompute_start, earliest_raw_date)

  seed_date = recompute_start - datetime.timedelta(days=1)
  seeded_lots = _load_seed_lots(seed_date)
  seeded_from_previous_day = seeded_lots is not None

  if seeded_lots is None:
    start_date = earliest_raw_date
    lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]] = {}
  else:
    start_date = recompute_start
    lots_by_asin = seeded_lots

  end_date = max(ads_max_date, kdp_max_date)
  ads_rows = firestore.list_amazon_ads_daily_stats(
    start_date=start_date,
    end_date=end_date,
  )
  kdp_rows = firestore.list_amazon_kdp_daily_stats(
    start_date=start_date,
    end_date=end_date,
  )

  ads_by_date = {row.date: row for row in ads_rows}
  kdp_by_date = {row.date: row for row in kdp_rows}

  reconciled_docs: list[models.AmazonSalesReconciledDailyStats] = []
  current_date = start_date
  while current_date <= end_date:
    _prune_expired_lots(lots_by_asin, current_date)
    _append_ads_lots_for_day(
      current_date=current_date,
      ads_stat=ads_by_date.get(current_date),
      lots_by_asin=lots_by_asin,
    )
    reconciled_docs.append(
      _build_daily_reconciled_doc(
        current_date=current_date,
        kdp_stat=kdp_by_date.get(current_date),
        lots_by_asin=lots_by_asin,
        latest_common_source_date=latest_common_source_date,
        run_time_utc=run_time_utc,
      ))
    current_date += datetime.timedelta(days=1)

  _upsert_reconciled_docs(reconciled_docs)

  settled_through_date = latest_common_source_date - datetime.timedelta(
    days=_MATCH_LOOKBACK_DAYS)
  stats: dict[str, object] = {
    "reconciled_days": len(reconciled_docs),
    "reconciled_start_date": start_date.isoformat(),
    "reconciled_end_date": end_date.isoformat(),
    "earliest_changed_date": earliest_changed_date.isoformat(),
    "seeded_from_previous_day": seeded_from_previous_day,
    "settled_through_date": settled_through_date.isoformat(),
  }
  logger.info(f"Sales reconciliation completed: {stats}")
  return stats


def _get_collection_date_bounds(
  collection_name: str, ) -> tuple[datetime.date, datetime.date] | None:
  """Return `(min_date, max_date)` for a date-keyed Firestore collection."""
  return firestore.get_amazon_daily_stats_date_bounds(collection_name)


def _load_seed_lots(
  seed_date: datetime.date,
) -> dict[str, deque[models.AmazonSalesReconciledAdsLot]] | None:
  """Load carry-forward unmatched ads lots from the previous reconciled day."""
  daily_stat = firestore.get_amazon_sales_reconciled_daily_stat(seed_date)
  if daily_stat is None:
    return None
  output: dict[str, deque[models.AmazonSalesReconciledAdsLot]] = {}
  for asin, lots in daily_stat.zzz_ending_unmatched_ads_lots_by_asin.items():
    queue = deque([
      models.AmazonSalesReconciledAdsLot(
        purchase_date=lot.purchase_date,
        units_remaining=lot.units_remaining,
      ) for lot in lots if lot.units_remaining > 0
    ])
    if queue:
      output[asin] = queue
  return output


def _prune_expired_lots(
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
  current_date: datetime.date,
) -> None:
  """Drop ads lots that are older than the 14-day matching window."""
  earliest_allowed_date = current_date - datetime.timedelta(
    days=_MATCH_LOOKBACK_DAYS)
  empty_asins: list[str] = []
  for asin, queue in lots_by_asin.items():
    while queue and queue[0].purchase_date < earliest_allowed_date:
      _ = queue.popleft()
    while queue and queue[0].units_remaining <= 0:
      _ = queue.popleft()
    if not queue:
      empty_asins.append(asin)
  for asin in empty_asins:
    del lots_by_asin[asin]


def _append_ads_lots_for_day(
  *,
  current_date: datetime.date,
  ads_stat: models.AmazonAdsDailyStats | None,
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
) -> None:
  """Append today's ads-attributed units as unmatched lots by ASIN."""
  if ads_stat is None:
    return

  units_by_asin: dict[str, int] = defaultdict(int)
  for campaign_stat in ads_stat.campaigns_by_id.values():
    for sale_item in campaign_stat.sale_items:
      asin = sale_item.asin.strip()
      if not asin:
        continue
      units = max(0, int(sale_item.units_sold))
      if units <= 0:
        continue
      units_by_asin[asin] += units

  for asin, units in units_by_asin.items():
    lots_by_asin.setdefault(asin, deque()).append(
      models.AmazonSalesReconciledAdsLot(
        purchase_date=current_date,
        units_remaining=units,
      ))


def _build_daily_reconciled_doc(
  *,
  current_date: datetime.date,
  kdp_stat: models.AmazonKdpDailyStats | None,
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
  latest_common_source_date: datetime.date,
  run_time_utc: datetime.datetime,
) -> models.AmazonSalesReconciledDailyStats:
  """Build one reconciled daily document and advance unmatched lot state."""
  by_asin: dict[str, models.AmazonSalesReconciledAsinStats] = {}

  kdp_units_total = 0
  ads_matched_units_total = 0
  organic_units_total = 0

  kdp_sales_usd_total = 0.0
  ads_matched_sales_usd_est = 0.0
  organic_sales_usd_est = 0.0

  kdp_royalty_usd_total = 0.0
  ads_matched_royalty_usd_est = 0.0
  organic_royalty_usd_est = 0.0

  kdp_print_cost_usd_total = 0.0
  ads_matched_print_cost_usd_est = 0.0
  organic_print_cost_usd_est = 0.0

  if kdp_stat is not None:
    for sale_item in kdp_stat.sale_items:
      asin = sale_item.asin.strip()
      if not asin:
        continue

      kdp_units = int(sale_item.units_sold)
      matched_units = _match_units(
        asin=asin,
        kdp_units=kdp_units,
        lots_by_asin=lots_by_asin,
      )
      organic_units = kdp_units - matched_units

      sales_usd = float(sale_item.total_sales_usd)
      royalty_usd = _resolve_kdp_royalty_usd(sale_item)
      print_cost_usd = float(sale_item.total_print_cost_usd or 0.0)

      if kdp_units > 0:
        matched_ratio = matched_units / kdp_units
      else:
        matched_ratio = 0.0

      ads_sales_usd = sales_usd * matched_ratio
      ads_royalty_usd = royalty_usd * matched_ratio
      ads_print_cost_usd = print_cost_usd * matched_ratio

      organic_sales_usd = sales_usd - ads_sales_usd
      organic_royalty_usd = royalty_usd - ads_royalty_usd
      organic_print_cost_usd = print_cost_usd - ads_print_cost_usd

      by_asin_entry = by_asin.setdefault(
        asin,
        models.AmazonSalesReconciledAsinStats(asin=asin),
      )
      by_asin_entry.kdp_units += kdp_units
      by_asin_entry.ads_matched_units += matched_units
      by_asin_entry.organic_units += organic_units
      by_asin_entry.kdp_sales_usd += sales_usd
      by_asin_entry.ads_matched_sales_usd_est += ads_sales_usd
      by_asin_entry.organic_sales_usd_est += organic_sales_usd
      by_asin_entry.kdp_royalty_usd += royalty_usd
      by_asin_entry.ads_matched_royalty_usd_est += ads_royalty_usd
      by_asin_entry.organic_royalty_usd_est += organic_royalty_usd
      by_asin_entry.kdp_print_cost_usd += print_cost_usd
      by_asin_entry.ads_matched_print_cost_usd_est += ads_print_cost_usd
      by_asin_entry.organic_print_cost_usd_est += organic_print_cost_usd

      kdp_units_total += kdp_units
      ads_matched_units_total += matched_units
      organic_units_total += organic_units
      kdp_sales_usd_total += sales_usd
      ads_matched_sales_usd_est += ads_sales_usd
      organic_sales_usd_est += organic_sales_usd
      kdp_royalty_usd_total += royalty_usd
      ads_matched_royalty_usd_est += ads_royalty_usd
      organic_royalty_usd_est += organic_royalty_usd
      kdp_print_cost_usd_total += print_cost_usd
      ads_matched_print_cost_usd_est += ads_print_cost_usd
      organic_print_cost_usd_est += organic_print_cost_usd

  _round_by_asin_fields(by_asin)

  settled_through_date = latest_common_source_date - datetime.timedelta(
    days=_MATCH_LOOKBACK_DAYS)
  is_settled = current_date <= settled_through_date

  return models.AmazonSalesReconciledDailyStats(
    date=current_date,
    is_settled=is_settled,
    reconciled_at=run_time_utc,
    kdp_units_total=kdp_units_total,
    ads_matched_units_total=ads_matched_units_total,
    organic_units_total=organic_units_total,
    kdp_sales_usd_total=round(kdp_sales_usd_total, 6),
    ads_matched_sales_usd_est=round(ads_matched_sales_usd_est, 6),
    organic_sales_usd_est=round(organic_sales_usd_est, 6),
    kdp_royalty_usd_total=round(kdp_royalty_usd_total, 6),
    ads_matched_royalty_usd_est=round(ads_matched_royalty_usd_est, 6),
    organic_royalty_usd_est=round(organic_royalty_usd_est, 6),
    kdp_print_cost_usd_total=round(kdp_print_cost_usd_total, 6),
    ads_matched_print_cost_usd_est=round(ads_matched_print_cost_usd_est, 6),
    organic_print_cost_usd_est=round(organic_print_cost_usd_est, 6),
    by_asin=by_asin,
    zzz_ending_unmatched_ads_lots_by_asin=_snapshot_lots(lots_by_asin),
  )


def _round_by_asin_fields(
  by_asin: dict[str, models.AmazonSalesReconciledAsinStats], ) -> None:
  """Round money fields in-place for deterministic Firestore payloads."""
  for asin_data in by_asin.values():
    asin_data.kdp_sales_usd = round(asin_data.kdp_sales_usd, 6)
    asin_data.ads_matched_sales_usd_est = round(
      asin_data.ads_matched_sales_usd_est, 6)
    asin_data.organic_sales_usd_est = round(asin_data.organic_sales_usd_est, 6)
    asin_data.kdp_royalty_usd = round(asin_data.kdp_royalty_usd, 6)
    asin_data.ads_matched_royalty_usd_est = round(
      asin_data.ads_matched_royalty_usd_est, 6)
    asin_data.organic_royalty_usd_est = round(
      asin_data.organic_royalty_usd_est, 6)
    asin_data.kdp_print_cost_usd = round(asin_data.kdp_print_cost_usd, 6)
    asin_data.ads_matched_print_cost_usd_est = round(
      asin_data.ads_matched_print_cost_usd_est, 6)
    asin_data.organic_print_cost_usd_est = round(
      asin_data.organic_print_cost_usd_est, 6)


def _resolve_kdp_royalty_usd(sale_item: models.AmazonProductStats) -> float:
  """Use explicit royalty field when present, otherwise fall back to profit."""
  if sale_item.total_royalty_usd is not None:
    return float(sale_item.total_royalty_usd)
  return float(sale_item.total_profit_usd)


def _match_units(
  *,
  asin: str,
  kdp_units: int,
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
) -> int:
  """Consume earliest unmatched ads lots for one ASIN and return matched units."""
  if kdp_units <= 0:
    return 0
  queue = lots_by_asin.get(asin)
  if not queue:
    return 0

  matched_units = 0
  remaining = kdp_units
  while remaining > 0 and queue:
    lot = queue[0]
    if lot.units_remaining <= 0:
      _ = queue.popleft()
      continue
    taken = min(remaining, lot.units_remaining)
    lot.units_remaining -= taken
    remaining -= taken
    matched_units += taken
    if lot.units_remaining <= 0:
      _ = queue.popleft()

  if not queue:
    del lots_by_asin[asin]
  return matched_units


def _snapshot_lots(
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
) -> dict[str, list[models.AmazonSalesReconciledAdsLot]]:
  """Copy unmatched lots into a Firestore-ready model structure."""
  output: dict[str, list[models.AmazonSalesReconciledAdsLot]] = {}
  for asin in sorted(lots_by_asin.keys()):
    lots = lots_by_asin[asin]
    copied_lots: list[models.AmazonSalesReconciledAdsLot] = []
    for lot in lots:
      if lot.units_remaining <= 0:
        continue
      copied_lots.append(
        models.AmazonSalesReconciledAdsLot(
          purchase_date=lot.purchase_date,
          units_remaining=int(lot.units_remaining),
        ))
    if copied_lots:
      output[asin] = copied_lots
  return output


def _upsert_reconciled_docs(
  docs: list[models.AmazonSalesReconciledDailyStats], ) -> None:
  """Upsert reconciled daily docs in Firestore batches."""
  _ = firestore.upsert_amazon_sales_reconciled_daily_stats(docs)
