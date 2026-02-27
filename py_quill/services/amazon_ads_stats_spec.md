# Amazon Ads/KDP Stats and Reconciliation Spec (v1)

This document is the canonical behavioral spec for:

- Ads report orchestration and ingestion in
  `py_quill/services/amazon.py`
- KDP xlsx ingestion in `py_quill/services/amazon_kdp.py`
- KDP-vs-ads FIFO reconciliation in
  `py_quill/services/amazon_sales_reconciliation.py`

Changes to this file must be reflected immediately in the corresponding code.

## 1. Scope and Data Sources

### 1.1 Ads source reports (Amazon Ads API v3)

Two Sponsored Products daily reports are requested per profile:

1. `spCampaigns` (campaign-level spend/click/sales rollups)
2. `spAdvertisedProduct` (advertised-product attributed units/sales + KENP)

Reports are requested as `GZIP_JSON`, time unit `DAILY`, date range 30 days.

### 1.2 KDP source report (manual xlsx upload)

The uploaded workbook contains:

- `Combined Sales`
- `KENP Read`

KDP rows are ship/read-date based.

### 1.3 Reconciled output

Daily reconciled docs split KDP ship-date outcomes into:

- `ads_ship_date_*` (matched ads-attributed portion by ship/read date)
- `ads_click_date_*` (same matched quantity projected to original click date)
- `organic_*` (unmatched KDP portion)
- `unmatched_ads_click_date_*` (ads click-date quantity still unmatched)

## 2. Firestore Collections and Ownership

All Firestore operations are owned by `py_quill/services/firestore.py`.

Collections:

1. `amazon_ads_reports`
2. `amazon_ads_daily_stats`
3. `amazon_kdp_daily_stats`
4. `amazon_sales_reconciled_daily_stats`

Reconciled docs persist per-item data as nested ASIN+country maps:

- `by_asin_country[asin][country_code] -> reconciled per-item stats`
- `zzz_ending_unmatched_ads_lots_by_asin_country[asin][country_code] -> lots`

Model classes live in `py_quill/common/models.py` and are the storage contract.

## 3. Ads Request/Fetch Lifecycle

### 3.1 Request phase

`request_ads_stats_reports(run_time_utc)`:

1. Compute target window:
   - `report_end_date = run_time_utc.date()`
   - `report_start_date = report_end_date - 30 days`
2. List all profiles and keep allowed countries (`US`, `CA`, `UK`, `GB`).
3. Load recent report metadata from Firestore and keep latest report-per
   `(profile_id, report_type_id)` created today for the target window.
4. For each selected profile:
   - If both required report types already exist and are not all processed,
     skip requesting.
   - Else create both reports and upsert metadata docs.
   - Report names and Firestore doc ids use the canonical format
     `YYYYMMDD_HHMMSS_[reportTypeId]_[country]` in Los Angeles local time.

### 3.2 Fetch phase

`fetch_ads_stats_reports(run_time_utc)`:

1. Build same context as request phase.
2. Wait a short fixed delay (`ADS_STATS_REPORT_METADATA_WAIT_SEC`).
3. For each selected profile:
   - Fetch latest report statuses by report id.
   - If both reports are complete and at least one is unprocessed:
     1. Download + parse rows from each report.
     2. Merge into `AmazonAdsDailyCampaignStats`.
     3. Aggregate by date into `AmazonAdsDailyStats`.
     4. Upsert daily stats.
     5. Mark both reports `processed=true` and upsert.
4. If any daily stats were upserted, run reconciliation with:
   - `earliest_changed_date = min(processed_ads_stat.date)`.

## 4. Ads Report Parsing

### 4.1 Download format

Downloaded report bytes are gzip-compressed JSON text. The unzipped text is
persisted to `AmazonAdsReport.raw_report_text` exactly as downloaded.

### 4.2 Row decoding

`parse_report_rows_text` supports:

1. JSON array payload
2. JSON object payload
3. JSON-lines fallback

Non-dict rows are ignored.

### 4.3 Currency normalization

All money is normalized to USD at ingest time using fixed FX rates.

Currency resolution priority:

1. row `campaignBudgetCurrencyCode`
2. profile-country fallback map
3. `USD`

## 5. Ads ASIN Decomposition (import-time correction)

### 5.1 Problem

`spAdvertisedProduct` units/sales can be attributed under `advertisedAsin`
even when purchased format differs (for example ebook ad click, paperback
purchase). Source totals are usually correct, but ASIN assignment can be wrong.

### 5.2 Inputs per advertised-product row

For each `(campaign_id, date, advertisedAsin)` row:

- `units_sold = unitsSoldSameSku14d`
- `sales_usd = attributedSalesSameSku14d` (converted to USD)
- country code from profile country
- row currency

### 5.3 Variant universe

The advertised ASIN is mapped to a canonical book variant via `book_defs`.
Then all variants of that same book become decomposition candidates
(typically ebook + paperback).

### 5.4 Price candidates

Candidate per-unit USD prices for each `(country_code, asin)` come from
historical KDP daily docs (lookback 180 days):

1. `sale_items_by_asin_country[asin][country].unit_prices`
2. fallback derived from the same bucket average
   (`total_sales_usd / units`)

Candidates are then filtered by `BookVariant.min_price_usd/max_price_usd`.

If no candidates remain, fallback candidates are generated from price-range
metadata (`min`, `max`, midpoint).

### 5.5 Allocation search

Given total units `U` and candidate variants `V`:

1. Enumerate all integer unit partitions across variants where sum = `U`.
2. For each partition, enumerate cartesian price choices from candidate
   price lists for active variants.
3. Compute base total sales `sum(units_i * price_i)`.
4. Pick the best combination by lexicographic score:
   - minimal absolute sales delta
   - minimal number of active variants
   - then preference toward units on advertised variant
   - deterministic unit tuple tie-break

### 5.6 Residual delta distribution

After choosing units + base prices:

1. Compute `residual = row_sales - base_total`.
2. Distribute residual across allocated variants proportionally:
   - by base sales if available, otherwise by units.
3. Force final variant to absorb floating remainder so allocated sales sum
   exactly equals row total.

Output becomes multiple ASIN allocations with corrected units/sales.

### 5.7 Merge output

Per-campaign/day ASIN totals are built entirely from advertised-product rows:

1. Units/sales come from decomposed advertised-product allocations.
2. Advertised-product KENP pages/royalties are accumulated directly onto
   `sale_items_by_asin_country`.
3. If the advertised ASIN is a paperback variant, advertised-product KENP is
   reassigned at import time to the ebook variant for the same book before
   persistence.

Then each ASIN+country total is converted to `AmazonProductStats`:

- `total_profit_usd = total_sales_usd * royalty_rate - units * print_cost`

## 6. KDP Parsing and Persistence

### 6.1 Identifier canonicalization

KDP `ASIN/ISBN` is mapped through `book_defs.find_book_variant`.
Paperback ISBNs are normalized to canonical ASIN before storage.

### 6.2 Format validation

Transaction type format (`ebook/paperback/hardcover`) must match
`book_defs` variant format or parsing fails.

### 6.3 Daily aggregate (existing totals)

Persisted per date:

- units totals by format
- KENP pages read total
- royalties/print cost in USD
- nested `sale_items_by_asin_country` keyed by ASIN then country

### 6.4 Per-ASIN+country persistence

`AmazonKdpDailyStats.sale_items_by_asin_country` stores buckets keyed by
`{ASIN}->{COUNTRY_CODE}` with `AmazonProductStats` values.

`AmazonProductStats.unit_prices` stores unique observed per-unit USD prices for
that ASIN+country+day. These are the primary candidate prices used later by ads
decomposition.

## 7. Reconciliation Algorithm (FIFO)

### 7.1 Core model

Reconciliation matches KDP ship/read-date quantities against prior ads
click-date lots with max lookback 14 days.

Each lot stores:

- `purchase_date`
- `units_remaining`
- `kenp_pages_remaining`

Lots are FIFO per `(ASIN, country_code)`.

### 7.2 Incremental recompute window

Given `earliest_changed_date`:

1. Start recompute at `earliest_changed_date - 14 days`.
2. If previous-day reconciled doc exists, seed unmatched lots from its
   `zzz_ending_unmatched_ads_lots_by_asin_country`.
3. If missing seed, fall back to full recompute from earliest raw date.

### 7.3 Daily loop

For each day in recompute range:

1. Expire lots older than 14-day window and record their residuals as
   unmatched click-date stats.
2. Append today’s ads lots from
   `amazon_ads_daily_stats.campaigns_by_id[*].sale_items_by_asin_country`.
3. Apply KDP stats for today:
   - Match units FIFO by `(ASIN, country_code)`
   - Match KENP pages FIFO by `(ASIN, country_code)`
   - Compute ads-ship vs organic split on ship date
   - Project matched quantities back to original click dates
4. Snapshot remaining lots into
   `zzz_ending_unmatched_ads_lots_by_asin_country`.

### 7.4 Settled flag

`is_settled = date <= latest_common_source_date - 14 days`.

### 7.5 Rounding

Money fields are rounded before persistence for deterministic docs.

## 8. Invariants

For every reconciled daily doc:

1. `kdp_*` fields are directly sourced from KDP totals for that date.
2. `ads_ship_date_* + organic_* == kdp_*` (subject to float rounding).
3. Summed across all dates:
   - `sum(ads_click_date_*) == sum(ads_ship_date_*)`
4. For fully-settled windows, click-date ads metrics should converge toward ads
   source totals; unsettled recent days may remain lower due unmatched carry.

## 9. Operational Notes

1. Matching windows and report windows are hard-coded in Python constants.
2. Reconciliation is triggered after ads ingest and after KDP upload.
3. Unknown ASIN/ISBN values fail fast in ingestion paths where attribution
   correctness depends on canonical mapping.

## 10. Compatibility and Evolution

1. This implementation is forward-only; no backward schema compatibility is
   maintained for previous KDP `sale_items` list shape.
2. Future changes must keep this document and model schemas synchronized.
