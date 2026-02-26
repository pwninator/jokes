"""Admin dashboard + stats routes."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

import flask
from common import amazon_redirect
from common import models
from firebase_functions import logger
from functions import auth_helpers
from services import amazon_kdp
from services import firestore
from web.routes import web_bp
from web.routes.redirects import amazon_redirect_view_models
from web.utils import stats as stats_utils

_ADS_STATS_LOOKBACK_DAYS = 30
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
  chart_data = _build_ads_stats_chart_data(
    stats_list=stats_list,
    start_date=start_date,
    end_date=end_date,
  )
  return flask.render_template(
    'admin/ads_stats.html',
    site_name='Snickerdoodle',
    chart_data=chart_data,
    start_date=start_date.isoformat(),
    end_date=end_date.isoformat(),
  )


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
  except amazon_kdp.AmazonKdpError as exc:
    return flask.jsonify({'error': str(exc)}), 400
  except Exception as exc:
    logger.error('Failed to upload KDP daily stats', exc_info=exc)
    return flask.jsonify({'error': 'Failed to process KDP report'}), 500

  return flask.jsonify({'days_saved': len(stats)})


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
    daily_entry["gross_profit_before_ads_usd"] = stat.gross_profit_before_ads_usd
    daily_entry["gross_profit_usd"] = stat.gross_profit_usd

    # Serialize campaign details for client-side filtering
    for campaign_stat in stat.campaigns_by_id.values():
      daily_campaigns[date_key].append(campaign_stat.to_dict())

  labels = list(daily_totals.keys())
  impressions = [int(daily_totals[label]["impressions"]) for label in labels]
  clicks = [int(daily_totals[label]["clicks"]) for label in labels]
  cost = [round(float(daily_totals[label]["cost"]), 2) for label in labels]
  sales_usd = [round(float(daily_totals[label]["sales_usd"]), 2) for label in labels]
  units_sold = [int(daily_totals[label]["units_sold"]) for label in labels]
  gross_profit_before_ads_usd = [
    round(float(daily_totals[label]["gross_profit_before_ads_usd"]), 2)
    for label in labels
  ]
  gross_profit_usd = [
    round(float(daily_totals[label]["gross_profit_usd"]), 2) for label in labels
  ]

  return {
    "labels": labels,
    "impressions": impressions,
    "clicks": clicks,
    "cost": cost,
    "sales_usd": sales_usd,
    "units_sold": units_sold,
    "gross_profit_before_ads_usd": gross_profit_before_ads_usd,
    "gross_profit_usd": gross_profit_usd,
    "daily_campaigns": daily_campaigns,
    "total_impressions": sum(impressions),
    "total_clicks": sum(clicks),
    "total_cost": round(sum(cost), 2),
    "total_sales_usd": round(sum(sales_usd), 2),
    "total_units_sold": sum(units_sold),
    "total_gross_profit_before_ads_usd": round(sum(gross_profit_before_ads_usd),
                                               2),
    "total_gross_profit_usd": round(sum(gross_profit_usd), 2),
  }
