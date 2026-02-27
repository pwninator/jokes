"""Reconcile KDP-date sales and KENP reads against ads click-date attribution.

This file must be sychronized with the spec in `amazon_ads_stats_spec.md`.
"""

from __future__ import annotations

import datetime
from collections import deque
from dataclasses import dataclass

from common import book_defs, models
from firebase_functions import logger
from services import firestore

_MATCH_LOOKBACK_DAYS = 14


@dataclass(frozen=True, kw_only=True)
class _MatchAllocation:
  """One matched quantity allocated back to its original ads click date."""

  purchase_date: datetime.date
  quantity: int


def reconcile_daily_sales(
  *,
  earliest_changed_date: datetime.date,
  run_time_utc: datetime.datetime | None = None,
) -> dict[str, object]:
  """Recompute reconciled daily stats from a rolling 14-day lookback start."""
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
    return {
      "reconciled_days": 0,
      "skipped": True,
      "reason": "missing_source_data",
    }

  ads_min_date, ads_max_date = ads_bounds
  kdp_min_date, kdp_max_date = kdp_bounds
  earliest_raw_date = min(ads_min_date, kdp_min_date)
  latest_common_source_date = min(ads_max_date, kdp_max_date)

  start_date = max(
    earliest_changed_date - datetime.timedelta(days=_MATCH_LOOKBACK_DAYS),
    earliest_raw_date,
  )
  seed_date = start_date - datetime.timedelta(days=1)
  lots_by_asin = _load_seed_lots(seed_date)
  seeded_from_previous_day = lots_by_asin is not None
  if lots_by_asin is None:
    start_date = earliest_raw_date
    lots_by_asin = {}

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

  settled_through_date = latest_common_source_date - datetime.timedelta(
    days=_MATCH_LOOKBACK_DAYS)
  docs_by_date = _initialize_docs_by_date(
    start_date=start_date,
    end_date=end_date,
    settled_through_date=settled_through_date,
    run_time_utc=run_time_utc,
  )

  current_date = start_date
  while current_date <= end_date:
    expired_lots = _prune_expired_lots(lots_by_asin, current_date)
    _record_unmatched_click_date_lots(
      expired_lots,
      docs_by_date=docs_by_date,
    )
    _append_ads_lots_for_day(
      current_date=current_date,
      ads_stat=ads_by_date.get(current_date),
      lots_by_asin=lots_by_asin,
    )
    _apply_kdp_reconciliation_for_day(
      current_date=current_date,
      kdp_stat=kdp_by_date.get(current_date),
      lots_by_asin=lots_by_asin,
      docs_by_date=docs_by_date,
    )
    docs_by_date[current_date].zzz_ending_unmatched_ads_lots_by_asin = (
      _snapshot_lots(lots_by_asin))
    current_date += datetime.timedelta(days=1)

  _record_unmatched_click_date_lots(
    _flatten_lots(lots_by_asin),
    docs_by_date=docs_by_date,
  )
  _round_docs(docs_by_date)
  reconciled_docs = [
    docs_by_date[date_value] for date_value in sorted(docs_by_date.keys())
  ]
  _upsert_reconciled_docs(reconciled_docs)

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


def _initialize_docs_by_date(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
  settled_through_date: datetime.date,
  run_time_utc: datetime.datetime,
) -> dict[datetime.date, models.AmazonSalesReconciledDailyStats]:
  """Create empty reconciled docs for every date in the recompute range."""
  docs: dict[datetime.date, models.AmazonSalesReconciledDailyStats] = {}
  current_date = start_date
  while current_date <= end_date:
    docs[current_date] = models.AmazonSalesReconciledDailyStats(
      date=current_date,
      is_settled=current_date <= settled_through_date,
      reconciled_at=run_time_utc,
    )
    current_date += datetime.timedelta(days=1)
  return docs


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
        kenp_pages_remaining=lot.kenp_pages_remaining,
      ) for lot in lots
      if lot.units_remaining > 0 or lot.kenp_pages_remaining > 0
    ])
    if queue:
      output[asin] = queue
  return output


def _prune_expired_lots(
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
  current_date: datetime.date,
) -> list[tuple[str, models.AmazonSalesReconciledAdsLot]]:
  """Drop lots older than the matching window and return their residuals."""
  earliest_allowed_date = current_date - datetime.timedelta(
    days=_MATCH_LOOKBACK_DAYS)
  expired: list[tuple[str, models.AmazonSalesReconciledAdsLot]] = []
  empty_asins: list[str] = []
  for asin, queue in lots_by_asin.items():
    while queue and queue[0].purchase_date < earliest_allowed_date:
      lot = queue.popleft()
      if lot.units_remaining > 0 or lot.kenp_pages_remaining > 0:
        expired.append((
          asin,
          models.AmazonSalesReconciledAdsLot(
            purchase_date=lot.purchase_date,
            units_remaining=lot.units_remaining,
            kenp_pages_remaining=lot.kenp_pages_remaining,
          ),
        ))
    while queue and queue[0].units_remaining <= 0 and queue[
        0].kenp_pages_remaining <= 0:
      _ = queue.popleft()
    if not queue:
      empty_asins.append(asin)
  for asin in empty_asins:
    del lots_by_asin[asin]
  return expired


def _append_ads_lots_for_day(
  *,
  current_date: datetime.date,
  ads_stat: models.AmazonAdsDailyStats | None,
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
) -> None:
  """Append today's ads-attributed units and KENP pages as unmatched lots."""
  if ads_stat is None:
    return

  lots_to_append: dict[str, models.AmazonSalesReconciledAdsLot] = {}
  for campaign_stat in ads_stat.campaigns_by_id.values():
    for sale_item in campaign_stat.sale_items:
      canonical_asin = _canonical_book_variant_asin(sale_item.asin)
      if not canonical_asin:
        continue
      lot = lots_to_append.setdefault(
        canonical_asin,
        models.AmazonSalesReconciledAdsLot(
          purchase_date=current_date,
          units_remaining=0,
          kenp_pages_remaining=0,
        ),
      )
      lot.units_remaining += max(0, int(sale_item.units_sold))
      lot.kenp_pages_remaining += max(0, int(sale_item.kenp_pages_read))

  for canonical_asin, lot in lots_to_append.items():
    if lot.units_remaining <= 0 and lot.kenp_pages_remaining <= 0:
      continue
    lots_by_asin.setdefault(canonical_asin, deque()).append(lot)


def _apply_kdp_reconciliation_for_day(
  *,
  current_date: datetime.date,
  kdp_stat: models.AmazonKdpDailyStats | None,
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
  docs_by_date: dict[datetime.date, models.AmazonSalesReconciledDailyStats],
) -> None:
  """Apply one KDP day's sales and KENP into ship-date and click-date docs."""
  if kdp_stat is None:
    return

  ship_doc = docs_by_date[current_date]
  for sale_item in kdp_stat.sale_items_by_asin.values():
    canonical_asin = _canonical_book_variant_asin(sale_item.asin)
    if not canonical_asin:
      continue

    asin_stats = _get_or_create_asin_stats(ship_doc, canonical_asin)

    kdp_units = max(0, int(sale_item.units_sold))
    ship_doc.kdp_units_total += kdp_units
    asin_stats.kdp_units += kdp_units

    sales_usd = float(sale_item.total_sales_usd)
    royalty_usd = _resolve_kdp_royalty_usd(sale_item)
    print_cost_usd = float(sale_item.total_print_cost_usd or 0.0)

    ship_doc.kdp_sales_usd_total += sales_usd
    ship_doc.kdp_royalty_usd_total += royalty_usd
    ship_doc.kdp_print_cost_usd_total += print_cost_usd
    asin_stats.kdp_sales_usd += sales_usd
    asin_stats.kdp_royalty_usd += royalty_usd
    asin_stats.kdp_print_cost_usd += print_cost_usd

    unit_allocations = _match_quantity(
      asin=canonical_asin,
      quantity=kdp_units,
      lots_by_asin=lots_by_asin,
      quantity_field="units_remaining",
    )
    matched_units = sum(allocation.quantity for allocation in unit_allocations)
    organic_units = kdp_units - matched_units
    matched_unit_ratio = (matched_units / kdp_units) if kdp_units > 0 else 0.0

    ads_ship_sales_usd = sales_usd * matched_unit_ratio
    ads_ship_royalty_usd = royalty_usd * matched_unit_ratio
    ads_ship_print_cost_usd = print_cost_usd * matched_unit_ratio
    organic_sales_usd = sales_usd - ads_ship_sales_usd
    organic_royalty_usd = royalty_usd - ads_ship_royalty_usd
    organic_print_cost_usd = print_cost_usd - ads_ship_print_cost_usd

    ship_doc.ads_ship_date_units_total += matched_units
    ship_doc.organic_units_total += organic_units
    ship_doc.ads_ship_date_sales_usd_est += ads_ship_sales_usd
    ship_doc.organic_sales_usd_est += organic_sales_usd
    ship_doc.ads_ship_date_royalty_usd_est += ads_ship_royalty_usd
    ship_doc.organic_royalty_usd_est += organic_royalty_usd
    ship_doc.ads_ship_date_print_cost_usd_est += ads_ship_print_cost_usd
    ship_doc.organic_print_cost_usd_est += organic_print_cost_usd
    asin_stats.ads_ship_date_units += matched_units
    asin_stats.organic_units += organic_units
    asin_stats.ads_ship_date_sales_usd_est += ads_ship_sales_usd
    asin_stats.organic_sales_usd_est += organic_sales_usd
    asin_stats.ads_ship_date_royalty_usd_est += ads_ship_royalty_usd
    asin_stats.organic_royalty_usd_est += organic_royalty_usd
    asin_stats.ads_ship_date_print_cost_usd_est += ads_ship_print_cost_usd
    asin_stats.organic_print_cost_usd_est += organic_print_cost_usd

    for allocation in unit_allocations:
      _apply_click_date_unit_allocation(
        allocation=allocation,
        kdp_units=kdp_units,
        sales_usd=sales_usd,
        royalty_usd=royalty_usd,
        print_cost_usd=print_cost_usd,
        asin=canonical_asin,
        docs_by_date=docs_by_date,
      )

    kdp_kenp_pages = max(0, int(sale_item.kenp_pages_read))
    ship_doc.kdp_kenp_pages_read_total += kdp_kenp_pages
    asin_stats.kdp_kenp_pages_read += kdp_kenp_pages

    kenp_allocations = _match_quantity(
      asin=canonical_asin,
      quantity=kdp_kenp_pages,
      lots_by_asin=lots_by_asin,
      quantity_field="kenp_pages_remaining",
    )
    matched_kenp_pages = sum(allocation.quantity
                             for allocation in kenp_allocations)
    organic_kenp_pages = kdp_kenp_pages - matched_kenp_pages

    ship_doc.ads_ship_date_kenp_pages_read_total += matched_kenp_pages
    ship_doc.organic_kenp_pages_read_total += organic_kenp_pages
    asin_stats.ads_ship_date_kenp_pages_read += matched_kenp_pages
    asin_stats.organic_kenp_pages_read += organic_kenp_pages

    for allocation in kenp_allocations:
      click_doc = docs_by_date.get(allocation.purchase_date)
      if click_doc is None:
        continue
      click_doc.ads_click_date_kenp_pages_read_total += allocation.quantity
      click_asin = _get_or_create_asin_stats(click_doc, canonical_asin)
      click_asin.ads_click_date_kenp_pages_read += allocation.quantity


def _apply_click_date_unit_allocation(
  *,
  allocation: _MatchAllocation,
  kdp_units: int,
  sales_usd: float,
  royalty_usd: float,
  print_cost_usd: float,
  asin: str,
  docs_by_date: dict[datetime.date, models.AmazonSalesReconciledDailyStats],
) -> None:
  """Write one matched unit allocation onto its click-date reconciled doc."""
  click_doc = docs_by_date.get(allocation.purchase_date)
  if click_doc is None:
    return

  allocation_ratio = (allocation.quantity /
                      kdp_units) if kdp_units > 0 else 0.0
  click_doc.ads_click_date_units_total += allocation.quantity
  click_doc.ads_click_date_sales_usd_est += sales_usd * allocation_ratio
  click_doc.ads_click_date_royalty_usd_est += royalty_usd * allocation_ratio
  click_doc.ads_click_date_print_cost_usd_est += (print_cost_usd *
                                                  allocation_ratio)

  click_asin = _get_or_create_asin_stats(click_doc, asin)
  click_asin.ads_click_date_units += allocation.quantity
  click_asin.ads_click_date_sales_usd_est += sales_usd * allocation_ratio
  click_asin.ads_click_date_royalty_usd_est += royalty_usd * allocation_ratio
  click_asin.ads_click_date_print_cost_usd_est += (print_cost_usd *
                                                   allocation_ratio)


def _match_quantity(
  *,
  asin: str,
  quantity: int,
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
  quantity_field: str,
) -> list[_MatchAllocation]:
  """Consume earliest unmatched ads lots for one ASIN and quantity type."""
  if quantity <= 0:
    return []
  queue = lots_by_asin.get(asin)
  if not queue:
    return []

  allocations: list[_MatchAllocation] = []
  remaining = quantity
  while remaining > 0 and queue:
    lot = queue[0]
    lot_quantity = int(getattr(lot, quantity_field))
    if lot_quantity <= 0:
      if lot.units_remaining <= 0 and lot.kenp_pages_remaining <= 0:
        _ = queue.popleft()
      else:
        break
      continue

    taken = min(remaining, lot_quantity)
    setattr(lot, quantity_field, lot_quantity - taken)
    remaining -= taken
    allocations.append(
      _MatchAllocation(
        purchase_date=lot.purchase_date,
        quantity=taken,
      ))
    if lot.units_remaining <= 0 and lot.kenp_pages_remaining <= 0:
      _ = queue.popleft()

  if not queue:
    del lots_by_asin[asin]
  return allocations


def _record_unmatched_click_date_lots(
  lots: list[tuple[str, models.AmazonSalesReconciledAdsLot]],
  *,
  docs_by_date: dict[datetime.date, models.AmazonSalesReconciledDailyStats],
) -> None:
  """Record unmatched residual ads lots back onto their original click date."""
  for asin, lot in lots:
    click_doc = docs_by_date.get(lot.purchase_date)
    if click_doc is None:
      continue
    click_doc.unmatched_ads_click_date_units_total += max(
      0, lot.units_remaining)
    click_doc.unmatched_ads_click_date_kenp_pages_read_total += max(
      0, lot.kenp_pages_remaining)
    click_asin = _get_or_create_asin_stats(click_doc, asin)
    click_asin.unmatched_ads_click_date_units += max(0, lot.units_remaining)
    click_asin.unmatched_ads_click_date_kenp_pages_read += max(
      0, lot.kenp_pages_remaining)


def _flatten_lots(
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
) -> list[tuple[str, models.AmazonSalesReconciledAdsLot]]:
  """Flatten remaining unmatched lots for end-of-run click-date reporting."""
  flattened: list[tuple[str, models.AmazonSalesReconciledAdsLot]] = []
  for asin, lots in lots_by_asin.items():
    for lot in lots:
      if lot.units_remaining <= 0 and lot.kenp_pages_remaining <= 0:
        continue
      flattened.append((
        asin,
        models.AmazonSalesReconciledAdsLot(
          purchase_date=lot.purchase_date,
          units_remaining=lot.units_remaining,
          kenp_pages_remaining=lot.kenp_pages_remaining,
        ),
      ))
  return flattened


def _get_or_create_asin_stats(
  doc: models.AmazonSalesReconciledDailyStats,
  asin: str,
) -> models.AmazonSalesReconciledAsinStats:
  """Return the per-ASIN reconciled stats entry for one daily doc."""
  return doc.by_asin.setdefault(
    asin,
    models.AmazonSalesReconciledAsinStats(asin=asin),
  )


def _round_docs(
  docs_by_date: dict[datetime.date, models.AmazonSalesReconciledDailyStats],
) -> None:
  """Round money fields in-place for deterministic Firestore payloads."""
  for doc in docs_by_date.values():
    doc.kdp_sales_usd_total = round(doc.kdp_sales_usd_total, 6)
    doc.ads_click_date_sales_usd_est = round(doc.ads_click_date_sales_usd_est,
                                             6)
    doc.ads_ship_date_sales_usd_est = round(doc.ads_ship_date_sales_usd_est, 6)
    doc.organic_sales_usd_est = round(doc.organic_sales_usd_est, 6)
    doc.kdp_royalty_usd_total = round(doc.kdp_royalty_usd_total, 6)
    doc.ads_click_date_royalty_usd_est = round(
      doc.ads_click_date_royalty_usd_est, 6)
    doc.ads_ship_date_royalty_usd_est = round(
      doc.ads_ship_date_royalty_usd_est, 6)
    doc.organic_royalty_usd_est = round(doc.organic_royalty_usd_est, 6)
    doc.kdp_print_cost_usd_total = round(doc.kdp_print_cost_usd_total, 6)
    doc.ads_click_date_print_cost_usd_est = round(
      doc.ads_click_date_print_cost_usd_est, 6)
    doc.ads_ship_date_print_cost_usd_est = round(
      doc.ads_ship_date_print_cost_usd_est, 6)
    doc.organic_print_cost_usd_est = round(doc.organic_print_cost_usd_est, 6)
    _round_by_asin_fields(doc.by_asin)


def _round_by_asin_fields(
  by_asin: dict[str, models.AmazonSalesReconciledAsinStats], ) -> None:
  """Round money fields in-place for deterministic Firestore payloads."""
  for asin_data in by_asin.values():
    asin_data.kdp_sales_usd = round(asin_data.kdp_sales_usd, 6)
    asin_data.ads_click_date_sales_usd_est = round(
      asin_data.ads_click_date_sales_usd_est, 6)
    asin_data.ads_ship_date_sales_usd_est = round(
      asin_data.ads_ship_date_sales_usd_est, 6)
    asin_data.organic_sales_usd_est = round(asin_data.organic_sales_usd_est, 6)
    asin_data.kdp_royalty_usd = round(asin_data.kdp_royalty_usd, 6)
    asin_data.ads_click_date_royalty_usd_est = round(
      asin_data.ads_click_date_royalty_usd_est, 6)
    asin_data.ads_ship_date_royalty_usd_est = round(
      asin_data.ads_ship_date_royalty_usd_est, 6)
    asin_data.organic_royalty_usd_est = round(
      asin_data.organic_royalty_usd_est, 6)
    asin_data.kdp_print_cost_usd = round(asin_data.kdp_print_cost_usd, 6)
    asin_data.ads_click_date_print_cost_usd_est = round(
      asin_data.ads_click_date_print_cost_usd_est, 6)
    asin_data.ads_ship_date_print_cost_usd_est = round(
      asin_data.ads_ship_date_print_cost_usd_est, 6)
    asin_data.organic_print_cost_usd_est = round(
      asin_data.organic_print_cost_usd_est, 6)


def _resolve_kdp_royalty_usd(sale_item: models.AmazonProductStats) -> float:
  """Use explicit royalty field when present, otherwise fall back to profit."""
  if sale_item.total_royalty_usd is not None:
    return float(sale_item.total_royalty_usd)
  return float(sale_item.total_profit_usd)


def _canonical_book_variant_asin(identifier: str) -> str | None:
  """Normalize an ASIN or ISBN identifier to the canonical book-variant ASIN."""
  raw_identifier = (identifier or "").strip()
  if not raw_identifier:
    return None
  book_variant = book_defs.find_book_variant(raw_identifier)
  if book_variant is None:
    logger.warn(f"Skipping unknown book variant identifier: {raw_identifier}")
    return None
  return book_variant.asin


def _snapshot_lots(
  lots_by_asin: dict[str, deque[models.AmazonSalesReconciledAdsLot]],
) -> dict[str, list[models.AmazonSalesReconciledAdsLot]]:
  """Copy unmatched lots into a Firestore-ready model structure."""
  output: dict[str, list[models.AmazonSalesReconciledAdsLot]] = {}
  for asin in sorted(lots_by_asin.keys()):
    copied_lots: list[models.AmazonSalesReconciledAdsLot] = []
    for lot in lots_by_asin[asin]:
      if lot.units_remaining <= 0 and lot.kenp_pages_remaining <= 0:
        continue
      copied_lots.append(
        models.AmazonSalesReconciledAdsLot(
          purchase_date=lot.purchase_date,
          units_remaining=int(lot.units_remaining),
          kenp_pages_remaining=int(lot.kenp_pages_remaining),
        ))
    if copied_lots:
      output[asin] = copied_lots
  return output


def _upsert_reconciled_docs(
  docs: list[models.AmazonSalesReconciledDailyStats], ) -> None:
  """Upsert reconciled daily docs in Firestore batches."""
  _ = firestore.upsert_amazon_sales_reconciled_daily_stats(docs)
