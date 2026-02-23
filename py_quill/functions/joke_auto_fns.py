"""Automated joke scheduling and maintenance functions."""

from __future__ import annotations

import dataclasses
import datetime
import html
import time
from collections import deque
from collections.abc import Iterator
from typing import cast
from zoneinfo import ZoneInfo

import flask
from common import (joke_category_operations, joke_lead_operations,
                    joke_operations, models)
from firebase_functions import https_fn, logger, options, scheduler_fn
from functions.function_utils import (error_response, html_response,
                                      success_response)
from google.cloud.firestore import (SERVER_TIMESTAMP, Client,
                                    DocumentReference, DocumentSnapshot)
from services import amazon, firestore

_RECENT_STATS_DAILY_DECAY_FACTOR = 0.9
_MAX_FIRESTORE_WRITE_BATCH_SIZE = 100
_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME = "last_recent_stats_update_time"
_ADS_STATS_TARGET_COUNTRY_CODES = {"US"}  #, "CA", "UK", "GB"}
_ADS_STATS_REPORT_WINDOW_DAYS = 7
_ADS_STATS_REPORT_METADATA_WAIT_SEC = 5
_ADS_STATS_REQUIRED_REPORT_TYPES = (
  "spCampaigns",
  "spAdvertisedProduct",
  "spPurchasedProduct",
)
_ADS_STATS_COMPLETE_REPORT_STATUSES = {"COMPLETED", "SUCCESS"}


@scheduler_fn.on_schedule(
  # Runs at every hour PST every day
  schedule="0 * * * *",
  timezone=ZoneInfo("America/Los_Angeles"),
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def auto_joke_hourly_scheduler(event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that performs daily maintenance tasks for jokes."""
  scheduled_time_utc = event.schedule_time
  if not scheduled_time_utc:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)
  _ = _joke_maintenance_internal(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def auto_joke_hourly_http(req: flask.Request) -> flask.Response:
  """HTTP endpoint to trigger daily maintenance tasks for jokes."""
  del req
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    maintenance_stats = _joke_maintenance_internal(run_time_utc)
    return success_response({
      "message": "Daily maintenance completed successfully",
      "stats": maintenance_stats
    })
  except Exception as exc:  # pylint: disable=broad-except
    return error_response(f'Failed to run daily maintenance: {exc}')


@scheduler_fn.on_schedule(
  # Runs daily at 2:30 AM PST
  schedule="30 2 * * *",
  timezone=ZoneInfo("America/Los_Angeles"),
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def auto_user_daily_scheduler(event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that performs daily maintenance tasks for users."""
  scheduled_time_utc = event.schedule_time
  if not scheduled_time_utc:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)
  _ = _user_daily_maintenance_internal(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def auto_user_daily_http(req: flask.Request) -> flask.Response:
  """HTTP endpoint to trigger daily maintenance tasks for users."""
  del req
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    maintenance_stats = _user_daily_maintenance_internal(run_time_utc)
    return success_response({
      "message": "User maintenance completed successfully",
      "stats": maintenance_stats
    })
  except Exception as exc:  # pylint: disable=broad-except
    return error_response(f'Failed to run user maintenance: {exc}')


@scheduler_fn.on_schedule(
  # Runs every 3 hours.
  schedule="0 */3 * * *",
  timezone=ZoneInfo("America/Los_Angeles"),
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def auto_ads_stats_scheduler(event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that kicks off daily Amazon Ads report generation."""
  scheduled_time_utc = event.schedule_time
  if not scheduled_time_utc:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)
  _ = _auto_ads_stats_internal(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def auto_ads_stats_http(req: flask.Request) -> flask.Response:
  """HTTP endpoint to trigger Amazon Ads report generation."""
  del req
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    stats = _auto_ads_stats_internal(run_time_utc)
    return html_response(_render_ads_stats_html(stats))
  except Exception as exc:  # pylint: disable=broad-except
    return error_response(f"Failed to run ads stats fetcher: {exc}")


def _joke_maintenance_internal(
    run_time_utc: datetime.datetime) -> dict[str, int]:
  """Run maintenance tasks for jokes.
  
  Returns:
    Combined dictionary with all maintenance statistics from joke updates and category cache refresh
  """

  joke_stats, jokes_by_id = _update_joke_attributes(run_time_utc)

  # After updating jokes (including is_public), refresh cached category results
  category_stats = joke_category_operations.refresh_category_caches(
    jokes_by_id=jokes_by_id)

  # Rebuild the cached category index document used by the admin UI.
  categories_index_stats = joke_category_operations.rebuild_joke_categories_index(
    jokes_by_id=jokes_by_id)

  # Combine all statistics
  combined_stats = {**joke_stats, **category_stats, **categories_index_stats}

  logger.info(f"Joke maintenance completed with stats: {combined_stats}")
  return combined_stats


def _user_daily_maintenance_internal(
    run_time_utc: datetime.datetime) -> dict[str, int]:
  """Run daily maintenance tasks for users."""
  del run_time_utc
  stats = joke_lead_operations.ensure_users_subscribed()
  logger.info(f"User maintenance completed with stats: {stats}")
  return stats


def _auto_ads_stats_internal(
    run_time_utc: datetime.datetime) -> dict[str, object]:
  """Fetch target country profiles and request daily ads reports."""
  report_end_date = run_time_utc.date() - datetime.timedelta(days=1)
  report_start_date = report_end_date - datetime.timedelta(
    days=_ADS_STATS_REPORT_WINDOW_DAYS)
  today_utc = run_time_utc.date()
  profiles = amazon.get_profiles(region="all")
  existing_reports = firestore.list_amazon_ads_reports(
    created_on_or_after=today_utc - datetime.timedelta(days=2))

  selected_profiles = sorted(
    [
      profile for profile in profiles
      if profile.country_code.upper() in _ADS_STATS_TARGET_COUNTRY_CODES
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

  report_requests: list[dict[str, str]] = []
  for profile in selected_profiles:
    if _has_all_required_reports(
        profile_id=profile.profile_id,
        reports_by_expected_key=reports_by_expected_key,
    ) and not _are_all_reports_processed(
        profile_id=profile.profile_id,
        reports_by_expected_key=reports_by_expected_key,
    ):
      continue

    report_pair = amazon.request_daily_campaign_stats_reports(
      profile=profile,
      start_date=report_start_date,
      end_date=report_end_date,
    )
    reports_by_expected_key[(profile.profile_id,
                             report_pair.campaigns_report.report_type_id
                             )] = report_pair.campaigns_report
    reports_by_expected_key[(
      profile.profile_id, report_pair.advertised_products_report.report_type_id
    )] = report_pair.advertised_products_report
    reports_by_expected_key[(
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

  time.sleep(_ADS_STATS_REPORT_METADATA_WAIT_SEC)
  report_metadata: list[dict[str, object]] = []
  daily_campaign_stats_rows: list[dict[str, object]] = []
  for profile in selected_profiles:
    report_ids = _collect_expected_report_ids_for_profile(
      profile_id=profile.profile_id,
      reports_by_expected_key=reports_by_expected_key,
    )
    if not report_ids:
      continue
    statuses = amazon.get_reports(
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

        daily_campaign_stats = amazon.get_daily_campaign_stats_from_reports(
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
          daily_stat.kenp_royalties += campaign_stat.kenp_royalties
          daily_stat.total_attributed_sales += campaign_stat.total_attributed_sales
          daily_stat.total_units_sold += campaign_stat.total_units_sold
          daily_stat.gross_profit_before_ads += campaign_stat.gross_profit_before_ads
          daily_stat.gross_profit += campaign_stat.gross_profit

        # Upsert aggregated stats
        daily_stats_list = list(stats_by_date.values())
        _ = firestore.upsert_amazon_ads_daily_stats(daily_stats_list)

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

  stats: dict[str, object] = {
    "report_date": report_end_date.isoformat(),
    "report_start_date": report_start_date.isoformat(),
    "report_end_date": report_end_date.isoformat(),
    "profiles_considered": len(profiles),
    "profiles_selected": len(selected_profiles),
    "reports_requested": len(report_requests),
    "requests": report_requests,
    "report_metadata": report_metadata,
    "daily_campaign_stats": daily_campaign_stats_rows,
  }
  stats["reports_fetched"] = len(report_metadata)
  stats["daily_campaign_stats_count"] = len(daily_campaign_stats_rows)
  logger.info(f"Ads stats report metadata: {report_metadata}")
  logger.info(f"Ads daily campaign stats rows: {daily_campaign_stats_rows}")
  logger.info(f"Ads stats fetcher completed with stats: {stats}")
  return stats


def _render_ads_stats_html(stats: dict[str, object]) -> str:
  """Render report metadata and daily campaign stats in HTML tables."""
  report_rows: list[dict[str, object]] = cast(list[dict[str, object]],
                                              stats.get("report_metadata", []))
  daily_stats_rows: list[dict[str, object]] = cast(
    list[dict[str, object]],
    stats.get("daily_campaign_stats", []),
  )
  report_fields = [
    field_def.name for field_def in dataclasses.fields(models.AmazonAdsReport)
  ]
  daily_stats_fields = [
    "profile_id",
    "profile_country",
    "region",
  ] + [
    field_def.name
    for field_def in dataclasses.fields(models.AmazonAdsDailyCampaignStats)
  ]

  reports_table_html = _render_html_table(
    rows=report_rows,
    fields=report_fields,
    empty_message="No report metadata found.",
    download_link_fields={"url"},
  )
  daily_stats_table_html = _render_html_table(
    rows=daily_stats_rows,
    fields=daily_stats_fields,
    empty_message="No daily campaign stats found.",
  )
  return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Ads Report Metadata</title></head>
<body>
  <h1>Ads Report Metadata</h1>
  <p><strong>Report Date:</strong> {html.escape(str(stats.get("report_date", "")))}</p>
  <p><strong>Report Start Date:</strong> {html.escape(str(stats.get("report_start_date", "")))}</p>
  <p><strong>Report End Date:</strong> {html.escape(str(stats.get("report_end_date", "")))}</p>
  <p><strong>Profiles Considered:</strong> {html.escape(str(stats.get("profiles_considered", "")))}</p>
  <p><strong>Profiles Selected:</strong> {html.escape(str(stats.get("profiles_selected", "")))}</p>
  <p><strong>Reports Requested:</strong> {html.escape(str(stats.get("reports_requested", "")))}</p>
  <p><strong>Reports Fetched:</strong> {html.escape(str(stats.get("reports_fetched", "")))}</p>
  <h2>Reports</h2>
  {reports_table_html}
  <h2>Daily Campaign Stats</h2>
  <p><strong>Daily Stats Rows:</strong> {html.escape(str(stats.get("daily_campaign_stats_count", "")))}</p>
  {daily_stats_table_html}
</body>
</html>"""


def _render_html_table(
  *,
  rows: list[dict[str, object]],
  fields: list[str],
  empty_message: str,
  download_link_fields: set[str] | None = None,
) -> str:
  """Render a generic HTML table for dictionary rows."""
  if not rows:
    return f"<p>{html.escape(empty_message)}</p>"

  if not download_link_fields:
    download_link_fields = set()

  rendered_rows: list[str] = []
  for row in rows:
    field_cells: list[str] = []
    for field_name in fields:
      value = row.get(field_name, "")
      if field_name in download_link_fields and str(value).strip():
        url = html.escape(str(value), quote=True)
        field_cells.append(f"<td><a href=\"{url}\">download</a></td>")
      else:
        field_cells.append(f"<td>{html.escape(str(value))}</td>")
    rendered_rows.append(f"<tr>{''.join(field_cells)}</tr>")

  header_cells = "".join(f"<th>{html.escape(field_name)}</th>"
                         for field_name in fields)
  return ("<table border='1' cellpadding='6' cellspacing='0'>"
          f"<thead><tr>{header_cells}</tr></thead>"
          f"<tbody>{''.join(rendered_rows)}</tbody>"
          "</table>")


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
    if report.report_type_id not in _ADS_STATS_REQUIRED_REPORT_TYPES:
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
             for report_type in _ADS_STATS_REQUIRED_REPORT_TYPES)


def _are_all_reports_processed(
  *,
  profile_id: str,
  reports_by_expected_key: dict[tuple[str, str], models.AmazonAdsReport],
) -> bool:
  """Return whether all required report types for the profile are processed."""
  for report_type in _ADS_STATS_REQUIRED_REPORT_TYPES:
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
  for report_type in _ADS_STATS_REQUIRED_REPORT_TYPES:
    report = reports_by_expected_key.get((profile_id, report_type))
    if not report:
      continue
    report_ids.append(report.report_id)
  return report_ids


def _are_reports_complete(*reports: models.AmazonAdsReport) -> bool:
  """Return True when all provided reports are complete."""
  return all(report.status.upper() in _ADS_STATS_COMPLETE_REPORT_STATUSES
             for report in reports)


def _should_skip_recent_update(
  data: dict[str, object],
  run_time_utc: datetime.datetime,
) -> bool:
  """Return True when the previous update was within the skip threshold."""
  last_update = data.get(_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME)
  if not isinstance(last_update, datetime.datetime):
    return False

  if last_update.tzinfo is None:
    last_update = last_update.replace(tzinfo=datetime.timezone.utc)
  else:
    last_update = last_update.astimezone(datetime.timezone.utc)

  return (run_time_utc - last_update) < datetime.timedelta(hours=22)


def _to_utc_datetime(value: object) -> datetime.datetime | None:
  """Normalize Firestore timestamp values to timezone-aware UTC datetimes."""
  if not isinstance(value, datetime.datetime):
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=datetime.timezone.utc)
  return value.astimezone(datetime.timezone.utc)


def _build_book_id_index(db_client: Client) -> tuple[dict[str, str], int]:
  """Return a map of joke_id -> book_id based on joke_books documents."""
  book_id_by_joke: dict[str, str] = {}
  duplicate_jokes = 0
  for book_doc in cast(
      Iterator[DocumentSnapshot],
      db_client.collection("joke_books").stream(),
  ):
    if not getattr(book_doc, "exists", False):
      continue
    book_data = book_doc.to_dict() or {}
    joke_ids = book_data.get("jokes")
    if not isinstance(joke_ids, list):
      continue
    joke_ids = cast(list[str], joke_ids)
    for joke_id in joke_ids:
      if not joke_id:
        continue
      joke_key = str(joke_id).strip()
      if not joke_key:
        continue
      existing_book = book_id_by_joke.get(joke_key)
      if existing_book and existing_book != book_doc.id:
        duplicate_jokes += 1
        logger.warn(
          f"Joke {joke_key} appears in multiple books: {existing_book}, {book_doc.id}"
        )
        continue
      book_id_by_joke[joke_key] = book_doc.id
  return book_id_by_joke, duplicate_jokes


def _expected_is_public(
  data: dict[str, object],
  now_utc: datetime.datetime,
) -> bool:
  """Determine whether a joke should currently be public."""
  state_value = data.get("state")
  try:
    state = models.JokeState(state_value)
  except Exception:  # pylint: disable=broad-except
    return False

  if state == models.JokeState.PUBLISHED:
    return True
  if state == models.JokeState.DAILY:
    public_timestamp = _to_utc_datetime(data.get("public_timestamp"))
    return bool(public_timestamp and public_timestamp <= now_utc)
  return False


def _build_recent_decay_payload(data: dict[str, object]) -> dict[str, object]:
  """Construct the payload that applies decay to the supplied joke data."""
  payload: dict[str, object] = {}

  for field_name in (
      "num_viewed_users_recent",
      "num_saved_users_recent",
      "num_shared_users_recent",
  ):
    original_value = data.get(field_name)
    if not original_value:
      continue
    if not isinstance(original_value, (int, float)):
      raise ValueError(
        f"Unexpected {field_name} type {type(original_value)} when decaying recent counters"
      )

    original_value = float(original_value)
    decayed_value = max(0.0, original_value * _RECENT_STATS_DAILY_DECAY_FACTOR)
    payload[field_name] = decayed_value

  payload[_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME] = SERVER_TIMESTAMP
  return payload


def _compute_joke_payload_and_stats(
  joke_data: dict[str, object],
  run_time_utc: datetime.datetime,
  expected_book_id: str | None,
) -> tuple[dict[str, object], dict[str, int]]:
  """Compute update payload and stat deltas for one joke.

  Returns:
    (payload, stats_delta) where stats_delta has keys public_updated,
    book_id_updated, jokes_decayed (each 0 or 1).
  """
  payload: dict[str, object] = {}
  stats_delta: dict[str, int] = {
    "public_updated": 0,
    "book_id_updated": 0,
    "jokes_decayed": 0,
  }

  expected_is_public = _expected_is_public(joke_data, run_time_utc)
  current_is_public = joke_data.get("is_public")
  if not isinstance(current_is_public,
                    bool) or current_is_public != expected_is_public:
    payload["is_public"] = expected_is_public
    stats_delta["public_updated"] = 1

  if expected_is_public:
    current_category_id = joke_data.get("category_id")
    if not isinstance(current_category_id,
                      str) or not current_category_id.strip():
      payload["category_id"] = firestore.UNCATEGORIZED_CATEGORY_ID

  has_book_id = "book_id" in joke_data
  current_book_id = joke_data.get("book_id")
  if isinstance(current_book_id, str):
    normalized_book_id = current_book_id.strip() or None
  else:
    normalized_book_id = None
  if expected_book_id is None:
    if not has_book_id or normalized_book_id is not None:
      payload["book_id"] = None
      stats_delta["book_id_updated"] = 1
  elif normalized_book_id != expected_book_id:
    payload["book_id"] = expected_book_id
    stats_delta["book_id_updated"] = 1

  if not _should_skip_recent_update(joke_data, run_time_utc):
    payload.update(_build_recent_decay_payload(joke_data))
    stats_delta["jokes_decayed"] = 1

  return payload, stats_delta


def _sync_joke_and_append_if_public(
  joke_doc_id: str,
  joke: models.PunnyJoke,
  public_jokes: list[models.PunnyJoke],
) -> None:
  """Sync joke to search collection if not draft; append to public_jokes if public."""
  if joke.state != models.JokeState.DRAFT:
    try:
      joke_operations.sync_joke_to_search_collection(joke=joke,
                                                     new_embedding=None)
    except Exception as sync_error:
      logger.warn(
        f"Failed to sync joke {joke_doc_id} to search collection: {sync_error}"
      )
  if joke.is_public:
    public_jokes.append(joke)


def _update_joke_attributes(
  run_time_utc: datetime.datetime
) -> tuple[dict[str, int], dict[str, models.PunnyJoke]]:
  """Apply exponential decay to recent counters across all jokes.

  Returns:
    Tuple of:
      - Dictionary with maintenance statistics: jokes_decayed, public_updated, jokes_skipped
      - Dictionary of all jokes (after applying any computed payload) keyed by joke id
  """

  db_client = firestore.db()
  jokes_collection = db_client.collection("jokes")
  book_id_by_joke, duplicate_book_jokes = _build_book_id_index(db_client)
  joke_docs = cast(Iterator[DocumentSnapshot], jokes_collection.stream())

  batch = db_client.batch()
  writes_in_batch = 0
  jokes_decayed = 0
  public_updated = 0
  book_id_updated = 0
  jokes_skipped = 0

  public_jokes: list[models.PunnyJoke] = []
  jokes_by_id: dict[str, models.PunnyJoke] = {}

  for joke_doc in joke_docs:
    if not joke_doc.exists:
      continue
    joke_data = joke_doc.to_dict() or {}
    joke_id = cast(str, joke_doc.id)
    joke_doc_ref = cast(DocumentReference, joke_doc.reference)
    expected_book_id = book_id_by_joke.get(joke_id)
    payload, stats_delta = _compute_joke_payload_and_stats(
      joke_data, run_time_utc, expected_book_id)
    public_updated += stats_delta["public_updated"]
    book_id_updated += stats_delta["book_id_updated"]
    jokes_decayed += stats_delta["jokes_decayed"]

    final_joke_data = {**joke_data, **payload}
    try:
      joke = models.PunnyJoke.from_firestore_dict(final_joke_data, joke_id)
    except Exception as parse_error:
      logger.warn(f"Failed to parse joke {joke_id}, skipping: {parse_error}")
      continue
    jokes_by_id[joke_id] = joke

    # Perform actions based on the final state.
    if payload:
      batch.update(joke_doc_ref, payload)
      writes_in_batch += 1
    else:
      jokes_skipped += 1

    _sync_joke_and_append_if_public(joke_id, joke, public_jokes)

    if writes_in_batch >= _MAX_FIRESTORE_WRITE_BATCH_SIZE:
      logger.info(f"Committing batch of {writes_in_batch} writes")
      batch.commit()  # pyright: ignore[reportUnusedCallResult]
      batch = db_client.batch()
      writes_in_batch = 0

  if writes_in_batch:
    logger.info(f"Committing final batch of {writes_in_batch} writes")
    batch.commit()  # pyright: ignore[reportUnusedCallResult]

  if public_jokes:
    logger.info(f"Public jokes found: {len(public_jokes)}")
    sorted_feed = build_joke_feed(public_jokes)
    firestore.update_joke_feed(
      [j.get_minimal_joke_data() for j in sorted_feed])

  logger.info(
    f"Joke daily maintenance completed: {jokes_decayed} recent stats decayed, {public_updated} is_public updated, {book_id_updated} book_id updated, {jokes_skipped} jokes skipped"
  )

  return {
    "jokes_decayed": jokes_decayed,
    "public_updated": public_updated,
    "book_id_updated": book_id_updated,
    "duplicate_book_jokes": duplicate_book_jokes,
    "jokes_skipped": jokes_skipped,
    "num_public_jokes": len(public_jokes),
  }, jokes_by_id


def build_joke_feed(jokes: list[models.PunnyJoke]) -> list[models.PunnyJoke]:
  """Reorders the input list of jokes to build a feed.

  The returned list contains all input jokes, ordered as follows:
  1. The 10 jokes with the highest `num_saved_users_fraction` appear first,
     sorted in descending order of that fraction.
  2. The remaining jokes follow, arranged in an alternating pattern of:
     a. The highest-ranked joke not yet included in the list.
     b. The lowest-viewed joke (by `num_viewed_users`) from the remaining pool.

  If the input contains fewer than 10 jokes, the entire list is simply sorted
  by `num_saved_users_fraction` in descending order.
  """
  if not jokes:
    return []

  sorted_by_fraction = deque[models.PunnyJoke](sorted(
    jokes, key=lambda j: j.num_saved_users_fraction, reverse=True))
  sorted_by_views = deque[models.PunnyJoke](sorted(
    jokes, key=lambda j: j.num_viewed_users))
  unused_ids = {id(joke) for joke in jokes}
  result_list: list[models.PunnyJoke] = []

  def _pop_next(queue: deque[models.PunnyJoke]) -> models.PunnyJoke | None:
    while queue:
      candidate = queue.popleft()
      candidate_id = id(candidate)
      if candidate_id in unused_ids:
        unused_ids.remove(candidate_id)
        return candidate
    return None

  top_pick_count = min(10, len(jokes))
  for _ in range(top_pick_count):
    next_joke = _pop_next(sorted_by_fraction)
    if next_joke is None:
      break
    result_list.append(next_joke)

  while unused_ids:
    ranked_joke = _pop_next(sorted_by_fraction)
    if ranked_joke:
      result_list.append(ranked_joke)

    if not unused_ids:
      break

    lowest_viewed_joke = _pop_next(sorted_by_views)
    if lowest_viewed_joke:
      result_list.append(lowest_viewed_joke)

  return result_list
