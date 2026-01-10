"""Tests for admin dashboard routes."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

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
  assert 'site-header--visible' in html.lower()
  assert 'addEventListener' in html
