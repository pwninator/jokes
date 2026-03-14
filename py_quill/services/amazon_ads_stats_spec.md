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

Four Sponsored Products daily reports are requested per profile:

1. `spCampaigns` (campaign-level spend/click/sales rollups)
2. `spAdvertisedProduct` (advertised-product attributed units/sales + KENP)
3. `spSearchTerm` (search-term metrics split by query/keyword/targeting)
4. `spCampaignsPlacement` (campaign-placement rollups)

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

### 1.4 Canonical Metric Definitions

This section defines the precise meaning of every metric persisted or derived
by the ads/KDP stats pipeline. Unless otherwise stated, all money is in USD
after ingest-time FX normalization.

#### 1.4.1 Raw Amazon Ads report metrics

Campaign report (`spCampaigns`) row fields:

- `impressions`: raw Amazon Ads impressions for that campaign/date row.
- `clicks`: raw Amazon Ads clicks for that campaign/date row.
- `cost`: raw Amazon Ads spend for that campaign/date row.
- `sales14d`: Amazon Ads 14-day attributed sales for that campaign/date row.
- `unitsSoldClicks14d`: Amazon Ads 14-day attributed units for that
  campaign/date row.
- `kindleEditionNormalizedPagesRead14d`: Amazon Ads 14-day attributed KENP
  pages for that campaign/date row.
- `kindleEditionNormalizedPagesRoyalties14d`: Amazon Ads 14-day attributed KENP
  royalties for that campaign/date row.

Advertised-product report (`spAdvertisedProduct`) row fields:

- `attributedSalesSameSku14d`: Amazon Ads 14-day attributed sales for the
  advertised-product row.
- `unitsSoldSameSku14d`: Amazon Ads 14-day attributed units for the
  advertised-product row.
- `kindleEditionNormalizedPagesRead14d`: Amazon Ads 14-day attributed KENP
  pages for the advertised-product row.
- `kindleEditionNormalizedPagesRoyalties14d`: Amazon Ads 14-day attributed KENP
  royalties for the advertised-product row.

Search-term report (`spSearchTerm`) row fields:

- `impressions`, `clicks`, `cost`, `purchases14d`, `unitsSoldClicks14d`,
  `sales14d`, `kindleEditionNormalizedPagesRead14d`,
  `kindleEditionNormalizedPagesRoyalties14d`: direct row-level Amazon Ads
  metrics for that `(date, profile, campaign, ad group, query/keyword/target)`
  tuple.

Placement report (`spCampaignsPlacement`) row fields:

- `impressions`, `clicks`, `cost`, `purchases14d`, `unitsSoldClicks14d`,
  `sales14d`, `kindleEditionNormalizedPagesRead14d`,
  `kindleEditionNormalizedPagesRoyalties14d`,
  `topOfSearchImpressionShare`: direct row-level Amazon Ads metrics for that
  `(date, profile, campaign, placement)` tuple.

#### 1.4.2 Persisted ads campaign/day metrics

`AmazonAdsDailyCampaignStats` stores one campaign/day aggregate with these
definitions:

- `spend`: campaign-row `cost`.
- `impressions`: campaign-row `impressions`.
- `clicks`: campaign-row `clicks`.
- `total_attributed_sales_usd`: campaign-row `sales14d`.
- `total_units_sold`: campaign-row `unitsSoldClicks14d`.
- `kenp_pages_read`: campaign-row
  `kindleEditionNormalizedPagesRead14d`, with fallback to
  `attributedKindleEditionNormalizedPagesRead14d` when present.
- `kenp_royalties_usd`: campaign-row
  `kindleEditionNormalizedPagesRoyalties14d`, with fallback to
  `attributedKindleEditionNormalizedPagesRoyalties14d` when present.
- `sale_items_by_asin_country`: per-ASIN+country totals built from
  advertised-product rows after ASIN decomposition.

For each ads-side `sale_items_by_asin_country[asin][country_code]` bucket:

- `units_sold`: decomposed units allocated from
  `spAdvertisedProduct.unitsSoldSameSku14d`.
- `total_sales_usd`: decomposed sales allocated from
  `spAdvertisedProduct.attributedSalesSameSku14d`.
- `kenp_pages_read`: advertised-product KENP pages accumulated onto the
  canonical ebook ASIN for the title.
- `kenp_royalties_usd`: advertised-product KENP royalties accumulated onto the
  canonical ebook ASIN for the title.
- `total_profit_usd`: estimated pre-ad product profit for book sales only:
  `total_sales_usd * royalty_rate - units_sold * print_cost`.
  This excludes KENP royalties.

Ads-side campaign/day profit metrics:

- `gross_profit_before_ads_usd`:
  `sum(sale_items_by_asin_country[*].total_profit_usd) + kenp_royalties_usd`.
- `gross_profit_usd`:
  `gross_profit_before_ads_usd - spend`.

`AmazonAdsDailyStats` stores one date-level aggregate across all campaign/day
rows for that date. Every numeric field on the daily aggregate is the sum of
the corresponding numeric field from its child `campaigns_by_id` rows.

#### 1.4.3 Persisted KDP day metrics

`AmazonKdpDailyStats` stores one ship/read-date aggregate with these
definitions:

- `ebook_units_sold`, `paperback_units_sold`, `hardcover_units_sold`: sums of
  paid `Combined Sales` `Net Units Sold` rows by format where
  `Avg. Offer Price without tax > 0`.
- `total_units_sold`:
  `ebook_units_sold + paperback_units_sold + hardcover_units_sold`.
- `free_units_downloaded`: sum of `Combined Sales` `Net Units Sold` rows where
  `Avg. Offer Price without tax <= 0`. Only ebook rows may contribute here.
- `kenp_pages_read`: sum of `KENP Read`
  `Kindle Edition Normalized Page (KENP) Read`.
- `total_royalties_usd`: sum of `Combined Sales` `Royalty`.
- `ebook_royalties_usd`, `paperback_royalties_usd`, `hardcover_royalties_usd`:
  format-specific partitions of `Royalty`.
- `total_print_cost_usd`: sum of
  `Net Units Sold * Avg. Delivery/Manufacturing cost`.

For each KDP-side `sale_items_by_asin_country[asin][country_code]` bucket:

- `units_sold`: paid units only from `Combined Sales`.
- `free_units_downloaded`: free ebook downloads only.
- `kenp_pages_read`: KENP pages from `KENP Read`.
- `total_sales_usd`: `Net Units Sold * Avg. Offer Price without tax`.
- `total_royalty_usd`: KDP `Royalty`.
- `total_print_cost_usd`: KDP
  `Net Units Sold * Avg. Delivery/Manufacturing cost`.
- `total_profit_usd`: compatibility alias for KDP royalty amount on this
  bucket. The canonical KDP book-profit field is `total_royalty_usd`.
- `unit_prices`: unique observed paid per-unit USD prices for that
  ASIN+country+day.

#### 1.4.4 Reconciled day metrics

`AmazonSalesReconciledDailyStats` stores ship/read-date KDP outcomes split into
matched-ads and organic portions by FIFO matching on `(ASIN, country_code)`.

Direct KDP totals for a reconciled day:

- `kdp_units_total`: sum of KDP paid units for that date.
- `kdp_kenp_pages_read_total`: sum of KDP KENP pages for that date.
- `kdp_sales_usd_total`: sum of KDP paid sales for that date.
- `kdp_royalty_usd_total`: sum of KDP royalties for that date.
- `kdp_print_cost_usd_total`: sum of KDP print cost for that date.

Matched ship-date metrics for a reconciled day:

- `ads_ship_date_units_total`: KDP paid units on that date matched to earlier
  ads lots.
- `ads_ship_date_kenp_pages_read_total`: KDP KENP pages on that date matched to
  earlier ads lots.
- `ads_ship_date_sales_usd_est`: portion of KDP paid sales allocated to matched
  units on that ship date.
- `ads_ship_date_royalty_usd_est`: portion of KDP royalties allocated to
  matched units on that ship date.
- `ads_ship_date_print_cost_usd_est`: portion of KDP print cost allocated to
  matched units on that ship date.

Organic ship-date metrics for a reconciled day:

- `organic_units_total`: KDP paid units on that date not matched to ads lots.
- `organic_kenp_pages_read_total`: KDP KENP pages on that date not matched to
  ads lots.
- `organic_sales_usd_est`: portion of KDP paid sales allocated to unmatched
  units on that ship date.
- `organic_royalty_usd_est`: portion of KDP royalties allocated to unmatched
  units on that ship date.
- `organic_print_cost_usd_est`: portion of KDP print cost allocated to
  unmatched units on that ship date.

Projected click-date metrics for a reconciled day:

- `ads_click_date_units_total`: matched KDP units projected back onto their
  original ads click dates.
- `ads_click_date_kenp_pages_read_total`: matched KDP KENP pages projected back
  onto their original ads click dates.
- `ads_click_date_sales_usd_est`: matched KDP sales projected back onto their
  original ads click dates.
- `ads_click_date_royalty_usd_est`: matched KDP royalties projected back onto
  their original ads click dates.
- `ads_click_date_print_cost_usd_est`: matched KDP print cost projected back
  onto their original ads click dates.

Residual unmatched ads metrics:

- `unmatched_ads_click_date_units_total`: ads-attributed units that aged out of
  the 14-day window without matching any KDP paid unit.
- `unmatched_ads_click_date_kenp_pages_read_total`: ads-attributed KENP pages
  that aged out of the 14-day window without matching any KDP KENP page.

Reconciled ASIN+country rows in `by_asin_country` use the same definitions as
the day-level fields above, scoped to one `(asin, country_code)` key.

#### 1.4.5 Derived reporting metrics

These formulas define the canonical reporting metrics that downstream views
should use when rendering scorecards or charts:

- `CTR = clicks / impressions`
- `CPC = spend / clicks`
- `Conversion Rate = total_units_sold / clicks`
- `Ads Sales = total_attributed_sales_usd`
- `Ads Profit Before Ads = gross_profit_before_ads_usd`
- `Ads Gross Profit = gross_profit_usd`
- `POAS = gross_profit_before_ads_usd / spend`

For reconciled reporting on a click-date basis:

- `Matched Ads Book Profit Before Ads = ads_click_date_royalty_usd_est`
- `Organic Book Profit Before Ads = organic_royalty_usd_est`
- `Reconciled Book Profit Before Ads`:
  `ads_click_date_royalty_usd_est + organic_royalty_usd_est`
- `Reconciled Gross Profit`:
  `(ads_click_date_royalty_usd_est + organic_royalty_usd_est) - spend`

When reporting layers include ads-attributed KENP royalties alongside
reconciled book profit, the KENP contribution must be added explicitly from the
ads-side metrics. Reconciled docs do not currently persist KDP-native KENP
royalty dollars.

## 2. Firestore Collections and Ownership

Ads report metadata/daily totals remain in `py_quill/services/firestore.py`.
Search-term row storage is owned by `py_quill/storage/amazon_ads_firestore.py`.

Collections:

1. `amazon_ads_reports`
2. `amazon_ads_daily_stats`
3. `amazon_ads_search_term_daily_stats`
4. `amazon_kdp_daily_stats`
5. `amazon_sales_reconciled_daily_stats`

Reconciled docs persist per-item data as nested ASIN+country maps:

- `by_asin_country[asin][country_code] -> reconciled per-item stats`
- `zzz_ending_unmatched_ads_lots_by_asin_country[asin][country_code] -> lots`

Model classes for search-term rows live in `py_quill/models/amazon_ads_models.py`.

## 3. Ads Request/Fetch Lifecycle

### 3.1 Request phase

`request_ads_stats_reports(run_time_utc)`:

1. Compute target window:
   - `report_end_date = run_time_utc.date()`
   - `report_start_date = report_end_date - 30 days`
2. List all profiles and keep allowed countries (`US`, `CA`, `UK`, `GB`).
3. Load recent report metadata from Firestore and keep latest report-per
   `(profile_id, report_key)` created today for the target window.
4. For each selected profile:
   - If all required report keys already exist and are not all processed,
     skip requesting.
   - Else create all four reports and upsert metadata docs.
   - Report names and Firestore doc ids use the canonical format
     `YYYYMMDD_HHMMSS_[reportKey]_[country]` in Los Angeles local time.

### 3.2 Fetch phase

`fetch_ads_stats_reports(run_time_utc)`:

1. Build same context as request phase.
2. Wait a short fixed delay (`ADS_STATS_REPORT_METADATA_WAIT_SEC`).
3. For each selected profile:
   - Fetch latest report statuses by report id.
   - If all four reports are complete and at least one is unprocessed:
     1. Download + parse rows from each report.
     2. Merge into `AmazonAdsDailyCampaignStats`.
     3. Normalize `spSearchTerm` rows into `AmazonAdsSearchTermDailyStat`.
     4. Normalize `spCampaignsPlacement` rows into
        `AmazonAdsPlacementDailyStat`.
     5. Upsert daily totals + search-term rows + placement rows.
     6. Mark all four reports `processed=true` and upsert.
4. If any daily stats were upserted, run reconciliation with:
   - `earliest_changed_date = min(processed_ads_stat.date)`.

## 4. Ads Report Parsing

### 4.1 Download format

Downloaded report bytes are gzip-compressed JSON text. The unzipped text is
persisted to `AmazonAdsReport.raw_report_text` exactly as downloaded.

`spSearchTerm` raw payloads are persisted the same way as other report types.

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

- paid units totals by format
- `free_units_downloaded` for free ebook downloads
- KENP pages read total
- royalties/print cost in USD
- nested `sale_items_by_asin_country` keyed by ASIN then country

### 6.4 Per-ASIN+country persistence

`AmazonKdpDailyStats.sale_items_by_asin_country` stores buckets keyed by
`{ASIN}->{COUNTRY_CODE}` with `AmazonProductStats` values.

`AmazonProductStats.units_sold` stores paid units only, while
`AmazonProductStats.free_units_downloaded` stores free ebook downloads.
Non-ebook rows with zero `Avg. Offer Price without tax` fail ingestion.

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
