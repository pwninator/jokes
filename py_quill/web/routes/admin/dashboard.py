"""Admin dashboard + stats routes."""

from __future__ import annotations

import csv
import datetime
import io
import json
import re
from typing import Any, cast
from zoneinfo import ZoneInfo

import flask
from common import amazon_redirect, models
from firebase_functions import logger
from functions import auth_helpers
from services import amazon, amazon_kdp, amazon_sales_reconciliation, firestore
from web.routes import web_bp
from web.routes.redirects import amazon_redirect_view_models
from web.utils import stats as stats_utils

_ADS_STATS_LOOKBACK_DAYS = 30
_ADS_REPORTS_LOOKBACK_DAYS = 3
_ADS_REPORT_TABLE_MAX_ROWS = 200
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOS_ANGELES_TIMEZONE = ZoneInfo("America/Los_Angeles")


def _today_in_los_angeles() -> datetime.date:
  """Return today's date in America/Los_Angeles."""
  return datetime.datetime.now(tz=_LOS_ANGELES_TIMEZONE).date()


@web_bp.route('/admin')
@auth_helpers.require_admin
def admin_dashboard():
  """Admin landing page."""
  return flask.render_template(
    'admin/dashboard.html',
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/redirect-tester')
@auth_helpers.require_admin
def admin_redirect_tester():
  """Render the Amazon redirect testing interface."""
  redirect_items = amazon_redirect_view_models()
  country_options = sorted(
    amazon_redirect.COUNTRY_TO_DOMAIN.items(),
    key=lambda item: item[0],
  )
  return flask.render_template(
    'admin/redirect_tester.html',
    redirect_items=redirect_items,
    country_options=country_options,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/stats')
@auth_helpers.require_admin
def admin_stats():
  """Render the stats dashboard."""
  stats_list = firestore.get_joke_stats_docs(limit=30)

  # Normalize buckets for charts
  for stats in stats_list:
    stats['num_1d_users_by_jokes_viewed'] = stats_utils.rebucket_counts(
      stats.get('num_1d_users_by_jokes_viewed'))
    stats['num_7d_users_by_jokes_viewed'] = stats_utils.rebucket_counts(
      stats.get('num_7d_users_by_jokes_viewed'))
    stats['num_7d_users_by_days_used_by_jokes_viewed'] = (
      stats_utils.rebucket_matrix(
        stats.get('num_7d_users_by_days_used_by_jokes_viewed')))

  # Collect all buckets from both DAU and retention to keep colors consistent
  all_buckets: set[str] = set()
  for s in stats_list:
    all_buckets.update(s.get('num_1d_users_by_jokes_viewed', {}).keys())
    all_buckets.update(s.get('num_7d_users_by_jokes_viewed', {}).keys())
    for day_data in s.get('num_7d_users_by_days_used_by_jokes_viewed',
                          {}).values():
      all_buckets.update(day_data.keys())

  sorted_buckets = sorted(list(all_buckets),
                          key=stats_utils.bucket_label_sort_key)
  color_map = stats_utils.build_bucket_color_map(sorted_buckets)

  # --- Prepare DAU Data ---
  dau_labels = [s['id'] for s in stats_list]

  dau_datasets = []
  for idx, bucket in enumerate(sorted_buckets):
    data_points = []
    for s in stats_list:
      val = s.get('num_1d_users_by_jokes_viewed', {}).get(bucket, 0)
      data_points.append(val)

    dau_datasets.append({
      'label': f'{bucket} jokes',
      'data': data_points,
      'backgroundColor': color_map.get(bucket, '#607d8b'),
      'stack': 'Stack 0',
      # Draw highest buckets first so they appear at the bottom of the stack.
      'order': -idx,
    })

  # --- Prepare Retention Data (from most recent stats doc only) ---
  latest_stats = stats_list[-1] if stats_list else {}
  retention_matrix_raw = latest_stats.get(
    'num_7d_users_by_days_used_by_jokes_viewed', {})
  retention_matrix = stats_utils.rebucket_days_used(retention_matrix_raw)

  # Sort days used (labels) numerically
  retention_labels = sorted(retention_matrix.keys(),
                            key=stats_utils.day_bucket_sort_key)

  # Identify all unique joke buckets in the matrix
  retention_buckets: set[str] = set()
  for day_data in retention_matrix.values():
    retention_buckets.update(day_data.keys())
  sorted_ret_buckets = sorted(retention_buckets,
                              key=stats_utils.bucket_label_sort_key)

  retention_datasets = []
  for bucket in sorted_ret_buckets:
    data_points = []
    for day in retention_labels:
      day_data = retention_matrix.get(day, {})
      count = day_data.get(bucket, 0)
      total = sum(day_data.values())
      percentage = (count / total * 100) if total > 0 else 0
      data_points.append(percentage)

    retention_datasets.append({
      'label':
      f'{bucket} jokes',
      'data':
      data_points,
      'backgroundColor':
      color_map.get(bucket, '#607d8b'),
    })

  return flask.render_template(
    'admin/stats.html',
    site_name='Snickerdoodle',
    dau_data={
      'labels': dau_labels,
      'datasets': dau_datasets
    },
    retention_data={
      'labels': retention_labels,
      'datasets': retention_datasets
    },
  )


@web_bp.route('/admin/ads-stats')
@auth_helpers.require_admin
def admin_ads_stats():
  """Render Amazon Ads daily metrics, aggregated by date."""
  end_date = _today_in_los_angeles()
  start_date = end_date - datetime.timedelta(days=_ADS_STATS_LOOKBACK_DAYS - 1)
  stats_list = firestore.list_amazon_ads_daily_stats(
    start_date=start_date,
    end_date=end_date,
  )
  kdp_stats_list = firestore.list_amazon_kdp_daily_stats(
    start_date=start_date,
    end_date=end_date,
  )
  reconciled_stats_list = firestore.list_amazon_sales_reconciled_daily_stats(
    start_date=start_date,
    end_date=end_date,
  )
  ads_events = firestore.list_amazon_ads_events(
    start_date=start_date,
    end_date=end_date,
  )
  chart_data = _build_ads_stats_chart_data(
    stats_list=stats_list,
    start_date=start_date,
    end_date=end_date,
  )
  reconciled_click_date_chart_data = _build_reconciled_click_date_chart_data(
    stats_list=stats_list,
    reconciled_stats_list=reconciled_stats_list,
    start_date=start_date,
    end_date=end_date,
  )
  reconciliation_debug_csv = _build_reconciliation_debug_csv(
    stats_list=stats_list,
    kdp_stats_list=kdp_stats_list,
    reconciled_stats_list=reconciled_stats_list,
    start_date=start_date,
    end_date=end_date,
  )
  return flask.render_template(
    'admin/ads_stats.html',
    site_name='Snickerdoodle',
    chart_data=chart_data,
    reconciled_click_date_chart_data=reconciled_click_date_chart_data,
    reconciliation_debug_csv=reconciliation_debug_csv,
    ads_events=[_serialize_amazon_ads_event(event) for event in ads_events],
    start_date=start_date.isoformat(),
    end_date=end_date.isoformat(),
  )


@web_bp.route('/admin/ads-reports')
@auth_helpers.require_admin
def admin_ads_reports():
  """Render recent ads report metadata and selected cached raw report rows."""
  selected_report_name = str(flask.request.args.get('selected_report_name',
                                                    '')).strip()
  view_model = _build_ads_reports_view_model(
    selected_report_name=selected_report_name)
  return flask.render_template(
    'admin/ads_reports.html',
    site_name='Snickerdoodle',
    **view_model,
  )


@web_bp.route('/admin/ads-reports/request', methods=['POST'])
@auth_helpers.require_admin
def admin_ads_reports_request():
  """Request new ads reports when no recent reports are pending processing."""
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    selected_report_name = _get_ads_reports_selected_report_name()
    current_view_model = _build_ads_reports_view_model(
      selected_report_name=selected_report_name)
    performed = False
    message = 'Reports are already pending.'
    if not cast(bool, current_view_model['has_unprocessed_reports']):
      request_result = amazon.request_ads_stats_reports(run_time_utc)
      performed = True
      num_requested = len(request_result.report_requests)
      message = (f'Requested {num_requested} report set'
                 f'{"s" if num_requested != 1 else ""}.')
    updated_view_model = _build_ads_reports_view_model(
      selected_report_name=selected_report_name,
      action_status_message=message,
      action_status_kind='success' if performed else 'info',
    )
    return _ads_reports_partial_response(
      action='request',
      performed=performed,
      view_model=updated_view_model,
    )
  except amazon.AmazonAdsError as exc:
    return flask.jsonify({'error': str(exc)}), 400
  except Exception as exc:
    logger.error('Failed to request ads stats reports', exc_info=exc)
    return flask.jsonify({'error': 'Failed to request ads stats reports'}), 500


@web_bp.route('/admin/ads-reports/process', methods=['POST'])
@auth_helpers.require_admin
def admin_ads_reports_process():
  """Fetch and process pending ads reports when recent reports are unprocessed."""
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    selected_report_name = _get_ads_reports_selected_report_name()
    current_view_model = _build_ads_reports_view_model(
      selected_report_name=selected_report_name)
    performed = False
    message = 'All reports are already processed.'
    if cast(bool, current_view_model['has_unprocessed_reports']):
      report_metadata, daily_campaign_stats_rows = amazon.fetch_ads_stats_reports(
        run_time_utc)
      performed = True
      message = ('Processed '
                 f'{len(report_metadata)} reports and saved '
                 f'{len(daily_campaign_stats_rows)} daily campaign rows.')
    updated_view_model = _build_ads_reports_view_model(
      selected_report_name=selected_report_name,
      action_status_message=message,
      action_status_kind='success' if performed else 'info',
    )
    return _ads_reports_partial_response(
      action='process',
      performed=performed,
      view_model=updated_view_model,
    )
  except amazon.AmazonAdsError as exc:
    return flask.jsonify({'error': str(exc)}), 400
  except Exception as exc:
    logger.error('Failed to process ads stats reports', exc_info=exc)
    return flask.jsonify({'error': 'Failed to process ads stats reports'}), 500


@web_bp.route('/admin/ads-stats/upload-kdp', methods=['POST'])
@auth_helpers.require_admin
def admin_ads_stats_upload_kdp():
  """Upload a KDP xlsx and persist parsed daily stats."""
  uploaded_file = flask.request.files.get('file')
  if uploaded_file is None or not uploaded_file.filename:
    return flask.jsonify({'error': 'Missing uploaded file'}), 400

  filename = uploaded_file.filename.lower()
  if not filename.endswith('.xlsx'):
    return flask.jsonify({'error': 'File must be a .xlsx report'}), 400

  try:
    stats = amazon_kdp.parse_kdp_xlsx(uploaded_file.read())
    _ = firestore.upsert_amazon_kdp_daily_stats(stats)
    if stats:
      earliest_changed_date = min(stat.date for stat in stats)
      _ = amazon_sales_reconciliation.reconcile_daily_sales(
        earliest_changed_date=earliest_changed_date)
  except amazon_kdp.AmazonKdpError as exc:
    return flask.jsonify({'error': str(exc)}), 400
  except Exception as exc:
    logger.error('Failed to upload KDP daily stats', exc_info=exc)
    return flask.jsonify({'error': 'Failed to process KDP report'}), 500

  return flask.jsonify({'days_saved': len(stats)})


@web_bp.route('/admin/ads-stats/events', methods=['POST'])
@auth_helpers.require_admin
def admin_ads_stats_create_event():
  """Create or update an ads event marker used on timeline charts."""
  payload_raw = flask.request.get_json(silent=True)
  payload = cast(dict[str, Any], payload_raw) if isinstance(payload_raw,
                                                            dict) else {}
  date_raw = str(payload.get('date', '')).strip()
  title = str(payload.get('title', '')).strip()

  if not _ISO_DATE_RE.fullmatch(date_raw):
    return flask.jsonify({'error': 'Date must be in YYYY-MM-DD format'}), 400
  if not title:
    return flask.jsonify({'error': 'Title is required'}), 400

  try:
    parsed_date = datetime.date.fromisoformat(date_raw)
  except ValueError:
    return flask.jsonify({'error': 'Date must be in YYYY-MM-DD format'}), 400

  try:
    saved_event = firestore.upsert_amazon_ads_event(
      models.AmazonAdsEvent(date=parsed_date, title=title))
  except ValueError as exc:
    return flask.jsonify({'error': str(exc)}), 400
  except Exception as exc:
    logger.error('Failed to save ads event', exc_info=exc)
    return flask.jsonify({'error': 'Failed to save ads event'}), 500

  return flask.jsonify({'event': _serialize_amazon_ads_event(saved_event)})


def _serialize_amazon_ads_event(
  event: models.AmazonAdsEvent, ) -> dict[str, object]:
  """Convert an ads event model to a JSON-safe dictionary."""
  return {
    'key': event.key,
    'date': event.date.isoformat(),
    'title': event.title,
    'created_at': event.created_at.isoformat() if event.created_at else None,
    'updated_at': event.updated_at.isoformat() if event.updated_at else None,
  }


def _serialize_amazon_ads_report(
  report: models.AmazonAdsReport, ) -> dict[str, object]:
  """Convert an ads report model to a JSON-safe dictionary for templates."""
  created_at_los_angeles = report.created_at.astimezone(_LOS_ANGELES_TIMEZONE)
  return {
    'report_id': report.report_id,
    'report_name': report.report_name,
    'status': report.status,
    'report_type_id': report.report_type_id,
    'profile_id': report.profile_id or "",
    'profile_country': report.profile_country or "",
    'start_date': report.start_date.isoformat(),
    'end_date': report.end_date.isoformat(),
    'created_at': report.created_at.isoformat(),
    'created_at_display':
    created_at_los_angeles.strftime('%Y-%m-%d %H:%M:%S %Z'),
    'updated_at': report.updated_at.isoformat(),
    'processed': report.processed,
    'has_raw_report_text': bool((report.raw_report_text or "").strip()),
  }


def _list_recent_amazon_ads_reports(
) -> tuple[datetime.date, datetime.date, list[models.AmazonAdsReport]]:
  """Return the recent ads reports window and matching reports."""
  end_date = _today_in_los_angeles()
  start_date = end_date - datetime.timedelta(days=_ADS_REPORTS_LOOKBACK_DAYS -
                                             1)
  reports = firestore.list_amazon_ads_reports(created_on_or_after=start_date)
  return start_date, end_date, reports


def _has_unprocessed_amazon_ads_reports(
  reports: list[models.AmazonAdsReport], ) -> bool:
  """Return whether any recent ads reports still need processing."""
  return any(not report.processed for report in reports)


def _get_ads_reports_action(has_unprocessed_reports: bool) -> dict[str, str]:
  """Describe the primary action for the ads reports page."""
  if has_unprocessed_reports:
    return {
      'label': 'Process Reports',
      'url': flask.url_for('web.admin_ads_reports_process'),
      'action': 'process',
    }
  return {
    'label': 'Request Reports',
    'url': flask.url_for('web.admin_ads_reports_request'),
    'action': 'request',
  }


def _build_ads_reports_view_model(
  *,
  selected_report_name: str,
  action_status_message: str | None = None,
  action_status_kind: str = 'info',
) -> dict[str, object]:
  """Build the ads reports template context for full-page and partial renders."""
  start_date, end_date, reports = _list_recent_amazon_ads_reports()
  selected_report = _select_amazon_ads_report(
    reports=reports,
    selected_report_name=selected_report_name,
  )
  selected_report_name = selected_report.report_name if selected_report else ""
  has_unprocessed_reports = _has_unprocessed_amazon_ads_reports(reports)
  return {
    'start_date':
    start_date.isoformat(),
    'end_date':
    end_date.isoformat(),
    'reports': [_serialize_amazon_ads_report(report) for report in reports],
    'selected_report_name':
    selected_report_name,
    'selected_cached_report_table':
    _build_cached_ads_report_table(selected_report),
    'has_unprocessed_reports':
    has_unprocessed_reports,
    'primary_action':
    _get_ads_reports_action(has_unprocessed_reports),
    'action_status_message':
    action_status_message or "",
    'action_status_kind':
    action_status_kind,
  }


def _get_ads_reports_selected_report_name() -> str:
  """Read the selected report name from JSON or form data."""
  payload = flask.request.get_json(silent=True)
  if isinstance(payload, dict):
    payload_dict = cast(dict[str, object], payload)
    selected_report_name = payload_dict.get('selected_report_name', '')
    return selected_report_name.strip() if isinstance(
      selected_report_name, str) else str(selected_report_name or '').strip()
  return (flask.request.form.get('selected_report_name') or '').strip()


def _render_ads_reports_content(view_model: dict[str, object]) -> str:
  """Render the replaceable ads reports content fragment."""
  return flask.render_template(
    'admin/_ads_reports_content.html',
    **view_model,
  )


def _ads_reports_partial_response(
  *,
  action: str,
  performed: bool,
  view_model: dict[str, object],
) -> flask.Response:
  """Return JSON for in-place ads reports updates."""
  return flask.jsonify({
    'action':
    action,
    'performed':
    performed,
    'has_unprocessed_reports':
    view_model['has_unprocessed_reports'],
    'selected_report_name':
    view_model['selected_report_name'],
    'content_html':
    _render_ads_reports_content(view_model),
  })


def _select_amazon_ads_report(
  *,
  reports: list[models.AmazonAdsReport],
  selected_report_name: str,
) -> models.AmazonAdsReport | None:
  """Return the selected report, defaulting to newest when not provided."""
  if not reports:
    return None
  if selected_report_name:
    for report in reports:
      if report.report_name == selected_report_name:
        return report
  return reports[0]


def _build_cached_ads_report_table(
  report: models.AmazonAdsReport | None, ) -> dict[str, object] | None:
  """Build a parsed report table for one selected report."""
  if report is None:
    return None

  raw_report_text = (report.raw_report_text or "").strip()
  if not raw_report_text:
    return None

  rows = amazon.parse_report_rows_text(
    report.report_name,
    raw_report_text,
    enable_logging=False,
  )
  row_count = len(rows)
  display_rows = rows[:_ADS_REPORT_TABLE_MAX_ROWS]
  columns = _collect_table_columns(display_rows)
  created_at_los_angeles = report.created_at.astimezone(_LOS_ANGELES_TIMEZONE)
  return {
    'report_name':
    report.report_name,
    'report_type_id':
    report.report_type_id,
    'profile_id':
    report.profile_id or "",
    'profile_country':
    report.profile_country or "",
    'start_date':
    report.start_date.isoformat(),
    'end_date':
    report.end_date.isoformat(),
    'created_at':
    created_at_los_angeles.strftime('%Y-%m-%d %H:%M:%S %Z'),
    'columns':
    columns,
    'rows': [{
      column: _format_ads_report_table_cell(row.get(column))
      for column in columns
    } for row in display_rows],
    'row_count':
    row_count,
    'truncated':
    row_count > len(display_rows),
  }


def _collect_table_columns(rows: list[dict[str, object]]) -> list[str]:
  """Collect and stabilize table columns from parsed JSON row dictionaries."""
  columns: list[str] = []
  seen_columns: set[str] = set()
  for row in rows:
    for key in row.keys():
      if key in seen_columns:
        continue
      seen_columns.add(key)
      columns.append(key)
  return columns


def _format_ads_report_table_cell(value: object) -> str:
  """Format a parsed report cell as readable text for HTML tables."""
  if value is None:
    return ""
  if isinstance(value, (dict, list)):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
  return str(value)


def _build_ads_stats_chart_data(
  *,
  stats_list: list[models.AmazonAdsDailyStats],
  start_date: datetime.date,
  end_date: datetime.date,
) -> dict[str, object]:
  """Aggregate campaign stats by day for charting."""
  daily_totals: dict[str, dict[str, float]] = {}
  daily_campaigns: dict[str, list[dict[str, object]]] = {}

  current_date = start_date
  while current_date <= end_date:
    date_key = current_date.isoformat()
    daily_totals[date_key] = {
      "impressions": 0.0,
      "clicks": 0.0,
      "cost": 0.0,
      "sales_usd": 0.0,
      "units_sold": 0.0,
      "gross_profit_before_ads_usd": 0.0,
      "gross_profit_usd": 0.0,
    }
    daily_campaigns[date_key] = []
    current_date += datetime.timedelta(days=1)

  for stat in stats_list:
    date_key = stat.date.isoformat()
    if date_key not in daily_totals:
      continue

    daily_entry = daily_totals[date_key]
    daily_entry["impressions"] = float(stat.impressions)
    daily_entry["clicks"] = float(stat.clicks)
    daily_entry["cost"] = stat.spend
    daily_entry["sales_usd"] = stat.total_attributed_sales_usd
    daily_entry["units_sold"] = float(stat.total_units_sold)
    daily_entry[
      "gross_profit_before_ads_usd"] = stat.gross_profit_before_ads_usd
    daily_entry["gross_profit_usd"] = stat.gross_profit_usd

    # Serialize campaign details for client-side filtering
    for campaign_stat in stat.campaigns_by_id.values():
      daily_campaigns[date_key].append(campaign_stat.to_dict())

  labels = list(daily_totals.keys())
  impressions = [int(daily_totals[label]["impressions"]) for label in labels]
  clicks = [int(daily_totals[label]["clicks"]) for label in labels]
  cost = [round(float(daily_totals[label]["cost"]), 2) for label in labels]
  sales_usd = [
    round(float(daily_totals[label]["sales_usd"]), 2) for label in labels
  ]
  units_sold = [int(daily_totals[label]["units_sold"]) for label in labels]
  gross_profit_before_ads_usd = [
    round(float(daily_totals[label]["gross_profit_before_ads_usd"]), 2)
    for label in labels
  ]
  gross_profit_usd = [
    round(float(daily_totals[label]["gross_profit_usd"]), 2)
    for label in labels
  ]

  return {
    "labels":
    labels,
    "impressions":
    impressions,
    "clicks":
    clicks,
    "cost":
    cost,
    "sales_usd":
    sales_usd,
    "units_sold":
    units_sold,
    "gross_profit_before_ads_usd":
    gross_profit_before_ads_usd,
    "gross_profit_usd":
    gross_profit_usd,
    "daily_campaigns":
    daily_campaigns,
    "total_impressions":
    sum(impressions),
    "total_clicks":
    sum(clicks),
    "total_cost":
    round(sum(cost), 2),
    "total_sales_usd":
    round(sum(sales_usd), 2),
    "total_units_sold":
    sum(units_sold),
    "total_gross_profit_before_ads_usd":
    round(sum(gross_profit_before_ads_usd), 2),
    "total_gross_profit_usd":
    round(sum(gross_profit_usd), 2),
  }


def _build_reconciled_click_date_chart_data(
  *,
  stats_list: list[models.AmazonAdsDailyStats],
  reconciled_stats_list: list[models.AmazonSalesReconciledDailyStats],
  start_date: datetime.date,
  end_date: datetime.date,
) -> dict[str, object]:
  """Build timeline-only chart data using reconciled ads click-date stats."""
  ads_by_date = {stat.date.isoformat(): stat for stat in stats_list}
  reconciled_by_date = {
    stat.date.isoformat(): stat
    for stat in reconciled_stats_list
  }

  labels: list[str] = []
  cost: list[float] = []
  gross_profit_before_ads_usd: list[float] = []
  gross_profit_usd: list[float] = []
  organic_profit_usd: list[float] = []
  poas: list[float] = []
  tpoas: list[float] = []

  current_date = start_date
  while current_date <= end_date:
    date_key = current_date.isoformat()
    labels.append(date_key)

    ads_stat = ads_by_date.get(date_key)
    reconciled_stat = reconciled_by_date.get(date_key)

    ads_cost = float(ads_stat.spend) if ads_stat is not None else 0.0
    ads_kenp_royalties = (float(ads_stat.kenp_royalties_usd)
                          if ads_stat is not None else 0.0)
    raw_gross_profit_before_ads = (float(ads_stat.gross_profit_before_ads_usd)
                                   if ads_stat is not None else 0.0)
    ads_click_date_product_profit = (float(
      reconciled_stat.ads_click_date_royalty_usd_est)
                                     if reconciled_stat is not None else 0.0)
    organic_product_profit = (float(reconciled_stat.organic_royalty_usd_est)
                              if reconciled_stat is not None else 0.0)
    organic_profit = (float(reconciled_stat.organic_royalty_usd_est)
                      if reconciled_stat is not None else 0.0)

    reconciled_gross_profit_before_ads = (ads_click_date_product_profit +
                                          ads_kenp_royalties)
    total_gross_profit = (reconciled_gross_profit_before_ads +
                          organic_product_profit - ads_cost)
    total_poas = ((raw_gross_profit_before_ads + organic_product_profit) /
                  ads_cost if ads_cost > 0 else 0.0)
    current_poas = (raw_gross_profit_before_ads /
                    ads_cost if ads_cost > 0 else 0.0)

    cost.append(round(ads_cost, 2))
    gross_profit_before_ads_usd.append(
      round(reconciled_gross_profit_before_ads, 2))
    gross_profit_usd.append(round(total_gross_profit, 2))
    organic_profit_usd.append(round(organic_profit, 2))
    poas.append(round(current_poas, 4))
    tpoas.append(round(total_poas, 4))
    current_date += datetime.timedelta(days=1)

  return {
    "labels":
    labels,
    "cost":
    cost,
    "gross_profit_before_ads_usd":
    gross_profit_before_ads_usd,
    "gross_profit_usd":
    gross_profit_usd,
    "organic_profit_usd":
    organic_profit_usd,
    "poas":
    poas,
    "tpoas":
    tpoas,
    "total_cost":
    round(sum(cost), 2),
    "total_gross_profit_before_ads_usd":
    round(sum(gross_profit_before_ads_usd), 2),
    "total_gross_profit_usd":
    round(sum(gross_profit_usd), 2),
    "total_organic_profit_usd":
    round(sum(organic_profit_usd), 2),
  }


def _iter_date_keys(
  start_date: datetime.date,
  end_date: datetime.date,
) -> list[str]:
  """Build inclusive ISO-date keys from start to end."""
  keys: list[str] = []
  current_date = start_date
  while current_date <= end_date:
    keys.append(current_date.isoformat())
    current_date += datetime.timedelta(days=1)
  return keys


def _build_reconciliation_debug_csv(
  *,
  stats_list: list[models.AmazonAdsDailyStats],
  kdp_stats_list: list[models.AmazonKdpDailyStats],
  reconciled_stats_list: list[models.AmazonSalesReconciledDailyStats],
  start_date: datetime.date,
  end_date: datetime.date,
) -> str:
  """Build a sectioned CSV with raw daily inputs and reconciliation outputs."""
  ads_by_date = {stat.date.isoformat(): stat for stat in stats_list}
  kdp_by_date = {stat.date.isoformat(): stat for stat in kdp_stats_list}
  reconciled_by_date = {
    stat.date.isoformat(): stat
    for stat in reconciled_stats_list
  }
  date_keys = _iter_date_keys(start_date, end_date)

  output = io.StringIO()
  writer = csv.writer(output)

  writer.writerow(["Section", "daily_overview"])
  writer.writerow([
    "Date",
    "ads_impressions",
    "ads_clicks",
    "ads_spend_usd",
    "ads_kenp_pages_read",
    "ads_kenp_royalties_usd",
    "ads_total_attributed_sales_usd",
    "ads_total_units_sold",
    "ads_gross_profit_before_ads_usd",
    "ads_gross_profit_usd",
    "kdp_total_units_sold",
    "kdp_kenp_pages_read",
    "kdp_total_royalties_usd",
    "kdp_total_print_cost_usd",
    "recon_is_settled",
    "recon_kdp_units_total",
    "recon_ads_click_date_units_total",
    "recon_ads_ship_date_units_total",
    "recon_unmatched_ads_click_date_units_total",
    "recon_organic_units_total",
    "recon_kdp_kenp_pages_read_total",
    "recon_ads_click_date_kenp_pages_read_total",
    "recon_ads_ship_date_kenp_pages_read_total",
    "recon_unmatched_ads_click_date_kenp_pages_read_total",
    "recon_organic_kenp_pages_read_total",
    "recon_kdp_sales_usd_total",
    "recon_ads_click_date_sales_usd_est",
    "recon_ads_ship_date_sales_usd_est",
    "recon_organic_sales_usd_est",
    "recon_kdp_royalty_usd_total",
    "recon_ads_click_date_royalty_usd_est",
    "recon_ads_ship_date_royalty_usd_est",
    "recon_organic_royalty_usd_est",
    "recon_kdp_print_cost_usd_total",
    "recon_ads_click_date_print_cost_usd_est",
    "recon_ads_ship_date_print_cost_usd_est",
    "recon_organic_print_cost_usd_est",
    "recon_by_asin_count",
    "recon_by_asin_country_count",
    "recon_unmatched_lot_count",
  ])
  for date_key in date_keys:
    ads_stat = ads_by_date.get(date_key)
    kdp_stat = kdp_by_date.get(date_key)
    reconciled_stat = reconciled_by_date.get(date_key)
    unmatched_lot_count = 0
    if reconciled_stat is not None:
      for country_map in (
          reconciled_stat.zzz_ending_unmatched_ads_lots_by_asin_country.values(
          )):
        for lots in country_map.values():
          unmatched_lot_count += len(lots)
    by_asin_country_count = 0
    if reconciled_stat is not None:
      by_asin_country_count = sum(
        len(country_map)
        for country_map in reconciled_stat.by_asin_country.values())
    writer.writerow([
      date_key,
      ads_stat.impressions if ads_stat is not None else 0,
      ads_stat.clicks if ads_stat is not None else 0,
      ads_stat.spend if ads_stat is not None else 0.0,
      ads_stat.kenp_pages_read if ads_stat is not None else 0,
      ads_stat.kenp_royalties_usd if ads_stat is not None else 0.0,
      ads_stat.total_attributed_sales_usd if ads_stat is not None else 0.0,
      ads_stat.total_units_sold if ads_stat is not None else 0,
      ads_stat.gross_profit_before_ads_usd if ads_stat is not None else 0.0,
      ads_stat.gross_profit_usd if ads_stat is not None else 0.0,
      kdp_stat.total_units_sold if kdp_stat is not None else 0,
      kdp_stat.kenp_pages_read if kdp_stat is not None else 0,
      kdp_stat.total_royalties_usd if kdp_stat is not None else 0.0,
      kdp_stat.total_print_cost_usd if kdp_stat is not None else 0.0,
      reconciled_stat.is_settled if reconciled_stat is not None else False,
      reconciled_stat.kdp_units_total if reconciled_stat is not None else 0,
      (reconciled_stat.ads_click_date_units_total
       if reconciled_stat is not None else 0),
      (reconciled_stat.ads_ship_date_units_total
       if reconciled_stat is not None else 0),
      (reconciled_stat.unmatched_ads_click_date_units_total
       if reconciled_stat is not None else 0),
      reconciled_stat.organic_units_total
      if reconciled_stat is not None else 0,
      (reconciled_stat.kdp_kenp_pages_read_total
       if reconciled_stat is not None else 0),
      (reconciled_stat.ads_click_date_kenp_pages_read_total
       if reconciled_stat is not None else 0),
      (reconciled_stat.ads_ship_date_kenp_pages_read_total
       if reconciled_stat is not None else 0),
      (reconciled_stat.unmatched_ads_click_date_kenp_pages_read_total
       if reconciled_stat is not None else 0),
      (reconciled_stat.organic_kenp_pages_read_total
       if reconciled_stat is not None else 0),
      reconciled_stat.kdp_sales_usd_total
      if reconciled_stat is not None else 0,
      (reconciled_stat.ads_click_date_sales_usd_est
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.ads_ship_date_sales_usd_est
       if reconciled_stat is not None else 0.0),
      reconciled_stat.organic_sales_usd_est
      if reconciled_stat is not None else 0,
      (reconciled_stat.kdp_royalty_usd_total
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.ads_click_date_royalty_usd_est
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.ads_ship_date_royalty_usd_est
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.organic_royalty_usd_est
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.kdp_print_cost_usd_total
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.ads_click_date_print_cost_usd_est
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.ads_ship_date_print_cost_usd_est
       if reconciled_stat is not None else 0.0),
      (reconciled_stat.organic_print_cost_usd_est
       if reconciled_stat is not None else 0.0),
      len(reconciled_stat.by_asin) if reconciled_stat is not None else 0,
      by_asin_country_count,
      unmatched_lot_count,
    ])

  writer.writerow([])
  writer.writerow(["Section", "ads_campaign_daily_rows"])
  writer.writerow([
    "Date",
    "campaign_id",
    "campaign_name",
    "impressions",
    "clicks",
    "spend_usd",
    "kenp_pages_read",
    "kenp_royalties_usd",
    "total_attributed_sales_usd",
    "total_units_sold",
    "gross_profit_before_ads_usd",
    "gross_profit_usd",
    "sale_items_count",
  ])
  for date_key in date_keys:
    ads_stat = ads_by_date.get(date_key)
    if ads_stat is None:
      continue
    for campaign_id in sorted(ads_stat.campaigns_by_id.keys()):
      campaign = ads_stat.campaigns_by_id[campaign_id]
      writer.writerow([
        date_key,
        campaign.campaign_id,
        campaign.campaign_name,
        campaign.impressions,
        campaign.clicks,
        campaign.spend,
        campaign.kenp_pages_read,
        campaign.kenp_royalties_usd,
        campaign.total_attributed_sales_usd,
        campaign.total_units_sold,
        campaign.gross_profit_before_ads_usd,
        campaign.gross_profit_usd,
        len(campaign.sale_items),
      ])

  writer.writerow([])
  writer.writerow(["Section", "ads_campaign_sale_items"])
  writer.writerow([
    "Date",
    "campaign_id",
    "country_code",
    "asin",
    "units_sold",
    "kenp_pages_read",
    "total_sales_usd",
    "total_profit_usd",
    "kenp_royalties_usd",
    "total_royalty_usd",
    "total_print_cost_usd",
    "unit_prices",
  ])
  for date_key in date_keys:
    ads_stat = ads_by_date.get(date_key)
    if ads_stat is None:
      continue
    for campaign_id in sorted(ads_stat.campaigns_by_id.keys()):
      campaign = ads_stat.campaigns_by_id[campaign_id]
      for asin in sorted(campaign.sale_items_by_asin_country.keys()):
        for country_code, sale_item in sorted(
            campaign.sale_items_by_asin_country[asin].items()):
          writer.writerow([
            date_key,
            campaign_id,
            country_code,
            sale_item.asin,
            sale_item.units_sold,
            sale_item.kenp_pages_read,
            sale_item.total_sales_usd,
            sale_item.total_profit_usd,
            sale_item.kenp_royalties_usd,
            sale_item.total_royalty_usd
            if sale_item.total_royalty_usd else 0.0,
            sale_item.total_print_cost_usd
            if sale_item.total_print_cost_usd else 0.0,
            "|".join(str(price) for price in sorted(sale_item.unit_prices)),
          ])

  writer.writerow([])
  writer.writerow(["Section", "kdp_sale_items"])
  writer.writerow([
    "Date",
    "country_code",
    "asin",
    "units_sold",
    "kenp_pages_read",
    "total_sales_usd",
    "total_profit_usd",
    "total_royalty_usd",
    "total_print_cost_usd",
    "unit_prices",
  ])
  for date_key in date_keys:
    kdp_stat = kdp_by_date.get(date_key)
    if kdp_stat is None:
      continue
    for asin in sorted(kdp_stat.sale_items_by_asin_country.keys()):
      for country_code, sale_item in sorted(
          kdp_stat.sale_items_by_asin_country[asin].items()):
        writer.writerow([
          date_key,
          country_code,
          sale_item.asin,
          sale_item.units_sold,
          sale_item.kenp_pages_read,
          sale_item.total_sales_usd,
          sale_item.total_profit_usd,
          sale_item.total_royalty_usd if sale_item.total_royalty_usd else 0.0,
          sale_item.total_print_cost_usd
          if sale_item.total_print_cost_usd else 0.0,
          "|".join(str(price) for price in sorted(sale_item.unit_prices)),
        ])

  writer.writerow([])
  writer.writerow(["Section", "reconciled_by_asin_country"])
  reconciled_units_headers = (
    "kdp_units ads_click_date_units ads_ship_date_units "
    "unmatched_ads_click_date_units organic_units "
    "kdp_kenp_pages_read ads_click_date_kenp_pages_read "
    "ads_ship_date_kenp_pages_read unmatched_ads_click_date_kenp_pages_read "
    "organic_kenp_pages_read").split()
  reconciled_money_headers = (
    "kdp_sales_usd ads_click_date_sales_usd_est ads_ship_date_sales_usd_est "
    "organic_sales_usd_est kdp_royalty_usd ads_click_date_royalty_usd_est "
    "ads_ship_date_royalty_usd_est organic_royalty_usd_est "
    "kdp_print_cost_usd ads_click_date_print_cost_usd_est "
    "ads_ship_date_print_cost_usd_est organic_print_cost_usd_est").split()
  writer.writerow([
    "Date",
    "asin",
    "country_code",
    *reconciled_units_headers,
    *reconciled_money_headers,
  ])
  for date_key in date_keys:
    reconciled_stat = reconciled_by_date.get(date_key)
    if reconciled_stat is None:
      continue
    for asin in sorted(reconciled_stat.by_asin_country.keys()):
      country_map = reconciled_stat.by_asin_country[asin]
      for country_code in sorted(country_map.keys()):
        asin_stats = country_map[country_code]
        writer.writerow([
          date_key,
          asin,
          country_code,
          asin_stats.kdp_units,
          asin_stats.ads_click_date_units,
          asin_stats.ads_ship_date_units,
          asin_stats.unmatched_ads_click_date_units,
          asin_stats.organic_units,
          asin_stats.kdp_kenp_pages_read,
          asin_stats.ads_click_date_kenp_pages_read,
          asin_stats.ads_ship_date_kenp_pages_read,
          asin_stats.unmatched_ads_click_date_kenp_pages_read,
          asin_stats.organic_kenp_pages_read,
          asin_stats.kdp_sales_usd,
          asin_stats.ads_click_date_sales_usd_est,
          asin_stats.ads_ship_date_sales_usd_est,
          asin_stats.organic_sales_usd_est,
          asin_stats.kdp_royalty_usd,
          asin_stats.ads_click_date_royalty_usd_est,
          asin_stats.ads_ship_date_royalty_usd_est,
          asin_stats.organic_royalty_usd_est,
          asin_stats.kdp_print_cost_usd,
          asin_stats.ads_click_date_print_cost_usd_est,
          asin_stats.ads_ship_date_print_cost_usd_est,
          asin_stats.organic_print_cost_usd_est,
        ])

  writer.writerow([])
  writer.writerow(
    ["Section", "reconciled_ending_unmatched_ads_lots_by_asin_country"])
  writer.writerow([
    "Date",
    "asin",
    "country_code",
    "purchase_date",
    "units_remaining",
    "kenp_pages_remaining",
  ])
  for date_key in date_keys:
    reconciled_stat = reconciled_by_date.get(date_key)
    if reconciled_stat is None:
      continue
    for asin in sorted(
        reconciled_stat.zzz_ending_unmatched_ads_lots_by_asin_country):
      country_map = reconciled_stat.zzz_ending_unmatched_ads_lots_by_asin_country[
        asin]
      for country_code in sorted(country_map.keys()):
        lots = country_map[country_code]
        for lot in lots:
          writer.writerow([
            date_key,
            asin,
            country_code,
            lot.purchase_date.isoformat(),
            lot.units_remaining,
            lot.kenp_pages_remaining,
          ])

  return output.getvalue().strip()
