"""Tests for joke_notes_sheet_operations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from common import joke_notes_sheet_operations, models


def _make_joke(
  *,
  key: str | None,
  fraction: float | None,
) -> models.PunnyJoke:
  joke = models.PunnyJoke(
    key=key,
    setup_text="Setup",
    punchline_text="Punchline",
  )
  joke.num_saved_users_fraction = fraction
  return joke


def test_generate_file_stem_sorts_joke_ids():
  stem_a = joke_notes_sheet_operations._generate_file_stem(
    ["b", "a"],
    quality=80,
  )
  stem_b = joke_notes_sheet_operations._generate_file_stem(
    ["a", "b"],
    quality=80,
  )
  stem_c = joke_notes_sheet_operations._generate_file_stem(
    ["a", "b"],
    quality=90,
  )

  assert stem_a == stem_b
  assert stem_a != stem_c


def test_average_saved_users_fraction_handles_empty():
  assert joke_notes_sheet_operations._average_saved_users_fraction([]) == 0.0


def test_average_saved_users_fraction_handles_invalid_values():
  jokes = [
    _make_joke(key="j1", fraction=0.2),
    _make_joke(key="j2", fraction=None),
    _make_joke(key="j3", fraction=0.0),
  ]
  jokes[2].num_saved_users_fraction = "bad"

  avg = joke_notes_sheet_operations._average_saved_users_fraction(jokes)

  assert avg == pytest.approx(0.2 / 3)


def test_ensure_joke_notes_sheet_averages_and_skips_missing_keys(monkeypatch):
  jokes = [
    _make_joke(key="joke1", fraction=0.2),
    _make_joke(key=None, fraction=0.6),
  ]
  gcs_calls: list[str] = []

  def _fake_exists(uri: str) -> bool:
    gcs_calls.append(uri)
    return True

  def _fake_upsert(sheet: models.JokeSheet) -> models.JokeSheet:
    sheet.key = "sheet-1"
    return sheet

  monkeypatch.setattr(joke_notes_sheet_operations.cloud_storage,
                      "gcs_file_exists", _fake_exists)
  monkeypatch.setattr(joke_notes_sheet_operations.firestore,
                      "upsert_joke_sheet", _fake_upsert)
  mock_create = MagicMock()
  monkeypatch.setattr(joke_notes_sheet_operations,
                      "_create_joke_notes_sheet_image", mock_create)

  result = joke_notes_sheet_operations.ensure_joke_notes_sheet(jokes)

  expected_stem = joke_notes_sheet_operations._generate_file_stem(
    ["joke1"],
    quality=80,
  )
  expected_pdf = (
    f"{joke_notes_sheet_operations._PDF_DIR_GCS_URI}/{expected_stem}.pdf")
  expected_image = (
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}.png")

  assert result.key == "sheet-1"
  assert result.joke_ids == ["joke1"]
  assert result.avg_saved_users_fraction == pytest.approx(0.4)
  assert gcs_calls == [expected_pdf, expected_image]
  assert mock_create.call_count == 0
