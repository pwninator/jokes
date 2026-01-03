"""Admin dashboard + stats routes."""

from __future__ import annotations

import flask

from common import amazon_redirect
from functions import auth_helpers
from services import firestore
from web.routes import web_bp
from web.routes.redirects import amazon_redirect_view_models
from web.utils import stats as stats_utils


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
  retention_buckets = set()
  for day_data in retention_matrix.values():
    retention_buckets.update(day_data.keys())
  sorted_ret_buckets = sorted(list(retention_buckets),
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
