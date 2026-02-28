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
    branded=True,
  )
  stem_b = joke_notes_sheet_operations._generate_file_stem(
    ["a", "b"],
    quality=80,
    branded=True,
  )
  stem_c = joke_notes_sheet_operations._generate_file_stem(
    ["a", "b"],
    quality=90,
    branded=True,
  )
  stem_d = joke_notes_sheet_operations._generate_file_stem(
    ["a", "b"],
    quality=80,
    branded=False,
  )

  assert stem_a == stem_b
  assert stem_a != stem_c
  assert stem_a != stem_d


def test_average_saved_users_fraction_handles_empty():
  assert joke_notes_sheet_operations.average_saved_users_fraction([]) == 0.0


def test_average_saved_users_fraction_handles_invalid_values():
  jokes = [
    _make_joke(key="j1", fraction=0.2),
    _make_joke(key="j2", fraction=None),
    _make_joke(key="j3", fraction=0.0),
  ]
  jokes[2].num_saved_users_fraction = "bad"

  avg = joke_notes_sheet_operations.average_saved_users_fraction(jokes)

  assert avg == pytest.approx(0.2 / 3)


def test_chunk_jokes_for_sheet_prefers_six_page_batches():
  jokes = [_make_joke(key=f"j{i}", fraction=0.1) for i in range(20)]

  pages = joke_notes_sheet_operations._chunk_jokes_for_sheet(jokes,
                                                             branded=True)

  assert [len(page_jokes) for page_jokes, _, _ in pages] == [6, 6, 6, 2]
  assert [template_url for _, template_url, _ in pages] == [
    joke_notes_sheet_operations._JOKE_NOTES_BRANDED6_URL,
    joke_notes_sheet_operations._JOKE_NOTES_BRANDED6_URL,
    joke_notes_sheet_operations._JOKE_NOTES_BRANDED6_URL,
    joke_notes_sheet_operations._JOKE_NOTES_BRANDED5_URL,
  ]
  assert [max_jokes for _, _, max_jokes in pages] == [6, 6, 6, 5]


def test_chunk_jokes_for_sheet_uses_only_six_page_batches_when_even():
  jokes = [_make_joke(key=f"j{i}", fraction=0.1) for i in range(12)]

  pages = joke_notes_sheet_operations._chunk_jokes_for_sheet(jokes,
                                                             branded=True)

  assert [len(page_jokes) for page_jokes, _, _ in pages] == [6, 6]
  assert [template_url for _, template_url, _ in pages] == [
    joke_notes_sheet_operations._JOKE_NOTES_BRANDED6_URL,
    joke_notes_sheet_operations._JOKE_NOTES_BRANDED6_URL,
  ]


def test_chunk_jokes_for_sheet_uses_unbranded_templates_when_requested():
  jokes = [_make_joke(key=f"j{i}", fraction=0.1) for i in range(8)]

  pages = joke_notes_sheet_operations._chunk_jokes_for_sheet(jokes,
                                                             branded=False)

  assert [template_url for _, template_url, _ in pages] == [
    joke_notes_sheet_operations._JOKE_NOTES_UNBRANDED6_URL,
    joke_notes_sheet_operations._JOKE_NOTES_UNBRANDED5_URL,
  ]


@pytest.mark.parametrize(
  ("joke_count", "expected_page_count"),
  [
    (0, 1),
    (1, 1),
    (5, 1),
    (6, 1),
    (7, 2),
    (11, 2),
    (12, 2),
    (20, 4),
  ],
)
def test_get_joke_notes_sheet_page_count(joke_count: int,
                                         expected_page_count: int):
  assert joke_notes_sheet_operations._get_joke_notes_sheet_page_count(
    joke_count) == expected_page_count


def test_build_page_image_gcs_uris_keeps_first_page_unsuffixed():
  stem = "sheet-stem"

  page_uris = joke_notes_sheet_operations._build_page_image_gcs_uris(stem, 20)

  assert page_uris == [
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{stem}.png",
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{stem}_2.png",
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{stem}_3.png",
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{stem}_4.png",
  ]


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
                      "_create_joke_notes_sheet_images", mock_create)

  result = joke_notes_sheet_operations.ensure_joke_notes_sheet(jokes)

  expected_stem = joke_notes_sheet_operations._generate_file_stem(
    ["joke1"],
    quality=80,
    branded=True,
  )
  expected_pdf = (
    f"{joke_notes_sheet_operations._PDF_DIR_GCS_URI}/{expected_stem}.pdf")
  expected_image = (
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}.png")

  assert result.key == "sheet-1"
  assert result.joke_str_hash == expected_stem
  assert result.joke_ids == ["joke1"]
  assert result.avg_saved_users_fraction == pytest.approx(0.4)
  assert gcs_calls == [expected_pdf, expected_image]
  assert result.image_gcs_uris == [expected_image]
  assert mock_create.call_count == 0


def test_ensure_joke_notes_sheet_uploads_all_page_images_and_pdf(monkeypatch):
  jokes = [_make_joke(key=f"joke{i}", fraction=0.1) for i in range(20)]
  uploaded: list[tuple[str, str]] = []
  created_pdf_images: list[object] = []

  def _fake_exists(_uri: str) -> bool:
    return False

  def _fake_upload(*, gcs_uri: str, content_type: str, **_kwargs):
    uploaded.append((gcs_uri, content_type))

  def _fake_create_pdf(images, quality: int):
    created_pdf_images.extend(images)
    assert quality == 80
    return b"pdf-bytes"

  def _fake_upsert(sheet: models.JokeSheet) -> models.JokeSheet:
    sheet.key = "sheet-20"
    return sheet

  page_images = [MagicMock(name=f"page-{i}") for i in range(4)]

  monkeypatch.setattr(joke_notes_sheet_operations.cloud_storage,
                      "gcs_file_exists", _fake_exists)
  monkeypatch.setattr(joke_notes_sheet_operations.cloud_storage,
                      "upload_bytes_to_gcs", _fake_upload)
  monkeypatch.setattr(joke_notes_sheet_operations.pdf_client, "create_pdf",
                      _fake_create_pdf)
  monkeypatch.setattr(joke_notes_sheet_operations.firestore,
                      "upsert_joke_sheet", _fake_upsert)
  monkeypatch.setattr(joke_notes_sheet_operations, "_encode_png",
                      lambda _image: b"png-bytes")
  monkeypatch.setattr(
    joke_notes_sheet_operations, "_create_joke_notes_sheet_images",
    lambda jokes_arg, *, branded: page_images
    if jokes_arg == jokes and branded is True else [])

  result = joke_notes_sheet_operations.ensure_joke_notes_sheet(jokes)

  expected_stem = joke_notes_sheet_operations._generate_file_stem(
    [joke.key for joke in jokes if joke.key],
    quality=80,
    branded=True,
  )
  expected_image_uris = [
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}.png",
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}_2.png",
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}_3.png",
    f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}_4.png",
  ]
  expected_pdf_uri = (
    f"{joke_notes_sheet_operations._PDF_DIR_GCS_URI}/{expected_stem}.pdf")

  assert result.image_gcs_uri == expected_image_uris[0]
  assert result.image_gcs_uris == expected_image_uris
  assert result.pdf_gcs_uri == expected_pdf_uri
  assert result.joke_str_hash == expected_stem
  assert created_pdf_images == page_images
  assert uploaded == [
    (expected_image_uris[0], "image/png"),
    (expected_image_uris[1], "image/png"),
    (expected_image_uris[2], "image/png"),
    (expected_image_uris[3], "image/png"),
    (expected_pdf_uri, "application/pdf"),
  ]
