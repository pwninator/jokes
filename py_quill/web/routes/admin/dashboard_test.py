"""Tests for admin dashboard routes."""

from __future__ import annotations

import datetime
import io
from unittest.mock import Mock

import pytest

from common import models
from functions import auth_helpers
from services import firestore as firestore_service
from web.app import app
from web.routes.admin import dashboard as dashboard_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def test_admin_stats_page_loads(monkeypatch):
  """Test the stats page loads and renders charts with data."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  # Mock Firestore query
  mock_db = Mock()
  mock_collection = Mock()
  mock_query = Mock()

  # Setup mock stats docs
  doc1 = Mock()
  doc1.id = "20230101"
  doc1.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "10": 5,
      "20": 2
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "5": {
        "50": 3
      }
    }
  }

  doc2 = Mock()
  doc2.id = "20230102"
  doc2.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "10": 6,
      "20": 3
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "5": {
        "50": 4
      }
    }
  }

  # Mock query returning doc2 then doc1 (Desc order)
  mock_query.limit.return_value.stream.return_value = [doc2, doc1]
  mock_collection.order_by.return_value = mock_query
  mock_db.collection.return_value = mock_collection

  monkeypatch.setattr(firestore_service, "db", lambda: mock_db)

  with app.test_client() as client:
    resp = client.get('/admin/stats')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  # Check for canvas elements
  assert '<canvas id="dauChart"></canvas>' in html
  assert '<canvas id="retentionChart"></canvas>' in html

  # Check for data injection (basic check)
  assert 'dauData' in html
  assert 'retentionData' in html
  assert '20230101' in html
  assert '20230102' in html

  # Verify processing logic for Chart.js
  # We expect buckets 10-19 and 20-29 for DAU after bucketing
  assert '"label": "10-19 jokes"' in html
  assert '"label": "20-29 jokes"' in html


def test_admin_stats_rebuckets_and_colors(monkeypatch):
  """Admin stats view rebuckets raw data and assigns gradient colors."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  class _FixedDate(datetime.date):

    @classmethod
    def today(cls):
      return cls(2026, 2, 20)

  monkeypatch.setattr(dashboard_routes.datetime, "date", _FixedDate)

  captured: dict = {}

  def _fake_render(template_name, **context):
    captured["template"] = template_name
    captured.update(context)
    return "OK"

  monkeypatch.setattr(dashboard_routes.flask, "render_template", _fake_render)

  # Mock Firestore query with raw (unbucketed) counts
  mock_db = Mock()
  mock_collection = Mock()
  mock_query = Mock()

  doc1 = Mock()
  doc1.id = "20230101"
  doc1.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "0": 1,
      "1": 2,
      "12": 3,
      "100": 4
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "2": {
        "1": 1,
        "12": 2,
        "150": 3
      },
      "9": {
        "1": 4
      },
      "15": {
        "12": 2
      },
    }
  }

  doc2 = Mock()
  doc2.id = "20230102"
  doc2.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "0": 1,
      "1": 2,
      "12": 3,
      "100": 4
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "2": {
        "1": 1,
        "12": 2,
        "150": 3
      },
      "9": {
        "1": 4
      },
      "15": {
        "12": 2
      },
    }
  }

  mock_query.limit.return_value.stream.return_value = [doc2, doc1]
  mock_collection.order_by.return_value = mock_query
  mock_db.collection.return_value = mock_collection
  monkeypatch.setattr(firestore_service, "db", lambda: mock_db)

  with app.test_client() as client:
    resp = client.get('/admin/stats')

  assert resp.status_code == 200
  assert captured["template"] == 'admin/stats.html'

  dau_data = captured["dau_data"]
  assert dau_data["labels"] == ["20230101", "20230102"]
  dau_labels = [ds["label"] for ds in dau_data["datasets"]]
  assert dau_labels == [
    "0 jokes", "1-9 jokes", "10-19 jokes", "100-149 jokes", "150-199 jokes"
  ]
  # Order places highest buckets at the bottom of the stack (most negative drawn first)
  orders = [ds["order"] for ds in dau_data["datasets"]]
  assert orders == [0, -1, -2, -3, -4]
  # Buckets aggregated chronologically (doc1 then doc2)
  assert dau_data["datasets"][0]["data"] == [1, 1]  # 0 bucket
  assert dau_data["datasets"][1]["data"] == [2, 2]  # 1-9 bucket
  assert dau_data["datasets"][2]["data"] == [3, 3]  # 10-19 bucket
  assert dau_data["datasets"][3]["data"] == [4, 4]  # 100-149 bucket
  assert dau_data["datasets"][4]["data"] == [0,
                                             0]  # 150-199 bucket (not in DAU)
  # Color map: zero bucket gray, others colored (not gray)
  assert dau_data["datasets"][0]["backgroundColor"] == "#9e9e9e"
  non_zero_colors = {ds["backgroundColor"] for ds in dau_data["datasets"][1:]}
  assert "#9e9e9e" not in non_zero_colors

  retention_data = captured["retention_data"]
  assert retention_data["labels"] == ["2", "8-14", "15-21"]
  retention_labels = [ds["label"] for ds in retention_data["datasets"]]
  assert retention_labels == ["1-9 jokes", "10-19 jokes", "150-199 jokes"]

  # Percentages: counts 1,2,3 => totals 6
  def _dataset(label):
    return next(d for d in retention_data["datasets"] if d["label"] == label)

  # Day 2: totals = 6 (1,2,3)
  assert _dataset("1-9 jokes")["data"][0] == pytest.approx(16.6666, rel=1e-3)
  assert _dataset("10-19 jokes")["data"][0] == pytest.approx(33.3333, rel=1e-3)
  assert _dataset("150-199 jokes")["data"][0] == pytest.approx(50.0, rel=1e-3)
  # Day 8-14: totals = 4 (all in 1-9)
  assert _dataset("1-9 jokes")["data"][1] == pytest.approx(100.0, rel=1e-3)
  assert _dataset("10-19 jokes")["data"][1] == pytest.approx(0.0, rel=1e-3)
  assert _dataset("150-199 jokes")["data"][1] == pytest.approx(0.0, rel=1e-3)
  # Day 15-21: totals = 2 (all in 10-19)
  assert _dataset("1-9 jokes")["data"][2] == pytest.approx(0.0, rel=1e-3)
  assert _dataset("10-19 jokes")["data"][2] == pytest.approx(100.0, rel=1e-3)
  assert _dataset("150-199 jokes")["data"][2] == pytest.approx(0.0, rel=1e-3)


def test_admin_dashboard_includes_sticky_header_script(monkeypatch):
  """Test that admin dashboard includes sticky header scroll script."""
  _mock_admin_session(monkeypatch)

  # Act
  with app.test_client() as client:
    resp = client.get('/admin')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'site-header' in html
  # Verify scroll detection script is present
  assert 'scroll' in html.lower()
  assert 'addEventListener' in html
  # Verify dock/floating state classes are referenced
  assert 'site-header--docked' in html.lower()
  assert 'site-header--floating' in html.lower()
  assert 'site-header--visible' in html.lower()
  # Verify 1000px scroll threshold logic
  assert '1000' in html or 'float_scroll_threshold' in html.lower()


def test_admin_dashboard_includes_image_prompt_tuner_link(monkeypatch):
  """Admin dashboard includes the image prompt tuner tile."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '/admin/image-prompt-tuner' in html
  assert 'Image Prompt Tuner' in html


def test_admin_dashboard_includes_joke_media_generator_link(monkeypatch):
  """Admin dashboard includes the joke media generator tile."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '/admin/joke-media-generator' in html
  assert 'Joke Media Generator' in html


def test_admin_dashboard_includes_character_animator_link(monkeypatch):
  """Admin dashboard includes the character animator tile."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '/admin/character-animator' in html
  assert 'Character Animator' in html


def test_admin_ads_stats_page_aggregates_daily_stats(monkeypatch):
  """Ads stats page uses daily stats rows and fills missing dates."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)
  monkeypatch.setattr(dashboard_routes, "_today_in_los_angeles",
                      lambda: datetime.date(2026, 2, 20))

  captured: dict = {}

  def _fake_render(template_name, **context):
    captured["template"] = template_name
    captured.update(context)
    return "OK"

  monkeypatch.setattr(dashboard_routes.flask, "render_template", _fake_render)

  call_args: dict = {}

  def _fake_list_stats(*, start_date, end_date):
    call_args["start_date"] = start_date
    call_args["end_date"] = end_date
    return [
      models.AmazonAdsDailyStats(
        date=datetime.date(2026, 2, 19),
        impressions=175,
        clicks=15,
        spend=25.0,
        total_attributed_sales_usd=37.0,
        gross_profit_before_ads_usd=60.0,
        gross_profit_usd=35.0,
      ),
      models.AmazonAdsDailyStats(
        date=datetime.date(2026, 2, 17),
        impressions=30,
        clicks=3,
        spend=4.50,
        total_attributed_sales_usd=9.00,
        gross_profit_before_ads_usd=9.0,
        gross_profit_usd=4.5,
      ),
    ]

  monkeypatch.setattr(
    firestore_service,
    "list_amazon_ads_daily_stats",
    _fake_list_stats,
  )

  with app.test_client() as client:
    resp = client.get('/admin/ads-stats')

  assert resp.status_code == 200
  assert captured["template"] == "admin/ads_stats.html"
  assert call_args["start_date"] == datetime.date(2026, 1, 22)
  assert call_args["end_date"] == datetime.date(2026, 2, 20)
  assert captured["start_date"] == "2026-01-22"
  assert captured["end_date"] == "2026-02-20"

  chart_data = captured["chart_data"]
  assert len(chart_data["labels"]) == 30
  assert chart_data["labels"][0] == "2026-01-22"
  assert chart_data["labels"][-1] == "2026-02-20"
  idx_0217 = chart_data["labels"].index("2026-02-17")
  idx_0219 = chart_data["labels"].index("2026-02-19")
  assert chart_data["impressions"][idx_0217] == 30
  assert chart_data["impressions"][idx_0219] == 175
  assert chart_data["clicks"][idx_0217] == 3
  assert chart_data["clicks"][idx_0219] == 15
  assert chart_data["cost"][idx_0217] == 4.5
  assert chart_data["cost"][idx_0219] == 25.0
  assert chart_data["sales_usd"][idx_0217] == 9.0
  assert chart_data["sales_usd"][idx_0219] == 37.0
  assert chart_data["gross_profit_before_ads_usd"][idx_0217] == 9.0
  assert chart_data["gross_profit_before_ads_usd"][idx_0219] == 60.0
  assert chart_data["gross_profit_usd"][idx_0217] == 4.5
  assert chart_data["gross_profit_usd"][idx_0219] == 35.0

  # Verify totals
  assert chart_data["total_impressions"] == 205
  assert chart_data["total_clicks"] == 18
  assert chart_data["total_cost"] == 29.5
  assert chart_data["total_sales_usd"] == 46.0
  assert chart_data["total_gross_profit_before_ads_usd"] == 69.0
  assert chart_data["total_gross_profit_usd"] == 39.5


def test_admin_dashboard_includes_ads_stats_link(monkeypatch):
  """Admin dashboard includes the ads stats tile."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '/admin/ads-stats' in html
  assert 'Ads Stats' in html


def test_admin_ads_stats_page_includes_nav_link(monkeypatch):
  """Ads stats page renders the admin top-nav link."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(
    firestore_service,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [],
  )

  with app.test_client() as client:
    resp = client.get('/admin/ads-stats')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'href="/admin/ads-stats"' in html
  assert 'Ads Stats' in html


def test_admin_ads_stats_page_includes_refresh_link(monkeypatch):
  """Ads stats page includes refresh link to the Cloud Function URL."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(
    firestore_service,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [],
  )

  with app.test_client() as client:
    resp = client.get('/admin/ads-stats')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert ('href="https://auto-ads-stats-http-uqdkqas7gq-uc.a.run.app/"'
          in html)
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert 'Back to Dashboard' not in html


def test_admin_ads_stats_page_chart_layout_and_order(monkeypatch):
  """Ads stats page renders combined chart layout in the expected order."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(
    firestore_service,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [],
  )

  with app.test_client() as client:
    resp = client.get('/admin/ads-stats')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'id="stat-sales"' not in html
  assert "<h3>Sales</h3>" not in html

  assert "<h3>Profit</h3>" in html
  assert "<h3>POAS</h3>" in html
  assert "<h3>Gross Profit</h3>" not in html
  assert "<h3>Cost / Gross Profit Before Ads</h3>" not in html
  assert '/static/js/ads_stats.js' in html
  assert 'window.initAdsStatsPage' in html
  assert 'chartData:' in html
  assert 'id="modeSelector"' in html
  assert 'id="stat-ctr"' in html
  assert '<canvas id="ctrChart"></canvas>' in html
  assert '<option value="Timeline">Timeline</option>' in html
  assert '<option value="Days of Week">Days of Week</option>' in html
  assert 'class="ads-stats-filters-row"' in html
  assert "flex-wrap: wrap;" in html

  profit_pos = html.find("<h3>Profit</h3>")
  poas_pos = html.find("<h3>POAS</h3>")
  cpc_and_cr_pos = html.find("<h3>CPC / Conversion Rate</h3>")
  ctr_pos = html.find("<h3>CTR</h3>")
  impressions_and_clicks_pos = html.find("<h3>Impressions / Clicks</h3>")

  assert profit_pos != -1
  assert poas_pos != -1
  assert cpc_and_cr_pos != -1
  assert ctr_pos != -1
  assert impressions_and_clicks_pos != -1
  assert "<h3>Impressions</h3>" not in html
  assert "<h3>Clicks</h3>" not in html
  assert '<canvas id="impressionsAndClicksChart"></canvas>' in html
  assert profit_pos < poas_pos
  assert poas_pos < cpc_and_cr_pos
  assert cpc_and_cr_pos < ctr_pos
  assert ctr_pos < impressions_and_clicks_pos


def test_admin_ads_stats_filtering(monkeypatch):
  """Ads stats page includes detailed campaign data for client-side filtering."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  captured: dict = {}

  def _fake_render(template_name, **context):
    captured["template"] = template_name
    captured.update(context)
    return "OK"

  monkeypatch.setattr(dashboard_routes.flask, "render_template", _fake_render)

  # Setup mock stats with nested campaigns
  stats = models.AmazonAdsDailyStats(
    date=datetime.date(2026, 2, 20),
    impressions=100,
    clicks=10,
    spend=5.0,
    total_attributed_sales_usd=20.0,
    total_units_sold=2,
    gross_profit_before_ads_usd=30.0,
    gross_profit_usd=10.0,
  )

  # Add campaign details
  stats.campaigns_by_id["c1"] = models.AmazonAdsDailyCampaignStats(
    campaign_id="c1",
    campaign_name="Campaign A",
    date=datetime.date(2026, 2, 20),
    impressions=60,
    clicks=6,
    spend=3.0,
    total_attributed_sales_usd=12.0,
    total_units_sold=1,
    gross_profit_before_ads_usd=18.0,
    gross_profit_usd=6.0,
  )
  stats.campaigns_by_id["c2"] = models.AmazonAdsDailyCampaignStats(
    campaign_id="c2",
    campaign_name="Campaign B",
    date=datetime.date(2026, 2, 20),
    impressions=40,
    clicks=4,
    spend=2.0,
    total_attributed_sales_usd=8.0,
    total_units_sold=1,
    gross_profit_before_ads_usd=12.0,
    gross_profit_usd=4.0,
  )

  monkeypatch.setattr(
    firestore_service,
    "list_amazon_ads_daily_stats",
    lambda *, start_date, end_date: [stats],
  )

  with app.test_client() as client:
    resp = client.get('/admin/ads-stats')

  assert resp.status_code == 200
  chart_data = captured["chart_data"]

  # Verify daily campaigns are serialized
  daily_campaigns = chart_data["daily_campaigns"]
  assert "2026-02-20" in daily_campaigns
  campaign_list = daily_campaigns["2026-02-20"]
  assert len(campaign_list) == 2

  # Verify campaign A details
  camp_a = next(c for c in campaign_list if c["campaign_name"] == "Campaign A")
  assert camp_a["impressions"] == 60
  assert camp_a["clicks"] == 6
  assert camp_a["spend"] == 3.0
  assert camp_a["total_units_sold"] == 1

  # Verify top-level aggregation includes units_sold
  assert chart_data["total_units_sold"] == 2

  # Find index of the stats date
  date_idx = chart_data["labels"].index("2026-02-20")
  assert chart_data["units_sold"][date_idx] == 2


def test_admin_ads_stats_upload_kdp_success(monkeypatch):
  """KDP upload route parses and persists daily stats."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  parsed_stats = [
    models.AmazonKdpDailyStats(date=datetime.date(2026, 2, 25)),
    models.AmazonKdpDailyStats(date=datetime.date(2026, 2, 24)),
  ]

  parse_mock = Mock(return_value=parsed_stats)
  upsert_mock = Mock(return_value=parsed_stats)
  reconcile_mock = Mock(return_value={"reconciled_days": 14})
  monkeypatch.setattr(dashboard_routes.amazon_kdp, "parse_kdp_xlsx",
                      parse_mock)
  monkeypatch.setattr(
    firestore_service,
    "upsert_amazon_kdp_daily_stats",
    upsert_mock,
  )
  monkeypatch.setattr(
    dashboard_routes.amazon_sales_reconciliation,
    "reconcile_daily_sales",
    reconcile_mock,
  )

  with app.test_client() as client:
    resp = client.post(
      "/admin/ads-stats/upload-kdp",
      data={"file": (io.BytesIO(b"fake xlsx"), "report.xlsx")},
      content_type="multipart/form-data",
    )

  assert resp.status_code == 200
  assert resp.get_json() == {"days_saved": 2}
  parse_mock.assert_called_once()
  upsert_mock.assert_called_once_with(parsed_stats)
  reconcile_mock.assert_called_once_with(
    earliest_changed_date=datetime.date(2026, 2, 24))


def test_admin_ads_stats_upload_kdp_missing_file_returns_400(monkeypatch):
  """KDP upload route requires a file."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  with app.test_client() as client:
    resp = client.post(
      "/admin/ads-stats/upload-kdp",
      data={},
      content_type="multipart/form-data",
    )

  assert resp.status_code == 400
  assert resp.get_json() == {"error": "Missing uploaded file"}


def test_admin_ads_stats_upload_kdp_parse_error_returns_400(monkeypatch):
  """KDP upload route surfaces parse errors as 400."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  monkeypatch.setattr(
    dashboard_routes.amazon_kdp,
    "parse_kdp_xlsx",
    Mock(side_effect=dashboard_routes.amazon_kdp.AmazonKdpError("bad report")),
  )

  with app.test_client() as client:
    resp = client.post(
      "/admin/ads-stats/upload-kdp",
      data={"file": (io.BytesIO(b"broken"), "report.xlsx")},
      content_type="multipart/form-data",
    )

  assert resp.status_code == 400
  assert resp.get_json() == {"error": "bad report"}
